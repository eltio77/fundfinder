import time
from typing import Annotated, Any

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from pydantic import BaseModel

from fundfinder.db import FUNDS, get_db
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

router = APIRouter()


def get_search(request: Request) -> FundSearch:
    settings = request.app.state.settings
    coll = get_db(request)[FUNDS]
    return FundSearch(coll, settings.embed_model)


def get_filters(
    asset_class: str | None = None,
    ia_sector: str | None = None,
    ocf_max: Annotated[float | None, Query(ge=0)] = None,
    is_passive: bool | None = None,
) -> Filters:
    return Filters(
        asset_class=asset_class, ia_sector=ia_sector, ocf_max=ocf_max, is_passive=is_passive
    )


class SearchParams(BaseModel):
    limit: int
    num_candidates: int | None
    exact: bool


def get_params(
    limit: Annotated[int, Query(ge=1, le=MAX_LIMIT)] = 10,
    num_candidates: Annotated[
        int | None,
        Query(ge=1, le=MAX_NUM_CANDIDATES, description="Default: 20 x limit"),
    ] = None,
    exact: Annotated[bool, Query(description="Exact (ENN) search instead of ANN")] = False,
) -> SearchParams:
    if num_candidates is not None and num_candidates < limit:
        raise HTTPException(422, "num_candidates must be >= limit")
    return SearchParams(limit=limit, num_candidates=num_candidates, exact=exact)


class SearchResponse(BaseModel):
    query: str | None = None
    fund_id: str | None = None
    mode: Mode | None = None
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
        filters=filters.model_dump(exclude_none=True),
        took_ms=round((time.perf_counter() - started) * 1000, 1),
        **kw,
    )


@router.get("/search", response_model=SearchResponse)
async def search(
    q: Annotated[str, Query(min_length=1, max_length=2000)],
    search: Annotated[FundSearch, Depends(get_search)],
    filters: Annotated[Filters, Depends(get_filters)],
    params: Annotated[SearchParams, Depends(get_params)],
) -> SearchResponse:
    started = time.perf_counter()
    hits = await search.search_text(
        q,
        limit=params.limit,
        num_candidates=params.num_candidates,
        filters=filters,
        exact=params.exact,
    )
    return _response(params, filters, started, query=q, results=hits)


@router.get("/funds/{fund_id}/similar", response_model=SearchResponse)
async def similar(
    fund_id: str,
    search: Annotated[FundSearch, Depends(get_search)],
    filters: Annotated[Filters, Depends(get_filters)],
    params: Annotated[SearchParams, Depends(get_params)],
    mode: Mode = Mode.both,
) -> SearchResponse:
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
    return _response(params, filters, started, fund_id=fund_id, mode=mode, results=hits)


@router.get("/funds/{fund_id}")
async def get_fund(
    fund_id: str, search: Annotated[FundSearch, Depends(get_search)]
) -> dict[str, Any]:
    fund = await search.get_fund(fund_id)
    if fund is None:
        raise HTTPException(404, f"fund {fund_id} not found")
    fund["id"] = fund.pop("_id")
    return fund


@router.get("/meta")
async def meta(
    request: Request, search: Annotated[FundSearch, Depends(get_search)]
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
        "defaults": {
            "limit": 10,
            "max_limit": MAX_LIMIT,
            "candidates_per_result": CANDIDATES_PER_RESULT,
            "max_num_candidates": MAX_NUM_CANDIDATES,
        },
    }


@router.get("/clusters")
async def clusters(
    search: Annotated[FundSearch, Depends(get_search)],
) -> dict[str, list[dict[str, str]]]:
    """Deliberate test clusters in the synthetic data (empty for real data)."""
    return await search.clusters()
