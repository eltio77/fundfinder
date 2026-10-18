"""Vector search over the funds collection: $vectorSearch pipeline builders and
the text / exposure / fused similarity modes."""

import asyncio
from enum import StrEnum
from typing import Any

from pydantic import AliasChoices, BaseModel, Field
from pymongo.asynchronous.collection import AsyncCollection

from fundfinder.indexes import EXPOSURE_INDEX, PROFILE_INDEX
from fundfinder.rrf import reciprocal_rank_fusion

CANDIDATES_PER_RESULT = 20
MAX_NUM_CANDIDATES = 10_000  # Atlas limit
MAX_LIMIT = 100
# In "both" mode each component list is fetched deeper than `limit` so fusion
# can promote funds that rank moderately well in both.
FUSION_DEPTH_FACTOR = 2

HIT_FIELDS = (
    "name",
    "provider",
    "ia_sector",
    "asset_class",
    "ocf",
    "is_passive",
    "tracked_index",
    "cluster_id",
    "exposure_vector",
    "sector_weights",
    "region_weights",
)


class Mode(StrEnum):
    text = "text"
    exposure = "exposure"
    both = "both"


class Filters(BaseModel):
    asset_class: str | None = None
    ia_sector: str | None = None
    ocf_max: float | None = Field(default=None, ge=0)
    is_passive: bool | None = None
    # Set by query understanding ("no bonds"), not exposed as a query parameter.
    asset_class_nin: list[str] | None = None

    def to_mql(self) -> dict[str, Any] | None:
        clauses: list[dict[str, Any]] = []
        if self.asset_class is not None:
            clauses.append({"asset_class": {"$eq": self.asset_class}})
        if self.ia_sector is not None:
            clauses.append({"ia_sector": {"$eq": self.ia_sector}})
        if self.ocf_max is not None:
            clauses.append({"ocf": {"$lte": self.ocf_max}})
        if self.is_passive is not None:
            clauses.append({"is_passive": {"$eq": self.is_passive}})
        if self.asset_class_nin:
            clauses.append({"asset_class": {"$nin": self.asset_class_nin}})
        if not clauses:
            return None
        return clauses[0] if len(clauses) == 1 else {"$and": clauses}


class Hit(BaseModel):
    id: str = Field(validation_alias=AliasChoices("_id", "id"))
    name: str
    provider: str
    ia_sector: str
    asset_class: str
    ocf: float
    is_passive: bool
    tracked_index: str | None = None
    # Synthetic-data evaluation label; lets the UI mark same-cluster results.
    cluster_id: str | None = None
    # Returned so clients can show why two funds look alike (26 floats).
    exposure_vector: list[float] | None = None
    # Used server-side for exclusions ("not tech"); left out of responses.
    sector_weights: dict[str, float] = Field(default_factory=dict, exclude=True)
    region_weights: dict[str, float] = Field(default_factory=dict, exclude=True)
    score: float
    # Only in "both" mode: 1-based rank in each component list (None = absent).
    ranks: dict[str, int | None] | None = None


def default_num_candidates(limit: int) -> int:
    return min(limit * CANDIDATES_PER_RESULT, MAX_NUM_CANDIDATES)


def vector_search_pipeline(
    *,
    index: str,
    path: str,
    limit: int,
    num_candidates: int | None,
    query: str | None = None,
    query_vector: list[float] | None = None,
    model: str | None = None,
    filters: Filters | None = None,
    exact: bool = False,
) -> list[dict[str, Any]]:
    if (query is None) == (query_vector is None):
        raise ValueError("pass exactly one of query or query_vector")
    stage: dict[str, Any] = {"index": index, "path": path, "limit": limit}
    if query is not None:
        stage["query"] = query
        if model:
            stage["model"] = model
    else:
        stage["queryVector"] = query_vector
    if exact:
        stage["exact"] = True
    else:
        stage["numCandidates"] = max(num_candidates or default_num_candidates(limit), limit)
    mql = filters.to_mql() if filters else None
    if mql:
        stage["filter"] = mql
    projection = {f: 1 for f in HIT_FIELDS} | {"score": {"$meta": "vectorSearchScore"}}
    return [{"$vectorSearch": stage}, {"$project": projection}]


