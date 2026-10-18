import pytest
from fastapi.testclient import TestClient
from pymongo.errors import OperationFailure

from fundfinder.main import create_app
from fundfinder.routes.api import get_search
from fundfinder.search import Hit, Mode


def make_hit(fid: str, score: float = 0.8) -> Hit:
    return Hit(
        id=fid, name=f"Fund {fid}", provider="P", ia_sector="Global", asset_class="Equity",
        ocf=0.4, is_passive=False, score=score,
    )  # fmt: skip


class FakeSearch:
    def __init__(self, fail: str | None = None):
        self.calls: list[tuple] = []
        self.fail = fail

    async def search_text(self, q, **kw):
        if self.fail:
            raise OperationFailure(self.fail)
        self.calls.append(("search", q, kw))
        return [make_hit("F2", 0.9), make_hit("F3", 0.7)]

    async def similar(self, fund_id, mode, **kw):
        self.calls.append(("similar", fund_id, mode, kw))
        return None if fund_id == "MISSING" else [make_hit("F9")]

    async def get_fund(self, fund_id):
        return None if fund_id == "MISSING" else {"_id": fund_id, "name": "Fund"}


@pytest.fixture
def fake():
    return FakeSearch()


@pytest.fixture
def client(fake):
    app = create_app()
    app.dependency_overrides[get_search] = lambda: fake
    with TestClient(app) as c:
        yield c


def test_search_returns_results_and_defaults(client, fake):
    r = client.get("/search", params={"q": "uk dividend"})
    assert r.status_code == 200
    body = r.json()
    assert [h["id"] for h in body["results"]] == ["F2", "F3"]
    assert body["limit"] == 10 and body["num_candidates"] == 200 and body["exact"] is False
    _, q, kw = fake.calls[0]
    assert q == "uk dividend"
    assert kw["limit"] == 10 and kw["num_candidates"] is None


def test_search_passes_filters(client, fake):
    r = client.get(
        "/search",
        params={"q": "x", "asset_class": "Equity", "ocf_max": 0.3, "is_passive": "true"},
    )
    assert r.status_code == 200
    assert r.json()["filters"] == {"asset_class": "Equity", "ocf_max": 0.3, "is_passive": True}
    filters = fake.calls[0][2]["filters"]
    assert filters.asset_class == "Equity" and filters.ocf_max == 0.3 and filters.is_passive


@pytest.mark.parametrize(
    "params",
    [
        {},  # q missing
        {"q": ""},
        {"q": "x", "limit": 0},
        {"q": "x", "limit": 101},
        {"q": "x", "limit": 10, "num_candidates": 5},  # fewer candidates than limit
        {"q": "x", "ocf_max": -1},
    ],
)
def test_search_validation(client, params):
    assert client.get("/search", params=params).status_code == 422


def test_search_exact_reports_no_num_candidates(client):
    body = client.get("/search", params={"q": "x", "exact": "true"}).json()
    assert body["exact"] is True and body["num_candidates"] is None


def test_similar_modes(client, fake):
    for mode in ("text", "exposure", "both"):
        r = client.get("/funds/F1/similar", params={"mode": mode, "limit": 5})
        assert r.status_code == 200
        assert r.json()["mode"] == mode
        assert r.json()["num_candidates"] == 100
    assert [c[2] for c in fake.calls] == [Mode.text, Mode.exposure, Mode.both]


def test_similar_default_mode_is_both(client, fake):
    client.get("/funds/F1/similar")
    assert fake.calls[0][2] is Mode.both


def test_similar_bad_mode(client):
    assert client.get("/funds/F1/similar", params={"mode": "nope"}).status_code == 422


def test_similar_unknown_fund_404(client):
    assert client.get("/funds/MISSING/similar").status_code == 404


def test_get_fund(client):
    assert client.get("/funds/F1").json() == {"id": "F1", "name": "Fund"}
    assert client.get("/funds/MISSING").status_code == 404


def _search_failing_with(message: str):
    app = create_app()
    app.dependency_overrides[get_search] = lambda: FakeSearch(fail=message)
    with TestClient(app) as c:
        return c.get("/search", params={"q": "x"})


def test_database_error_returns_503():
    r = _search_failing_with("boom")
    assert r.status_code == 503
    assert r.json() == {"detail": "database unavailable"}


def test_embedding_rate_limit_returns_429():
    r = _search_failing_with(
        "PlanExecutor error during aggregation :: caused by :: "
        "Embedding provider rate limit exceeded, retry later"
    )
    assert r.status_code == 429
    assert r.headers["retry-after"] == "20"
