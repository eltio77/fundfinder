import pytest
from fastapi.testclient import TestClient
from pymongo.errors import OperationFailure

from fundfinder.main import create_app
from fundfinder.routes.api import get_search
from fundfinder.search import Hit, Mode


def make_hit(fid: str, score: float = 0.8, ocf: float = 0.4) -> Hit:
    return Hit(
        id=fid, name=f"Fund {fid}", provider="P", ia_sector="Global", asset_class="Equity",
        ocf=ocf, is_passive=False, score=score,
    )  # fmt: skip


class FakeSearch:
    def __init__(self, fail: str | None = None):
        self.calls: list[tuple] = []
        self.fail = fail

    async def search_text(self, q, **kw):
        if self.fail:
            raise OperationFailure(self.fail)
        self.calls.append(("search", q, kw))
        return [make_hit("F2", 0.9), make_hit("F3", 0.7, ocf=0.1), make_hit("F4", 0.6)]

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
    assert [h["id"] for h in body["results"]] == ["F2", "F3", "F4"]
    assert body["sort"] == "relevance"
    assert body["limit"] == 10 and body["num_candidates"] == 200 and body["exact"] is False
    _, q, kw = fake.calls[0]
    assert q == "uk dividend"
    assert kw["limit"] == 10 and kw["num_candidates"] is None


@pytest.mark.parametrize("q", ["lowest cost global tracker", "a cheap UK fund"])
def test_low_cost_query_sorts_by_annual_cost(client, q):
    body = client.get("/search", params={"q": q}).json()
    assert body["sort"] == "cost"
    # Cheapest first; equal costs keep match order.
    assert [h["id"] for h in body["results"]] == ["F3", "F2", "F4"]


@pytest.mark.parametrize("q", ["highest cost global fund", "the most expensive fund"])
def test_high_cost_query_sorts_by_annual_cost_descending(client, q):
    body = client.get("/search", params={"q": q}).json()
    assert body["sort"] == "cost_desc"
    # Most expensive first; equal costs keep match order.
    assert [h["id"] for h in body["results"]] == ["F2", "F4", "F3"]


@pytest.mark.parametrize(
    ("q", "sort", "expected"),
    [
        ("lowest cost tracker", "relevance", ["F2", "F3", "F4"]),
        ("uk dividend", "cost", ["F3", "F2", "F4"]),
        ("cheapest tracker", "cost_desc", ["F2", "F4", "F3"]),
    ],
)
def test_explicit_sort_overrides_detection(client, q, sort, expected):
    body = client.get("/search", params={"q": q, "sort": sort}).json()
    assert body["sort"] == sort
    assert [h["id"] for h in body["results"]] == expected


def test_search_passes_filters(client, fake):
    r = client.get(
        "/search",
        params={"q": "x", "asset_class": "Equity", "ocf_max": 0.3, "is_passive": "true"},
    )
    assert r.status_code == 200
    assert r.json()["filters"] == {"asset_class": "Equity", "ocf_max": 0.3, "is_passive": True}
    filters = fake.calls[0][2]["filters"]
    assert filters.asset_class == "Equity" and filters.ocf_max == 0.3 and filters.is_passive


def test_search_interprets_constraints(client, fake):
    body = client.get("/search", params={"q": "index funds under 0.2% a year, no bonds"}).json()
    _, text, kw = fake.calls[0]
    assert text == "index funds"  # what gets embedded
    f = kw["filters"]
    assert f.is_passive is True and f.ocf_max == 0.2 and f.asset_class_nin == ["Fixed Income"]
    assert body["interpretation"]["text"] == "index funds"
    assert [a["key"] for a in body["interpretation"]["applied"]] == [
        "ocf_max",
        "is_passive",
        "not_asset:Fixed Income",
    ]
    assert body["filters"] == {"ocf_max": 0.2, "is_passive": True}


def test_search_ignore_and_interpret_off(client, fake):
    client.get("/search", params={"q": "index funds under 0.2%", "ignore": ["is_passive"]})
    assert fake.calls[-1][2]["filters"].is_passive is None
    assert fake.calls[-1][2]["filters"].ocf_max == 0.2

    body = client.get(
        "/search", params={"q": "index funds under 0.2%", "interpret": "false"}
    ).json()
    assert fake.calls[-1][1] == "index funds under 0.2%"
    assert fake.calls[-1][2]["filters"].ocf_max is None
    assert body["interpretation"]["applied"] == []


