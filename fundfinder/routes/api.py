import logging
import time
from enum import StrEnum
from typing import Annotated, Any, Literal

from fastapi import APIRouter, Depends, HTTPException, Path, Query, Request
from pydantic import BaseModel, Field

from fundfinder.db import FUNDS, get_db
from fundfinder.intent import Sort, resolve_sort
from fundfinder.llm_intent import LlmInterpreter, LlmUnavailable, Vocabulary
from fundfinder.ratelimit import limit_llm, limit_search
from fundfinder.search import (
    CANDIDATES_PER_RESULT,
    MAX_LIMIT,
    MAX_NUM_CANDIDATES,
    Filters,
    FundSearch,
    Hit,
    Mode,
    default_num_candidates,
)
from fundfinder.taxonomy import ASSET_CLASS_BREAKDOWN, GICS_SECTORS, REGIONS
from fundfinder.understanding import Exclusions, Plan, Understood, merge, plan

router = APIRouter()
log = logging.getLogger("fundfinder")

# Fund ids are short codes (F0001); anything else is rejected before reaching Mongo.
FundId = Annotated[str, Path(pattern=r"^[A-Za-z0-9_-]{1,64}$", examples=["F0001"])]
# Keys look like "is_passive" or "not_sector:Information Technology".
MAX_IGNORE = 20


class Intent(StrEnum):
    rules = "rules"  # deterministic reading of explicit constraints (default)
    llm = "llm"  # Claude reads intent: typos, vague wording, implied indexes


def get_llm(request: Request) -> LlmInterpreter | None:
    return getattr(request.app.state, "llm", None)


async def get_vocabulary(request: Request, search: FundSearch) -> Vocabulary:
    # Fetched once per process: the vocabulary only changes on re-seed.
    vocab = getattr(request.app.state, "vocabulary", None)
    if vocab is None:
        vocab = Vocabulary.from_facets(await search.facets())
        request.app.state.vocabulary = vocab
    return vocab


def get_search(request: Request) -> FundSearch:
    settings = request.app.state.settings
    coll = get_db(request)[FUNDS]
    return FundSearch(coll, settings.embed_model)


def get_filters(
    asset_class: Annotated[str | None, Query(description="e.g. Equity, Fixed Income")] = None,
    ia_sector: Annotated[str | None, Query(description="IA sector, e.g. Global")] = None,
    ocf_max: Annotated[
        float | None, Query(ge=0, description="Maximum ongoing charge, in % a year")
    ] = None,
    is_passive: Annotated[
        bool | None, Query(description="true = index funds, false = active")
    ] = None,
) -> Filters:
    return Filters(
        asset_class=asset_class, ia_sector=ia_sector, ocf_max=ocf_max, is_passive=is_passive
    )


class SearchParams(BaseModel):
    limit: int
    num_candidates: int | None
    exact: bool


def get_params(
    limit: Annotated[int, Query(ge=1, le=MAX_LIMIT, description="Number of results")] = 10,
    num_candidates: Annotated[
        int | None,
        Query(ge=1, le=MAX_NUM_CANDIDATES, description="Default: 20 x limit"),
    ] = None,
    exact: Annotated[bool, Query(description="Exact (ENN) search instead of ANN")] = False,
) -> SearchParams:
    if num_candidates is not None and num_candidates < limit:
        raise HTTPException(422, "num_candidates must be >= limit")
    return SearchParams(limit=limit, num_candidates=num_candidates, exact=exact)


# With exclusions ("not tech") results are dropped after the search, so fetch
# more to still fill the page. If that still leaves the page short, look much
# deeper once: "tech but not US" must get past every US-heavy tech fund.
EXCLUSION_OVERFETCH = 3
EXCLUSION_DEEP_FETCH = 200


def _exclusion_rules(
    exclusions: Exclusions, applied: list[Understood]
) -> list[tuple[str, Exclusions]]:
    """Each applied post-filter on its own, with its chip label."""
    rules = []
    for item in applied:
        kind, _, value = item.key.partition(":")
        if kind == "not_sector":
            rules.append((item.label, Exclusions(sectors=[value])))
        elif kind == "not_region":
            rules.append((item.label, Exclusions(regions=[value])))
        elif kind == "tracks":
            rules.append((item.label, Exclusions(tracked_indexes=exclusions.tracked_indexes)))
    return list({label: r for label, r in rules}.items())


