from fundfinder.profile import build_profile
from tests.factories import make_fund


def test_profile_contains_core_fields():
    text = build_profile(make_fund())
    assert text.startswith("Kestrel FTSE 100 Index Fund.")
    assert "The fund aims to track the FTSE 100 Index." in text
    assert "IA sector: UK All Companies. Asset class: Equity." in text
    assert "Passive index fund tracking the FTSE 100 Index." in text
    assert "Top holdings: Shell, AstraZeneca." in text


def test_profile_sectors_ranked_top_three():
    fund = make_fund(
        sector_weights={"Energy": 0.1, "Financials": 0.4, "Health Care": 0.3, "Utilities": 0.2}
    )
    assert "Main sectors: Financials 40%, Health Care 30%, Utilities 20%." in build_profile(fund)


def test_profile_region_split_drops_small_regions():
    text = build_profile(make_fund())
    assert "Region split: UK 97%." in text
    assert "North America" not in text


def test_profile_active_fund():
    text = build_profile(make_fund(is_passive=False, tracked_index=None))
    assert "Actively managed." in text
    assert "Passive" not in text


def test_profile_bond_fund_has_no_sector_line():
    text = build_profile(make_fund(sector_weights={}))
    assert "Main sectors" not in text


def test_profile_is_deterministic_on_ties():
    fund = make_fund(region_weights={"UK": 0.5, "Japan": 0.5})
    assert build_profile(fund) == build_profile(fund)
    assert "Region split: Japan 50%, UK 50%." in build_profile(fund)
