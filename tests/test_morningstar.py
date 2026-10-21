import pytest

from fundfinder.data.morningstar import (
    Listing,
    MorningstarSource,
    SkipFund,
    parse_list,
    spread,
    to_fund,
)
from fundfinder.documents import to_document

LIST_XML = b"""<Securities TotalNumberOfPages="29">
<Security><LegalStructure>Open Ended Investment Company</LegalStructure><SEDOL>B2PB2C7</SEDOL>
  <Name>7IM AAP Adventurous C Acc</Name>
  <IMASectorName>Flexible Investment</IMASectorName></Security>
<Security><LegalStructure>SICAV</LegalStructure><SEDOL>AAAAAAA</SEDOL>
  <Name>Not an OEIC</Name><IMASectorName>Global</IMASectorName></Security>
<Security><LegalStructure>Open Ended Investment Company</LegalStructure><SEDOL>BBBBBBB</SEDOL>
  <Name>No IA sector</Name><IMASectorName></IMASectorName></Security>
<Security><LegalStructure>Open Ended Investment Company</LegalStructure><SEDOL></SEDOL>
  <Name>No SEDOL</Name><IMASectorName>Global</IMASectorName></Security>
</Securities>"""


def _breakdown(values: dict[str, float], **extra) -> list[dict]:
    net = {"SalePosition": "N", **extra, "BreakdownValues": [
        {"Type": k, "Value": v} for k, v in values.items()
    ]}  # fmt: skip
    short = {**net, "SalePosition": "S", "BreakdownValues": [{"Type": "1", "Value": 99}]}
    return [short, net]


def detail(**overrides) -> dict:
    portfolio = {
        "AssetAllocations": [
            *_breakdown({"1": 60, "3": 30, "7": 5, "8": 5}, Type="MorningStarDefault"),
            *_breakdown({"6": 5}, Type="MorningstarUK6"),
        ],
        "GlobalBondSectorBreakdownLevel1": _breakdown({"10": 75, "30": 25, "50": 10}),
        "GlobalStockSectorBreakdown": _breakdown({"311": 50, "103": 50}),
        "RegionalExposure": _breakdown({"1": 50, "4": 50, "15": 100}),
        "CountryExposure": _breakdown({"GBR": 100}, Type="Bond"),
        "PortfolioHoldings": [
            {"SecurityName": "Small", "Weighting": 1.5},
            {"SecurityName": "Big", "Weighting": 9.0},
        ],
    }
    base = {
        "FundId": "FS1",
        "Name": "Example Global Index C Acc",
        "IMASector": {"Name": "Mixed Investment 40-85% Shares"},
        "CategoryBroadAssetClass": {"Name": "Allocation"},
        "OngoingCharge": 0.25,
        "InvestmentStrategy": "Tracks the index.",
        "ProviderCompany": {"Name": "Example"},
        "FundBenchmark": [{"Name": "MSCI World NR GBP"}],
        "Portfolios": [portfolio],
    }
    return {**base, **overrides}


def test_parse_list_keeps_oeics_with_sedol_and_sector():
    listings, pages = parse_list(LIST_XML)
    assert pages == 29
    assert listings == [Listing("B2PB2C7", "7IM AAP Adventurous C Acc", "Flexible Investment")]


def test_parse_list_rejects_service_errors():
    with pytest.raises(ValueError, match="No securities found"):
        parse_list(b"<WebServiceException><StatusMessage>No securities found</StatusMessage>"
                   b"</WebServiceException>")  # fmt: skip


def test_spread_round_robins_sectors():
    items = [Listing(f"A{i}", "", "A") for i in range(3)] + [Listing("B0", "", "B")]
    out = spread(items, seed=1)
    assert sorted(out, key=lambda li: li.sedol) == sorted(items, key=lambda li: li.sedol)
    assert {out[0].ia_sector, out[1].ia_sector} == {"A", "B"}


def test_to_fund_maps_weights_onto_whole_portfolio():
    fund = to_fund(detail(), "SEDOL01")
    assert fund.id == "SEDOL01"
    assert fund.asset_class == "Mixed Assets"
    assert fund.asset_class_weights["Equity"] == 0.6
    assert fund.asset_class_weights["Government Bonds"] == 0.225
    assert fund.asset_class_weights["Corporate Bonds"] == 0.075
    assert fund.asset_class_weights["Property"] == 0.05
    assert fund.asset_class_weights["Cash"] == 0.05
    assert "Alternatives" not in fund.asset_class_weights  # "other" was all property
    # Equity sectors are scaled to the equity share; short positions are ignored.
    assert fund.sector_weights == {"Financials": 0.3, "Information Technology": 0.3}
    # Equity regions (60%) and bond countries (30%), rescaled to 1.
    assert fund.region_weights == {"North America": 0.3333, "UK": 0.6667}
    assert [h.name for h in fund.top_holdings] == ["Big", "Small"]
    assert fund.top_holdings[0].weight == 0.09
    assert fund.is_passive and fund.tracked_index == "MSCI World NR GBP"
    assert len(to_document(fund)["exposure_vector"]) > 0


@pytest.mark.parametrize(
    ("name", "passive"),
    [
        ("HSBC FTSE 100 Index C Acc", True),
        ("abrdn UK All Share Tracker B Acc", True),
        ("iShares Core MSCI EM IMI ETF USD Dist", True),
        ("Royal London Index Linked M Inc", False),
        ("Fidelity Index-Linked Bond I Inc", False),
        ("Invesco Asian UK Z Inc", False),
    ],
)
def test_passive_read_from_name(name, passive):
    assert to_fund(detail(Name=name), "S").is_passive is passive


def test_peer_group_benchmark_is_not_a_tracked_index():
    fund = to_fund(detail(FundBenchmark=[{"Name": "IA Global"}]), "S")
    assert fund.is_passive and fund.tracked_index is None


def test_ia_sector_overrides_broad_asset_class():
    fund = to_fund(detail(IMASector={"Name": "Standard Money Market"}), "S")
    assert fund.asset_class == "Money Market"


@pytest.mark.parametrize("missing", ["OngoingCharge", "InvestmentStrategy", "Portfolios"])
def test_missing_essentials_skip_the_fund(missing):
    with pytest.raises(SkipFund):
        to_fund(detail(**{missing: None}), "S")


def test_fetch_keeps_one_share_class_per_fund(monkeypatch):
    listings = [Listing("ACC", "", "Global"), Listing("INC", "", "Global"),
                Listing("OTHER", "", "Japan")]  # fmt: skip
    details = {"ACC": detail(FundId="F1"), "INC": detail(FundId="F1"),
               "OTHER": detail(FundId="F2")}  # fmt: skip
    source = MorningstarSource(limit=5)
    monkeypatch.setattr(source, "listings", lambda: listings)
    monkeypatch.setattr(source, "_detail", lambda sedol: details[sedol])
    funds = source.fetch()
    assert len(funds) == 2
    assert len({f.id for f in funds} & {"ACC", "INC"}) == 1