def _empty_notice(hits: list[Hit], exclusions: Exclusions, applied: list[Understood]) -> str:
    """Why exclusions left nothing: name the rule that removed the most matches."""

    def removed(rule: Exclusions) -> int:
        return sum(rule.excludes(h.sector_weights, h.region_weights, h.tracked_index) for h in hits)

    rules = _exclusion_rules(exclusions, applied)
    if not hits or not rules:
        return "No funds matched all of these. Try removing one."
    label, _ = max(rules, key=lambda r: removed(r[1]))
    return (
        f"No funds matched all of these. The closest matches are excluded by “{label}”: "
        "remove it to see them."
    )


def order_by(hits: list[Hit], order: Sort) -> None:
    """Re-order the best matches by cost, in place. Stable, so equal costs keep
    their match order. Relevance (and auto) leaves the list as it is."""
    if order in (Sort.cost, Sort.cost_desc):
        hits.sort(key=lambda h: h.ocf, reverse=order is Sort.cost_desc)


class Interpretation(BaseModel):
    source: Literal["rules", "llm"] = "rules"
    text: str = Field(description="What was embedded, after removing constraints")
    applied: list[Understood] = Field(
        description="Constraints read from the query; pass a key in `ignore` to drop it"
    )
    summary: str | None = Field(None, description="LLM only: how the query was read")
    notice: str | None = Field(None, description="E.g. why the LLM reading wasn't used")


class SearchResponse(BaseModel):
    query: str | None = None
    fund_id: str | None = None
    mode: Mode | None = None
    # Order of `results`: "cost" = ascending OCF, "cost_desc" = descending, else similarity.
    sort: Sort = Sort.relevance
    interpretation: Interpretation | None = None
    limit: int
    num_candidates: int | None
    exact: bool
    filters: dict[str, Any]
    took_ms: float
    results: list[Hit]


def _response(params: SearchParams, filters: Filters, started: float, **kw) -> SearchResponse:
    return SearchResponse(
        limit=params.limit,
        num_candidates=None
        if params.exact
        else params.num_candidates or default_num_candidates(params.limit),
        exact=params.exact,
        filters=filters.model_dump(exclude_none=True, exclude={"asset_class_nin", "ia_sector_nin"}),
        took_ms=round((time.perf_counter() - started) * 1000, 1),
        **kw,
    )


@router.get(
    "/search", response_model=SearchResponse, tags=["search"], dependencies=[Depends(limit_search)]
)
async def search(
    request: Request,
    q: Annotated[
        str,
        Query(
            min_length=1,
            max_length=2000,
            description="Plain-English description of the fund you want",
            examples=["lowest cost global tracker"],
        ),
    ],
    search: Annotated[FundSearch, Depends(get_search)],
    filters: Annotated[Filters, Depends(get_filters)],
    params: Annotated[SearchParams, Depends(get_params)],
    sort: Annotated[
        Sort,
        Query(
            description="auto: by annual cost if the query asks for low cost (cheapest first) "
            "or high cost (most expensive first), otherwise by match"
        ),
    ] = Sort.auto,
    interpret: Annotated[
        bool,
        Query(description="Read cost caps, fund type, asset class and negations from q"),
    ] = True,
    ignore: Annotated[
        list[str],
        Query(
            max_length=MAX_IGNORE,
            description="Keys from `interpretation.applied` to drop, e.g. is_passive",
        ),
    ] = [],  # noqa: B006 - FastAPI copies defaults per request
    intent: Annotated[
        Intent,
        Query(
            description="rules: read explicit constraints (default). llm: Claude also reads "
            "vague wording and typos, e.g. 'cheap well known Uk' -> cheap FTSE 100 trackers"
        ),
    ] = Intent.rules,
    llm: Annotated[LlmInterpreter | None, Depends(get_llm)] = None,
) -> SearchResponse:
    """Semantic search. Constraints in `q` ("under 0.2%", "index funds", "not tech")
    become filters; Atlas embeds the rest with Voyage and searches `profile_auto`."""
    started = time.perf_counter()
    source: Literal["rules", "llm"] = "rules"
    summary = notice = None
    llm_sort: Sort | None = None
    if intent is Intent.llm and interpret:
        if llm is None:
            raise HTTPException(503, "AI interpretation is not configured: set ANTHROPIC_API_KEY")
        limit_llm(request)
        try:
            reading = await llm.read(q, await get_vocabulary(request, search))
        except LlmUnavailable as exc:
            log.warning("LLM intent failed, using rules: %s", exc)
            notice = "AI interpretation is unavailable right now, so the standard reading was used."
            p = plan(q, filters, set(ignore))
        else:
            source, summary, llm_sort = "llm", reading.summary, reading.sort
            p = merge(
                reading.text,
                reading.filters,
                reading.exclusions,
                reading.applied,
                explicit=filters,
                ignore=set(ignore),
            )
    elif interpret:
        p = plan(q, filters, set(ignore))
    else:
        p = Plan(text=q, filters=filters, exclusions=Exclusions(), applied=[])
    text, effective, exclusions, applied = p.text, p.filters, p.exclusions, p.applied

    async def fetch_hits(fetch: int) -> list[Hit]:
        return await search.search_text(
            text,
            limit=fetch,
            num_candidates=None
            if params.num_candidates is None and not exclusions
            else max(params.num_candidates or default_num_candidates(params.limit), fetch),
            filters=effective,
            exact=params.exact,
        )

    def kept(found: list[Hit]) -> list[Hit]:
        return [
            h
            for h in found
            if not exclusions.excludes(h.sector_weights, h.region_weights, h.tracked_index)
        ]

    fetch = params.limit * EXCLUSION_OVERFETCH if exclusions else params.limit
    found = await fetch_hits(fetch)
    hits = kept(found) if exclusions else found
    # Short page, and the search had more to give: look deeper once.
    if exclusions and len(hits) < params.limit and len(found) == fetch < EXCLUSION_DEEP_FETCH:
        found = await fetch_hits(EXCLUSION_DEEP_FETCH)
        hits = kept(found)
    if exclusions and not hits:
        notice = " ".join(filter(None, [notice, _empty_notice(found, exclusions, applied)]))
    hits = hits[: params.limit]
    order = llm_sort if sort is Sort.auto and llm_sort else resolve_sort(sort, q)
    order_by(hits, order)
    return _response(
        params,
        effective,
        started,
        query=q,
        sort=order,
        interpretation=Interpretation(
            source=source, text=text, applied=applied, summary=summary, notice=notice
        ),
        results=hits,
    )


