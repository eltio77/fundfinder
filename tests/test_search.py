import asyncio

import pytest

from fundfinder.indexes import (
    EXPOSURE_INDEX,
    PROFILE_INDEX,
    definition_matches,
    index_definitions,
)
from fundfinder.search import Filters, FundSearch, Mode, fuse, vector_search_pipeline


def hit(fid: str, score: float = 0.9) -> dict:
    return dict(
        _id=fid,
        name=f"Fund {fid}",
        provider="P",
        ia_sector="Global",
        asset_class="Equity",
        ocf=0.5,
        is_passive=False,
        score=score,
    )


class FakeCursor:
    def __init__(self, docs):
        self.docs = docs

    async def to_list(self):
        return self.docs


class FakeCollection:
    """Returns canned results per index and records the pipelines it saw."""

    def __init__(self, fund: dict, by_index: dict[str, list[dict]]):
        self.fund = fund
        self.by_index = by_index
        self.pipelines: list[list[dict]] = []

    async def find_one(self, q):
        return self.fund if q["_id"] == self.fund["_id"] else None

    async def aggregate(self, pipeline):
        self.pipelines.append(pipeline)
        stage = pipeline[0]["$vectorSearch"]
        return FakeCursor(self.by_index[stage["index"]][: stage["limit"]])


FUND = {"_id": "F1", "profile": "UK income fund", "exposure_vector": [0.1] * 26}


def run(coro):
    return asyncio.run(coro)


# ----------------------------------------------------------------- filters


def test_filters_to_mql():
    assert Filters().to_mql() is None
    assert Filters(asset_class="Equity").to_mql() == {"asset_class": {"$eq": "Equity"}}
    mql = Filters(ocf_max=0.2, is_passive=True).to_mql()
    assert mql == {"$and": [{"ocf": {"$lte": 0.2}}, {"is_passive": {"$eq": True}}]}


# ---------------------------------------------------------------- pipeline


def test_text_pipeline_defaults_num_candidates_to_20x_limit():
    stage = vector_search_pipeline(
        index=PROFILE_INDEX, path="profile", query="gilts", model="voyage-4", limit=5,
        num_candidates=None,
    )[0]["$vectorSearch"]  # fmt: skip
    assert stage == {
        "index": PROFILE_INDEX,
        "path": "profile",
        "query": "gilts",
        "model": "voyage-4",
        "limit": 5,
        "numCandidates": 100,
    }


def test_vector_pipeline_exact_omits_num_candidates_and_adds_filter():
    stage = vector_search_pipeline(
        index=EXPOSURE_INDEX, path="exposure_vector", query_vector=[1.0], limit=3,
        num_candidates=50, exact=True, filters=Filters(asset_class="Equity"),
    )[0]["$vectorSearch"]  # fmt: skip
    assert stage["exact"] is True
    assert "numCandidates" not in stage
    assert stage["queryVector"] == [1.0]
    assert stage["filter"] == {"asset_class": {"$eq": "Equity"}}


def test_pipeline_requires_exactly_one_query():
    with pytest.raises(ValueError):
        vector_search_pipeline(index="i", path="p", limit=1, num_candidates=None)
    with pytest.raises(ValueError):
        vector_search_pipeline(
            index="i", path="p", limit=1, num_candidates=None, query="x", query_vector=[1.0]
        )


def test_pipeline_projects_score():
    project = vector_search_pipeline(index="i", path="p", query="x", limit=1, num_candidates=None)[
        1
    ]["$project"]
    assert project["score"] == {"$meta": "vectorSearchScore"}


# --------------------------------------------------------------- similar


def test_similar_text_excludes_self_and_uses_profile_as_query():
    coll = FakeCollection(FUND, {PROFILE_INDEX: [hit("F1", 1.0), hit("F2"), hit("F3")]})
    hits = run(FundSearch(coll, "voyage-4").similar("F1", Mode.text, limit=2))
    assert [h.id for h in hits] == ["F2", "F3"]
    stage = coll.pipelines[0][0]["$vectorSearch"]
    assert stage["query"] == "UK income fund"
    assert stage["limit"] == 3  # limit + 1 to allow for self
    assert stage["numCandidates"] == 40