def test_search_exclusions_drop_mainly_matching_funds(client, fake):
    tech = make_hit("T1", 0.95)
    tech.sector_weights = {"Information Technology": 0.7}
    broad = make_hit("G1", 0.9)
    broad.sector_weights = {"Information Technology": 0.25}

    async def search_text(q, **kw):
        fake.calls.append(("search", q, kw))
        return [tech, broad]

    fake.search_text = search_text
    body = client.get("/search", params={"q": "global equity but not tech", "limit": 5}).json()
    assert [h["id"] for h in body["results"]] == ["G1"]
    assert "sector_weights" not in body["results"][0]  # internal only
    _, text, kw = fake.calls[0]
    assert text == "global equity"
    assert kw["limit"] == 200  # fetched deep to fill the page after exclusions
    assert kw["num_candidates"] >= 200


def us_tech(fid: str) -> Hit:
    hit = make_hit(fid)
    hit.region_weights = {"North America": 0.8}
    return hit


def test_search_exclusions_fetch_deep_in_one_pass(client, fake):
    async def search_text(q, **kw):
        fake.calls.append(("search", q, kw))
        hits = [us_tech(f"T{i}") for i in range(kw["limit"])]
        hits[-1] = make_hit("EU1")  # the only non-US fund is far down the list
        return hits

    fake.search_text = search_text
    body = client.get("/search", params={"q": "tech but not US", "limit": 5}).json()
    assert [c[2]["limit"] for c in fake.calls] == [200]  # one search, one embedding
    assert [h["id"] for h in body["results"]] == ["EU1"]
    assert body["interpretation"]["notice"] is None


def test_search_explains_when_exclusions_leave_nothing(client, fake):
    async def search_text(q, **kw):
        fake.calls.append(("search", q, kw))
        return [us_tech("T1"), us_tech("T2")]

    fake.search_text = search_text
    body = client.get("/search", params={"q": "tech but not US"}).json()
    assert body["results"] == [] and len(fake.calls) == 1
    notice = body["interpretation"]["notice"]
    assert "No funds matched all of these" in notice
    assert "“Not mainly North America”" in notice


def test_search_runs_each_alternative_and_merges(client, fake):
    async def search_text(q, **kw):
        fake.calls.append(("search", q, kw))
        side = "T" if q.startswith("tech") else "H"
        return [make_hit(f"{side}{i}", 0.9 - i / 100) for i in range(3)]

    fake.search_text = search_text
    body = client.get("/search", params={"q": "tech or healthcare funds", "limit": 4}).json()
    assert sorted(c[1] for c in fake.calls) == ["healthcare funds", "tech funds"]
    assert [h["id"] for h in body["results"]] == ["T0", "H0", "T1", "H1"]
    interp = body["interpretation"]
    assert interp["alternatives"] == ["tech funds", "healthcare funds"]
    assert {"key": "any_of", "label": "Any of: tech · healthcare"} in interp["applied"]


def test_search_alternatives_can_be_turned_off(client, fake):
    params = {"q": "tech or healthcare", "ignore": ["any_of"]}
    body = client.get("/search", params=params).json()
    assert [c[1] for c in fake.calls] == ["tech or healthcare"]
    assert body["interpretation"]["alternatives"] == []


class FakeLlm:
    model = "claude-test"

    def __init__(self, fail: bool = False):
        self.fail = fail
        self.calls: list[str] = []

    async def read(self, q, vocab):
        from fundfinder.intent import Sort
        from fundfinder.llm_intent import LlmReading, LlmUnavailable
        from fundfinder.search import Filters
        from fundfinder.understanding import Exclusions, Understood

        self.calls.append(q)
        if self.fail:
            raise LlmUnavailable("down")
        return LlmReading(
            text="UK large companies index fund tracking the FTSE 100",
            filters=Filters(is_passive=True),
            exclusions=Exclusions(),
            applied=[Understood(key="is_passive", label="Index funds only")],
            sort=Sort.cost,
            summary="Cheap FTSE 100 trackers, cheapest first.",
        )


def _llm_client(fake, llm):
    from fundfinder.routes.api import get_llm

    app = create_app()
    app.dependency_overrides[get_search] = lambda: fake
    app.dependency_overrides[get_llm] = lambda: llm
    return TestClient(app)