@router.get(
    "/funds/{fund_id}/similar",
    response_model=SearchResponse,
    tags=["search"],
    dependencies=[Depends(limit_search)],
)
async def similar(
    fund_id: FundId,
    search: Annotated[FundSearch, Depends(get_search)],
    filters: Annotated[Filters, Depends(get_filters)],
    params: Annotated[SearchParams, Depends(get_params)],
    mode: Annotated[
        Mode,
        Query(description="text: description · exposure: holdings mix · both: RRF fusion"),
    ] = Mode.both,
    sort: Annotated[
        Sort,
        Query(description="relevance, or cost / cost_desc to show the matches by annual cost"),
    ] = Sort.relevance,
) -> SearchResponse:
    """Funds most like this one, excluding itself."""
    started = time.perf_counter()
    hits = await search.similar(
        fund_id,
        mode,
        limit=params.limit,
        num_candidates=params.num_candidates,
        filters=filters,
        exact=params.exact,
    )
    if hits is None:
        raise HTTPException(404, f"fund {fund_id} not found")
    order = Sort.relevance if sort is Sort.auto else sort  # no query text to read
    order_by(hits, order)
    return _response(params, filters, started, fund_id=fund_id, mode=mode, sort=order, results=hits)


@router.get("/funds/{fund_id}", tags=["funds"])
async def get_fund(
    fund_id: FundId,
    search: Annotated[FundSearch, Depends(get_search)],
) -> dict[str, Any]:
    """One fund: facts, holdings, sector/region/asset weights and exposure vector."""
    fund = await search.get_fund(fund_id)
    if fund is None:
        raise HTTPException(404, f"fund {fund_id} not found")
    fund["id"] = fund.pop("_id")
    return fund


@router.get("/meta", tags=["reference"])
async def meta(
    request: Request,
    search: Annotated[FundSearch, Depends(get_search)],
    llm: Annotated[LlmInterpreter | None, Depends(get_llm)],
) -> dict[str, Any]:
    """Filter options, exposure-vector layout and search defaults for clients."""
    return {
        **await search.facets(),
        "exposure_layout": {
            "sectors": GICS_SECTORS,
            "regions": REGIONS,
            "asset_classes": ASSET_CLASS_BREAKDOWN,
        },
        "embed_model": request.app.state.settings.embed_model,
        # Whether the "Interpret with AI" option can be offered.
        "llm_intent": {"available": llm is not None, "model": llm.model if llm else None},
        "defaults": {
            "limit": 10,
            "max_limit": MAX_LIMIT,
            "candidates_per_result": CANDIDATES_PER_RESULT,
            "max_num_candidates": MAX_NUM_CANDIDATES,
        },
    }


@router.get("/clusters", tags=["reference"])
async def clusters(
    search: Annotated[FundSearch, Depends(get_search)],
) -> dict[str, list[dict[str, str]]]:
    """Deliberate test clusters in the synthetic data (empty for real data)."""
    return await search.clusters()