def test_similar_exposure_uses_stored_vector_and_truncates_when_self_absent():
    coll = FakeCollection(FUND, {EXPOSURE_INDEX: [hit("F2"), hit("F3"), hit("F4")]})
    hits = run(FundSearch(coll, "voyage-4").similar("F1", Mode.exposure, limit=2))
    assert [h.id for h in hits] == ["F2", "F3"]
    assert coll.pipelines[0][0]["$vectorSearch"]["queryVector"] == FUND["exposure_vector"]


def test_similar_both_fuses_lists():
    coll = FakeCollection(
        FUND,
        {
            PROFILE_INDEX: [hit("F1"), hit("F2"), hit("F3"), hit("F5")],
            EXPOSURE_INDEX: [hit("F1"), hit("F4"), hit("F3"), hit("F2")],
        },
    )
    hits = run(FundSearch(coll, "voyage-4").similar("F1", Mode.both, limit=2))
    # F2: text 1 + exposure 3; F3: text 2 + exposure 2 -> F2 and F3 beat F4 (exposure only).
    assert [h.id for h in hits] == ["F2", "F3"]
    assert hits[0].ranks == {"text": 1, "exposure": 3}
    assert all(h.id != "F1" for h in hits)
    assert len(coll.pipelines) == 2


def test_similar_unknown_fund_returns_none():
    coll = FakeCollection(FUND, {})
    assert run(FundSearch(coll, "voyage-4").similar("NOPE", Mode.text)) is None


def test_fuse_marks_missing_ranks():
    from fundfinder.search import Hit

    a, b = Hit.model_validate(hit("A")), Hit.model_validate(hit("B"))
    fused = fuse([a], [b])
    assert {h.id: h.ranks for h in fused} == {
        "A": {"text": 1, "exposure": None},
        "B": {"text": None, "exposure": 1},
    }


# ----------------------------------------------------------------- indexes


def test_index_definitions_use_filters_and_model():
    defs = index_definitions("voyage-4")
    auto = defs[PROFILE_INDEX]["fields"][0]
    assert auto == {"type": "autoEmbed", "modality": "text", "path": "profile", "model": "voyage-4"}
    vec = defs[EXPOSURE_INDEX]["fields"][0]
    assert vec["numDimensions"] == 26 and vec["similarity"] == "cosine"
    for d in defs.values():
        filters = {f["path"] for f in d["fields"] if f["type"] == "filter"}
        assert filters == {"asset_class", "ia_sector", "ocf", "is_passive"}


def test_definition_matches_ignores_server_defaults():
    desired = index_definitions("voyage-4")[EXPOSURE_INDEX]
    actual = {"fields": [dict(f) for f in desired["fields"]]}
    actual["fields"][0]["quantization"] = "none"  # default added by Atlas
    assert definition_matches(desired, actual)
    assert not definition_matches(desired, None)
    changed = {"fields": [dict(f) for f in desired["fields"]]}
    changed["fields"][0]["similarity"] = "euclidean"
    assert not definition_matches(desired, changed)
    assert not definition_matches(desired, {"fields": desired["fields"][:-1]})


def test_clusters_groups_members():
    class Cursor:
        def __init__(self, docs):
            self.docs = docs

        def sort(self, *a):
            return self

        def __aiter__(self):
            async def gen():
                for d in self.docs:
                    yield d

            return gen()

    class Coll:
        def find(self, q, proj):
            assert q == {"cluster_id": {"$ne": None}}
            return Cursor(
                [
                    {"_id": "F1", "name": "A", "cluster_id": "trk_b"},
                    {"_id": "F2", "name": "B", "cluster_id": "act_a"},
                    {"_id": "F3", "name": "C", "cluster_id": "trk_b"},
                ]
            )

    out = run(FundSearch(Coll(), "voyage-4").clusters())
    assert list(out) == ["act_a", "trk_b"]
    assert out["trk_b"] == [{"id": "F1", "name": "A"}, {"id": "F3", "name": "C"}]
