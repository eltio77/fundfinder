import json
import time

import pytest

from fundfinder.search import Filters
from fundfinder.understanding import NEUTRAL_TEXT, Exclusions, alternatives, interpret, plan


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
        # Below 1%, a sector or region after the cap is what the fund invests in.
        ("under 0.2% in tech or healthcare", 0.2, "tech or healthcare"),
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
        "fees under 101%",  # over 100% is never an annual charge
        "fees under " + "9" * 400 + "%",  # float() of this is inf
    ],
)
def test_no_cost_cap(q):
    filters = interpret(q)[1]
    assert filters.ocf_max is None
    json.dumps(filters.model_dump(), allow_nan=False)  # the API echoes filters as JSON


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
        ("not active", True),
        ("not actively managed funds", True),
        ("not index funds, not active", None),  # contradicts itself: apply neither
        ("index-linked gilts", None),  # "index-linked" is a bond type
        ("not index-linked gilts", None),  # ...so negating it says nothing about trackers
        ("bonds but not index linked", None),
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
        # One alternative among others isn't "only" that class...
        ("income from bonds or dividends", None),
        ("dividends or bonds", None),
        ("property or infrastructure funds", None),
        # ...but alternatives within the class, or a class word qualifying both, are.
        ("bonds or gilts", "Fixed Income"),
        ("UK gilts or corporate bonds", "Fixed Income"),
        ("UK or European equity", "Equity"),
        ("money market or cash funds", "Money Market"),
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
        ("neither tech nor banks, UK", "UK",
         ["not_sector:Information Technology", "not_sector:Financials"]),
        ("not too risky", "not too risky", []),
        ("gold mining shares not a commodities", "gold mining shares",
         ["asset_class", "not_ia_sector:Commodities and Natural Resources"]),
        ("energy, not natural resources funds", "energy",
         ["not_ia_sector:Commodities and Natural Resources"]),
        # Other ways of saying "not".
        ("anything but bonds", NEUTRAL_TEXT, ["not_asset:Fixed Income"]),
        ("other than tech", NEUTRAL_TEXT, ["not_sector:Information Technology"]),
        ("apart from the US", NEUTRAL_TEXT, ["not_region:North America"]),
        ("neither tech nor banks", NEUTRAL_TEXT,
         ["not_sector:Information Technology", "not_sector:Financials"]),
        ("global equity, nothing with bonds", "global equity",
         ["asset_class", "not_asset:Fixed Income"]),
        ("doesn't invest in tech or energy", NEUTRAL_TEXT,
         ["not_sector:Information Technology", "not_sector:Energy"]),
        ("global funds not heavy in US or tech", "global funds",
         ["not_sector:Information Technology", "not_region:North America"]),
        ("not active funds", NEUTRAL_TEXT, ["is_passive"]),
        # Bond sub-types exclude their sector, not every bond fund.
        ("safe income but not gilts", "safe income", ["not_ia_sector:UK Gilts"]),
        ("not UK gilts", NEUTRAL_TEXT, ["not_ia_sector:UK Gilts"]),
        ("not corporate bonds", NEUTRAL_TEXT, ["not_ia_sector:£ Corporate Bond"]),
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


def test_negated_ia_sector_is_a_pre_filter():
    sector = "Commodities and Natural Resources"
    p = plan("gold mining shares not commodities", Filters())
    assert p.filters.ia_sector_nin == [sector]
    assert p.applied[-1].label == f"No {sector} funds"
    # Removing the chip, or choosing that sector yourself, drops the exclusion.
    assert (
        plan(
            "gold miners not commodities", Filters(), {f"not_ia_sector:{sector}"}
        ).filters.ia_sector_nin
        is None
    )
    assert (
        plan("gold miners not commodities", Filters(ia_sector=sector)).filters.ia_sector_nin is None
    )


@pytest.mark.parametrize(
    "q",
    [
        "not" + " " * 1997,
        "not tech" + " or tech" * 249,
        "not tech" + " , " * 664 + "x",
        "fees of " * 250,
        "tracks the " + "a " * 994,
        "no us " * 333,
        "1 % in " * 285,
    ],
)
def test_long_adversarial_queries_stay_fast(q):
    # Guards against catastrophic regex backtracking at the API's 2000-char limit.
    # These take ~1-4 ms today; the bound is loose so slow CI doesn't flake.
    started = time.perf_counter()
    interpret(q[:2000])
    assert time.perf_counter() - started < 0.5


@pytest.mark.parametrize(
    ("text", "expected"),
    [
        ("tech or healthcare", [("tech", "tech"), ("healthcare", "healthcare")]),
        ("UK or European equity", [("UK", "UK equity"), ("European", "European equity")]),
        ("income from bonds or dividends",
         [("bonds", "income from bonds"), ("dividends", "income from dividends")]),
        ("index funds tracking the S&P 500 or FTSE 100",
         [("S&P 500", "index funds tracking the S&P 500"),
          ("FTSE 100", "index funds tracking the FTSE 100")]),
        ("tech, healthcare or energy",
         [("tech", "tech"), ("healthcare", "healthcare"), ("energy", "energy")]),
        ("either gold or energy", [("gold", "gold"), ("energy", "energy")]),
        ("money market or cash funds",
         [("money market", "money market funds"), ("cash", "cash funds")]),
        ("equity or fixed income funds",
         [("equity", "equity funds"), ("fixed income", "fixed income funds")]),
        ("income funds or growth funds",
         [("income funds", "income funds"), ("growth funds", "growth funds")]),
        ("UK or Europe, lowest cost first",
         [("UK", "UK, lowest cost first"), ("Europe", "Europe, lowest cost first")]),
        ("global equity", []),
        ("tech or tech", []),
        ("tech or", []),
    ],
)  # fmt: skip
def test_alternatives(text, expected):
    assert [(a.name, a.text) for a in alternatives(text)] == expected


def test_alternatives_cap_list_length():
    assert len(alternatives("a, b, c, d, e or f")) == 4