class FundSearch:
    def __init__(self, coll: AsyncCollection, embed_model: str) -> None:
        self.coll = coll
        self.embed_model = embed_model

    async def _run(self, pipeline: list[dict[str, Any]]) -> list[Hit]:
        cursor = await self.coll.aggregate(pipeline)
        return [Hit.model_validate(doc) for doc in await cursor.to_list()]

    async def get_fund(self, fund_id: str) -> dict[str, Any] | None:
        return await self.coll.find_one({"_id": fund_id})

    async def clusters(self) -> dict[str, list[dict[str, str]]]:
        """Synthetic evaluation clusters -> member funds (id, name), for test navigation."""
        cursor = self.coll.find({"cluster_id": {"$ne": None}}, {"name": 1, "cluster_id": 1}).sort(
            "_id", 1
        )
        out: dict[str, list[dict[str, str]]] = {}
        async for doc in cursor:
            out.setdefault(doc["cluster_id"], []).append({"id": doc["_id"], "name": doc["name"]})
        return dict(sorted(out.items()))

    async def facets(self) -> dict[str, list[str]]:
        """Distinct values for the filter dropdowns."""
        ia_sectors, asset_classes = await asyncio.gather(
            self.coll.distinct("ia_sector"), self.coll.distinct("asset_class")
        )
        return {"ia_sectors": sorted(ia_sectors), "asset_classes": sorted(asset_classes)}

    async def search_text(
        self,
        q: str,
        *,
        limit: int = 10,
        num_candidates: int | None = None,
        filters: Filters | None = None,
        exact: bool = False,
    ) -> list[Hit]:
        return await self._run(
            vector_search_pipeline(
                index=PROFILE_INDEX,
                path="profile",
                query=q,
                model=self.embed_model,
                limit=limit,
                num_candidates=num_candidates,
                filters=filters,
                exact=exact,
            )
        )

    async def neighbours(
        self,
        fund: dict[str, Any],
        mode: Mode,
        *,
        limit: int,
        num_candidates: int | None,
        filters: Filters | None,
        exact: bool,
    ) -> list[Hit]:
        """Top `limit` neighbours for one mode, excluding the fund itself.
        Asks for limit + 1 because the fund is usually its own nearest match."""
        fetch = limit + 1
        candidates = max(num_candidates or default_num_candidates(limit), fetch)
        if mode is Mode.text:
            pipeline = vector_search_pipeline(
                index=PROFILE_INDEX,
                path="profile",
                query=fund["profile"],
                model=self.embed_model,
                limit=fetch,
                num_candidates=candidates,
                filters=filters,
                exact=exact,
            )
        else:
            pipeline = vector_search_pipeline(
                index=EXPOSURE_INDEX,
                path="exposure_vector",
                query_vector=fund["exposure_vector"],
                limit=fetch,
                num_candidates=candidates,
                filters=filters,
                exact=exact,
            )
        hits = await self._run(pipeline)
        return [h for h in hits if h.id != fund["_id"]][:limit]

    async def similar(
        self,
        fund_id: str,
        mode: Mode,
        *,
        limit: int = 10,
        num_candidates: int | None = None,
        filters: Filters | None = None,
        exact: bool = False,
    ) -> list[Hit] | None:
        """None if the fund doesn't exist."""
        fund = await self.get_fund(fund_id)
        if fund is None:
            return None
        opts = {"num_candidates": num_candidates, "filters": filters, "exact": exact}
        if mode is not Mode.both:
            return await self.neighbours(fund, mode, limit=limit, **opts)

        depth = limit * FUSION_DEPTH_FACTOR
        opts["num_candidates"] = max(num_candidates or default_num_candidates(limit), depth + 1)
        text_hits, exposure_hits = await asyncio.gather(
            self.neighbours(fund, Mode.text, limit=depth, **opts),
            self.neighbours(fund, Mode.exposure, limit=depth, **opts),
        )
        return fuse(text_hits, exposure_hits)[:limit]


def fuse(text_hits: list[Hit], exposure_hits: list[Hit]) -> list[Hit]:
    """RRF over the two lists; score becomes the RRF score."""
    by_id = {h.id: h for h in exposure_hits} | {h.id: h for h in text_hits}
    text_rank = {h.id: i for i, h in enumerate(text_hits, start=1)}
    exposure_rank = {h.id: i for i, h in enumerate(exposure_hits, start=1)}
    fused = reciprocal_rank_fusion([[h.id for h in text_hits], [h.id for h in exposure_hits]])
    return [
        by_id[fid].model_copy(
            update={
                "score": round(score, 6),
                "ranks": {"text": text_rank.get(fid), "exposure": exposure_rank.get(fid)},
            }
        )
        for fid, score in fused
    ]
