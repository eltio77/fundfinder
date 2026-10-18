import pytest

from fundfinder.search import Filters
from fundfinder.understanding import NEUTRAL_TEXT, Exclusions, interpret, plan


def keys(q: str) -> list[str]:
    return [a.key for a in interpret(q)[3]]


@pytest.mark.parametrize(
    ("q", "ocf_max", "text"),
    [
        ("index funds under 0.2% a year", 0.2, "index funds"),
        ("global trackers with fees below 15bps", 0.15, "global trackers"),
        ("OCF under 0.25 world equity", 0.25, "world equity"),
        ("japan funds costing less than 0.5 percent", 0.5, "japan funds"),
        ("UK bonds no more than 0.3% p.a.", 0.3, "UK bonds"),
        ("funds under 0.1% in S&P", 0.1, "funds in S&P"),
        ("trackers under 0.1% in the S&P 500", 0.1, "trackers in the S&P 500"),
        ("under 0.2% in a FTSE 100 tracker", 0.2, "a FTSE 100 tracker"),
    ],
)
def test_cost_cap(q, ocf_max, text):
    got_text, filters, _, _ = interpret(q)
    assert filters.ocf_max == pytest.approx(ocf_max)
    assert got_text == text


@pytest.mark.parametrize(
    "q",
    [
        "under 50% in shares",  # an allocation, not a cost
        "less than 20% of the fund in bonds",
        "under 1% in tech",
        "under 2% in the US",
        "no more than 0.5% in cash",
        "global equity under 0.2",  # unitless with no cost word
        "FTSE 100 tracker",
    ],
)
def test_no_cost_cap(q):
    assert interpret(q)[1].ocf_max is None


@pytest.mark.parametrize(
    ("q", "passive"),
    [
        ("S&P 500 index fund", True),
        ("cheap global tracker", True),
        ("passive bond fund", True),
        ("a cheap fund that follows the US stock market", True),
        ("actively managed UK smaller companies", False),
        ("stock picking in Japan", False),
        ("not an index fund", False),
        ("index-linked gilts", None),  # "index-linked" is a bond type
        ("active fund or tracker", None),  # both: leave it
        ("Japanese companies that are reforming", None),
    ],
)
def test_fund_type(q, passive):
    assert interpret(q)[1].is_passive is passive


@pytest.mark.parametrize(
    ("q", "asset"),
    [
        ("low-risk UK government bonds", "Fixed Income"),
        ("gilts", "Fixed Income"),
        ("global equity income", "Equity"),
        ("gold mining shares", "Equity"),
        ("UK commercial property", "Property"),
        ("balanced multi-asset fund", "Mixed Assets"),
        ("a fund with 60% in shares and the rest in bonds", "Mixed Assets"),
        ("money market fund", "Money Market"),
        ("shares and bonds", None),  # two named, not mixed: leave it
        ("steady income from big UK companies", None),
    ],
)
def test_asset_class(q, asset):
    assert interpret(q)[1].asset_class == asset


@pytest.mark.parametrize(
    ("q", "text", "expected"),
    [
        ("global equity but not tech", "global equity",
         ["asset_class", "not_sector:Information Technology"]),
        ("global funds without tech or banks", "global funds",
         ["not_sector:Information Technology", "not_sector:Financials"]),
        ("excluding tech, banks or energy", NEUTRAL_TEXT,
         ["not_sector:Information Technology", "not_sector:Financials", "not_sector:Energy"]),
        ("european funds ex UK", "european funds", ["not_region:UK"]),
        ("non-UK equity income", "equity income", ["asset_class", "not_region:UK"]),
        ("healthcare but not in the US", "healthcare", ["not_region:North America"]),
        ("emerging markets excluding China", "emerging markets", ["not_region:Emerging Asia"]),
        ("income, no bonds or property", "income",
         ["not_asset:Fixed Income", "not_asset:Property"]),
        # A comma without a closing conjunction starts a new clause.
        ("not an index fund, japan", "japan", ["is_passive"]),
        ("not too risky", "not too risky", []),
    ],
)  # fmt: skip
def test_negations(q, text, expected):
    got_text, _, _, applied = interpret(q)
    assert got_text == text
    assert [a.key for a in applied] == expected


def test_constraint_only_query_embeds_neutral_text():
    text, filters, _, _ = interpret("under 0.1%")
    assert text == NEUTRAL_TEXT and filters.ocf_max == pytest.approx(0.1)


def test_plain_queries_are_untouched():
    for q in ["Japanese companies that are reforming", "artificial intelligence and chips"]:
        text, filters, exclusions, applied = interpret(q)
        assert text == q and applied == [] and not exclusions
        assert filters == Filters()


def test_exclusions_mean_mainly():
    ex = Exclusions(sectors=["Information Technology"], regions=["UK"])
    assert ex.excludes({"Information Technology": 0.7}, {})  # a tech fund
    assert not ex.excludes({"Information Technology": 0.39}, {})  # a global fund
    assert ex.excludes({}, {"UK": 0.9})
    em = Exclusions(regions=["Emerging Asia+Emerging EMEA+Latin America"])
    assert em.excludes({}, {"Emerging Asia": 0.3, "Emerging EMEA": 0.15, "Latin America": 0.1})


def test_tracked_index_post_filter():
    ex = Exclusions(tracked_indexes=["FTSE 100 Index"])
    assert not ex.excludes({}, {}, "FTSE 100 Index")
    assert ex.excludes({}, {}, "FTSE All-Share Index")
    assert ex.excludes({}, {}, None)  # active funds track nothing


def test_plan_explicit_filters_win_and_ignore_drops():
    p = plan("index funds under 0.2%, no bonds", Filters(is_passive=False))
    assert p.filters.is_passive is False  # user's own filter
    assert "is_passive" not in [a.key for a in p.applied]
    assert p.filters.ocf_max == pytest.approx(0.2)
    assert p.filters.asset_class_nin == ["Fixed Income"]

    p = plan(
        "index funds under 0.2% not tech",
        Filters(),
        {"ocf_max", "not_sector:Information Technology"},
    )
    assert p.filters.ocf_max is None and p.filters.is_passive is True
    assert not p.exclusions
    assert [a.key for a in p.applied] == ["is_passive"]