def test_search_llm_intent(fake):
    async def facets():
        return {
            "asset_classes": ["Equity"],
            "ia_sectors": [],
            "tracked_indexes": ["FTSE 100 Index"],
        }

    fake.facets = facets
    llm = FakeLlm()
    with _llm_client(fake, llm) as c:
        body = c.get("/search", params={"q": "cheap well known Uk", "intent": "llm"}).json()
        assert body["interpretation"]["source"] == "llm"
        assert body["interpretation"]["summary"].startswith("Cheap FTSE 100")
        assert fake.calls[0][1] == "UK large companies index fund tracking the FTSE 100"
        assert fake.calls[0][2]["filters"].is_passive is True
        assert body["sort"] == "cost"  # the LLM's order, since sort=auto
        assert [h["id"] for h in body["results"]] == ["F3", "F2", "F4"]

        # An explicit sort and the user's own filters still win.
        body = c.get(
            "/search",
            params={"q": "cheap well known Uk", "intent": "llm", "sort": "relevance",
                    "is_passive": "false"},
        ).json()  # fmt: skip
        assert body["sort"] == "relevance"
        assert fake.calls[1][2]["filters"].is_passive is False
        assert body["interpretation"]["applied"] == []


def test_search_llm_failure_falls_back_to_rules(fake):
    async def facets():
        return {}

    fake.facets = facets
    with _llm_client(fake, FakeLlm(fail=True)) as c:
        body = c.get("/search", params={"q": "index funds under 0.2%", "intent": "llm"}).json()
    assert body["interpretation"]["source"] == "rules"
    assert "unavailable" in body["interpretation"]["notice"]
    assert fake.calls[0][2]["filters"].ocf_max == 0.2


def test_search_repeats_are_served_from_cache(client, fake):
    first = client.get("/search", params={"q": "uk dividend"})
    second = client.get("/search", params={"q": "uk dividend"})
    assert second.json()["results"] == first.json()["results"]
    assert len(fake.calls) == 1  # embedded once
    assert "s-maxage" in second.headers["cache-control"]

    # Anything that changes the results is a different entry.
    client.get("/search", params={"q": "uk dividend", "ocf_max": 0.5})
    client.get("/search", params={"q": "uk dividend", "sort": "cost"})
    client.get("/search", params={"q": "uk dividend", "ignore": ["any_of"]})
    assert len(fake.calls) == 4


def test_search_errors_are_not_cached(client, fake):
    fake.fail = "embedding rate limit exceeded"
    assert client.get("/search", params={"q": "uk dividend"}).status_code == 429
    fake.fail = None
    assert client.get("/search", params={"q": "uk dividend"}).status_code == 200
    assert len(fake.calls) == 1


def test_search_llm_results_are_never_cached(fake):
    async def facets():
        return {"asset_classes": [], "ia_sectors": [], "tracked_indexes": []}

    fake.facets = facets
    llm = FakeLlm()
    with _llm_client(fake, llm) as c:
        for _ in range(2):
            r = c.get("/search", params={"q": "cheap well known Uk", "intent": "llm"})
            assert r.headers["cache-control"] == "private, no-store"
    assert len(fake.calls) == 2


def test_search_llm_not_configured(client):
    r = client.get("/search", params={"q": "x", "intent": "llm"})
    assert r.status_code == 503
    assert "ANTHROPIC_API_KEY" in r.json()["detail"]


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


@pytest.mark.parametrize(
    ("sort", "expected"),
    [(None, ["F2", "F3", "F4"]), ("cost", ["F3", "F2", "F4"]), ("cost_desc", ["F2", "F4", "F3"])],
)
def test_similar_sort(client, fake, sort, expected):
    hits = [make_hit("F2", 0.9), make_hit("F3", 0.7, ocf=0.1), make_hit("F4", 0.6)]

    async def similar(fund_id, mode, **kw):
        return hits

    fake.similar = similar
    params = {"sort": sort} if sort else {}
    body = client.get("/funds/F1/similar", params=params).json()
    assert body["sort"] == (sort or "relevance")
    assert [h["id"] for h in body["results"]] == expected


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


def test_meta(client, fake):
    async def facets():
        return {"ia_sectors": ["Global"], "asset_classes": ["Equity"]}

    fake.facets = facets
    body = client.get("/meta").json()
    assert body["ia_sectors"] == ["Global"]
    assert len(body["exposure_layout"]["sectors"]) == 11
    assert body["defaults"]["candidates_per_result"] == 20


def test_web_mount_serves_spa_routes(tmp_path):
    (tmp_path / "assets").mkdir()
    (tmp_path / "assets" / "app.js").write_text("console.log(1)")
    (tmp_path / "index.html").write_text("<div id=root></div>")
    (tmp_path / "favicon.svg").write_text("<svg/>")
    app = create_app(web_dist=tmp_path)
    with TestClient(app) as c:
        assert c.get("/").text == "<div id=root></div>"
        assert c.get("/fund/F0001").text == "<div id=root></div>"
        assert c.get("/assets/app.js").status_code == 200


def test_web_mount_skipped_without_build(tmp_path):
    from fundfinder.routes.web import mount_web

    assert mount_web(create_app(web_dist=None), tmp_path) is False


def test_clusters(client, fake):
    async def clusters():
        return {"trk_sp500": [{"id": "F1", "name": "A"}, {"id": "F2", "name": "B"}]}

    fake.clusters = clusters
    assert client.get("/clusters").json() == {
        "trk_sp500": [{"id": "F1", "name": "A"}, {"id": "F2", "name": "B"}]
    }


def _limited(client, **capacities):
    from fundfinder.ratelimit import Limits, RateLimiter

    limits = Limits.unlimited()
    for name, capacity in capacities.items():
        setattr(limits, name, RateLimiter(capacity))
    client.app.state.limits = limits


def test_search_rate_limited_per_client(client):
    _limited(client, search=2)
    assert client.get("/search", params={"q": "x"}).status_code == 200
    assert client.get("/funds/F1/similar").status_code == 200
    r = client.get("/search", params={"q": "x"})
    assert r.status_code == 429
    assert r.headers["retry-after"] == "30"
    assert client.get("/funds/F1/similar").status_code == 429
    assert client.get("/funds/F1").status_code == 200  # no embedding, not limited


def test_llm_rate_limited_per_client_and_globally(fake):
    async def facets():
        return {}

    fake.facets = facets
    llm = FakeLlm()
    with _llm_client(fake, llm) as c:
        _limited(c, llm=1)
        assert c.get("/search", params={"q": "a", "intent": "llm"}).status_code == 200
        r = c.get("/search", params={"q": "b", "intent": "llm"})
        assert r.status_code == 429 and "AI" in r.json()["detail"]
        assert c.get("/search", params={"q": "c"}).status_code == 200  # rules still work

        _limited(c, llm_budget=1)
        assert c.get("/search", params={"q": "d", "intent": "llm"}).status_code == 200
        r = c.get("/search", params={"q": "e", "intent": "llm"})
        assert r.status_code == 429 and "budget" in r.json()["detail"]
    assert llm.calls == ["a", "d"]


def test_limits_come_from_settings(client):
    s, limits = client.app.state.settings, client.app.state.limits
    assert limits.search.capacity == s.search_rate_per_min
    assert limits.llm.capacity == s.llm_rate_per_min
    assert limits.llm_budget.capacity == s.llm_daily_budget
    assert limits.llm_budget.rate == s.llm_daily_budget / 86400


@pytest.mark.parametrize("fund_id", ["F%7B%7D", "a.b", "x" * 65, "F1%24ne"])
def test_fund_id_format_validated(client, fake, fund_id):
    assert client.get(f"/funds/{fund_id}").status_code == 422
    assert client.get(f"/funds/{fund_id}/similar").status_code == 422
    assert fake.calls == []


def test_ignore_list_is_bounded(client):
    params = {"q": "x", "ignore": [f"k{i}" for i in range(21)]}
    assert client.get("/search", params=params).status_code == 422


def test_security_headers(client):
    r = client.get("/funds/F1")
    assert r.headers["x-content-type-options"] == "nosniff"
    assert r.headers["x-frame-options"] == "DENY"
    assert r.headers["referrer-policy"] == "strict-origin-when-cross-origin"
    csp = r.headers["content-security-policy"]
    assert "frame-ancestors 'none'" in csp and "script-src" not in csp
    # Errors carry them too.
    assert client.get("/funds/MISSING").headers["x-frame-options"] == "DENY"


def test_docs_csp_allows_swagger_ui(client):
    r = client.get("/docs")
    assert r.status_code == 200
    csp = r.headers["content-security-policy"]
    assert "https://cdn.jsdelivr.net" in csp and "frame-ancestors 'none'" in csp
