"""Deterministic synthetic UK fund universe.

Not real data: providers are fictional, weights are made up. Index names and
listed company names are used only for realism.

Deliberate structure for evaluation (via `cluster_id`):
  trk_*      several providers tracking the same index (near-identical funds)
  act_*      near-duplicate active funds (shared process, holdings, wording)
  outlier_*  one-off funds with no true neighbours
Everything else is background (cluster_id=None), perturbed around archetypes.
"""

import random
import re
from dataclasses import dataclass, field

from fundfinder.models import Fund, Holding
from fundfinder.taxonomy import GICS_SECTORS, REGIONS

DEFAULT_SEED = 42
DEFAULT_N = 300

# Log-normal sigma for weight noise. Trackers of one index differ only through
# reporting dates and classification; near-dupes share a centroid; background
# funds scatter widely around their archetype.
TRACKER_NOISE = 0.06
DUPE_CENTROID_NOISE = 0.25
DUPE_MEMBER_NOISE = 0.2
BACKGROUND_NOISE = 0.35

PROVIDERS = (
    "Aldwych", "Thamesbridge", "Northgate", "Kestrel", "Halden", "Marlowe",
    "Pennine", "Ravensworth", "Severn", "Clarendon", "Wexford", "Ashcombe",
    "Calder", "Brightwater", "Fenwick", "Lowther", "Saltmarsh", "Holloway",
)  # fmt: skip

HORIZONS = (
    "any five-year period",
    "rolling five-year periods",
    "the long term (at least five years)",
    "any seven-year period",
)

# ---------------------------------------------------------------- holdings pools

UK_LARGE = (
    "Shell", "AstraZeneca", "HSBC Holdings", "Unilever", "BP", "RELX", "GSK",
    "British American Tobacco", "Diageo", "Rio Tinto", "London Stock Exchange Group",
    "National Grid", "Glencore", "Barclays", "Lloyds Banking Group", "BAE Systems",
    "Rolls-Royce Holdings", "Compass Group", "Reckitt Benckiser", "Tesco",
    "Legal & General", "Aviva", "Imperial Brands", "SSE", "Prudential", "NatWest Group",
    "Experian", "3i Group",
)  # fmt: skip
UK_INCOME_EXTRA = ("Phoenix Group", "M&G", "Vodafone", "Persimmon", "Taylor Wimpey")
UK_SMALL = (
    "Bloomsbury Publishing", "Volution Group", "Treatt", "Gamma Communications",
    "Craneware", "Judges Scientific", "Bytes Technology", "Alpha Group", "XPS Pensions",
    "CVS Group", "FD Technologies", "Hollywood Bowl", "Cranswick", "Chemring",
    "Morgan Sindall", "Telecom Plus", "Breedon Group", "Ricardo", "Marshalls", "Dunelm",
)  # fmt: skip
US = (
    "Apple", "Microsoft", "Nvidia", "Amazon", "Alphabet", "Meta Platforms", "Broadcom",
    "Tesla", "Berkshire Hathaway", "JPMorgan Chase", "Eli Lilly", "Visa", "UnitedHealth",
    "Exxon Mobil", "Mastercard", "Procter & Gamble", "Johnson & Johnson", "Costco",
    "Home Depot", "Netflix", "Oracle", "AbbVie", "Chevron", "Bank of America",
)  # fmt: skip
EUROPE = (
    "ASML", "Novo Nordisk", "SAP", "Nestle", "LVMH", "Roche", "Novartis", "TotalEnergies",
    "Siemens", "Schneider Electric", "Allianz", "Sanofi", "L'Oreal", "Airbus", "Iberdrola",
    "BNP Paribas", "Banco Santander", "Deutsche Telekom", "Zurich Insurance", "Hermes",
    "UBS", "Inditex", "ABB", "Safran",
)  # fmt: skip
JAPAN = (
    "Toyota Motor", "Sony Group", "Mitsubishi UFJ", "Hitachi", "Keyence", "Tokyo Electron",
    "Recruit Holdings", "Shin-Etsu Chemical", "Sumitomo Mitsui", "Nintendo",
    "Fast Retailing", "Daiichi Sankyo", "Tokio Marine", "Mitsubishi Corp", "Itochu", "KDDI",
    "Hoya", "Fanuc", "Takeda", "Honda Motor",
)  # fmt: skip
ASIA_EM = (
    "TSMC", "Tencent", "Samsung Electronics", "Alibaba", "HDFC Bank", "Reliance Industries",
    "AIA Group", "Infosys", "ICICI Bank", "Meituan", "BHP Group", "Commonwealth Bank",
    "DBS Group", "SK Hynix", "PDD Holdings", "Xiaomi", "MediaTek", "Bharti Airtel",
    "Naspers", "Itau Unibanco", "Petrobras", "Grupo Mexico", "Al Rajhi Bank",
)  # fmt: skip
TECH = (
    "Microsoft", "Nvidia", "Apple", "Broadcom", "ASML", "TSMC", "Alphabet",
    "Meta Platforms", "Amazon", "Salesforce", "ServiceNow", "Adobe", "AMD", "Palantir",
    "CrowdStrike", "Shopify", "Oracle", "Synopsys", "Cadence Design", "Arista Networks",
    "Datadog", "SAP", "Intuit", "Snowflake",
)  # fmt: skip
GILTS = (
    "UK Treasury 4.25% 2032", "UK Treasury 0.5% 2061", "UK Treasury 4.5% 2034",
    "UK Treasury 1.25% 2041", "UK Treasury 3.75% 2038", "UK Treasury 4.125% 2029",
    "UK Treasury 0.875% 2033", "UK Treasury 4% 2060", "UK Treasury 1.5% 2047",
    "UK Treasury 3.5% 2045", "UK Treasury 4.75% 2030", "UK Treasury 0.625% 2035",
)  # fmt: skip
GLOBAL_GOVT = (
    "US Treasury 4.0% 2034", "US Treasury 4.125% 2032", "Bund 2.5% 2033",
    "Japan Govt 0.8% 2033", "France OAT 3% 2034", "Italy BTP 4% 2031",
    "US Treasury 2.875% 2028", "Canada 3.25% 2033", "Spain 3.15% 2033",
    "Australia 4.25% 2034", "China Govt 2.6% 2033", "Japan Govt 1.1% 2043",
)  # fmt: skip
CORP_BONDS = (
    "HSBC 6.8% 2031", "Barclays 7.09% 2029", "Aviva 6.875% 2058", "Lloyds 5.25% 2029",
    "Vodafone 5.9% 2032", "Legal & General 5.625% 2049", "AT&T 4.375% 2029",
    "NatWest 5.125% 2030", "Orsted 5.125% 2034", "Tesco 6% 2029", "National Grid 4.1% 2030",
    "BNP Paribas 3.375% 2030", "Volkswagen 4.25% 2028", "EDF 6% 2114",
    "Heathrow Funding 6.45% 2031", "Annington 3.685% 2034",
)  # fmt: skip
PROPERTY = (
    "Segro", "Landsec", "British Land", "Prologis", "Equinix", "Welltower", "Unite Group",
    "LondonMetric", "Vonovia", "Tritax Big Box", "Big Yellow", "Derwent London",
    "Goodman Group", "Digital Realty", "Public Storage",
)  # fmt: skip
RESOURCES = (
    "BHP Group", "Rio Tinto", "Glencore", "Shell", "Exxon Mobil", "Chevron", "TotalEnergies",
    "Freeport-McMoRan", "Anglo American", "Vale", "Nutrien", "Newmont", "ConocoPhillips",
)  # fmt: skip
MONEY_MARKET = (
    "UK Treasury Bill Dec 2026", "UK Treasury Bill Jan 2027", "UK Treasury Bill Mar 2027",
    "Barclays Bank CD", "Lloyds Bank CD", "NatWest Reverse Repo", "BNP Paribas CD",
    "Santander UK CP", "Toronto-Dominion CD", "Nordea CP", "Rabobank CD", "DBS CD",
)  # fmt: skip
ABS_RETURN = (
    "UK Treasury Bill Feb 2027", "US Treasury 2y Future (short)",
    "FTSE 100 Index Future (short)", "EUR/GBP Forward", "UK Treasury 4.125% 2029",
    "S&P 500 Index Future", "Microsoft", "Shell", "Japan Govt 0.8% 2033", "USD/JPY Option",
    "Euro Stoxx 50 Future (short)", "Cash deposits",
)  # fmt: skip
MIXED = US[:8] + UK_LARGE[:6] + GILTS[:4] + CORP_BONDS[:4] + GLOBAL_GOVT[:3]

# ------------------------------------------------------------------- archetypes

EQUITY_STYLES = (
    "The manager {focuses on|favours} {high-quality|quality} businesses with strong "
    "balance sheets.",
    "The process combines bottom-up stock selection with {macroeconomic|top-down} views.",
    "Sustainability factors are integrated into the investment process.",
    "The portfolio is {concentrated|focused}, typically holding {30 to 50|40 to 60} stocks.",
    "The fund follows a {disciplined|systematic} quantitative approach.",
    "The managers take a {contrarian|valuation-driven} approach.",
)
BOND_STYLES = (
    "The manager actively manages interest rate and credit risk.",
    "The fund {focuses on|emphasises} investment grade issuers.",
    "Currency exposure is hedged back to sterling.",
    "Duration is kept close to that of the benchmark.",
)
MIXED_STYLES = (
    "Asset allocation is reviewed {regularly|monthly} by an investment committee.",
    "The fund invests via a mix of direct holdings and collective investment schemes.",
    "Risk is managed to stay within a defined volatility band.",
)
GROWTH_GOALS = (
    "achieve capital growth",
    "{deliver|generate} long-term capital growth",
    "{provide|achieve} a total return (capital growth plus income)",
)
INCOME_GOALS = (
    "provide an income {yield above|higher than} its benchmark together with capital growth",
    "{deliver|provide} a {rising|growing} income and some capital growth",
)
BOND_GOALS = (
    "{provide|generate} income and preserve capital",
    "maximise total return through income and capital growth",
)
EQUITY_ASSETS = {"Equity": 0.98, "Cash": 0.02}


@dataclass(frozen=True)
class Archetype:
    key: str
    ia_sector: str
    asset_class: str
    universe: str
    sectors: dict[str, float]  # distribution within the GICS-classifiable share
    regions: dict[str, float]
    assets: dict[str, float]
    holdings: tuple[str, ...]
    stems: tuple[str, ...]
    goals: tuple[str, ...] = GROWTH_GOALS
    styles: tuple[str, ...] = EQUITY_STYLES
    ocf: tuple[float, float] = (0.55, 1.05)
    top_weight: tuple[float, float] = (0.03, 0.07)
    indices: tuple[str, ...] = ()
    weight: float = 1.0  # relative share of the background universe


ARCHETYPES: dict[str, Archetype] = {
    a.key: a
    for a in [
        Archetype(
            "uk_large", "UK All Companies", "Equity",
            "at least 80% in shares of UK-listed companies",
            {"Financials": 23, "Consumer Staples": 14, "Health Care": 12, "Energy": 11,
             "Industrials": 12, "Materials": 7, "Consumer Discretionary": 8, "Utilities": 4,
             "Communication Services": 3, "Information Technology": 2, "Real Estate": 2},
            {"UK": 95, "Europe ex UK": 3, "North America": 2}, EQUITY_ASSETS, UK_LARGE,
            ("UK Growth", "UK Opportunities", "UK Select", "UK Equity", "UK Focus",
             "UK Alpha", "UK Recovery", "UK Core", "British Companies"),
            indices=("FTSE 250 Index", "MSCI United Kingdom Index"), weight=22,
        ),
        Archetype(
            "uk_income", "UK Equity Income", "Equity",
            "mainly in shares of UK companies that pay dividends",
            {"Financials": 28, "Consumer Staples": 14, "Energy": 13, "Utilities": 9,
             "Health Care": 10, "Materials": 8, "Industrials": 8, "Communication Services": 4,
             "Consumer Discretionary": 3, "Real Estate": 3},
            {"UK": 90, "Europe ex UK": 6, "North America": 4}, {"Equity": 0.97, "Cash": 0.03},
            UK_LARGE + UK_INCOME_EXTRA,
            ("UK Equity Income", "Higher Income", "UK Income", "Dividend Growth",
             "Income Builder", "Enhanced Income"),
            goals=INCOME_GOALS, indices=("FTSE UK Dividend+ Index",), weight=14,
        ),
        Archetype(
            "uk_smaller", "UK Smaller Companies", "Equity",
            "in shares of smaller UK companies",
            {"Industrials": 28, "Consumer Discretionary": 18, "Financials": 15,
             "Information Technology": 12, "Materials": 6, "Health Care": 6,
             "Communication Services": 6, "Real Estate": 6, "Consumer Staples": 3},
            {"UK": 97, "Europe ex UK": 2, "North America": 1}, {"Equity": 0.96, "Cash": 0.04},
            UK_SMALL,
            ("UK Smaller Companies", "UK Small Cap", "UK Emerging Companies", "UK Mid Cap",
             "UK Microcap"),
            ocf=(0.75, 1.15), top_weight=(0.025, 0.045), indices=("FTSE SmallCap Index",),
            weight=12,
        ),
        Archetype(
            "us", "North America", "Equity", "in shares of US and Canadian companies",
            {"Information Technology": 31, "Financials": 13, "Health Care": 10,
             "Consumer Discretionary": 10, "Communication Services": 9, "Industrials": 8,
             "Consumer Staples": 6, "Energy": 3.5, "Utilities": 2.5, "Real Estate": 2.2,
             "Materials": 2},
            {"North America": 99, "Europe ex UK": 1}, {"Equity": 0.99, "Cash": 0.01}, US,
            ("American", "US Equity", "North American", "US Opportunities", "US Growth",
             "US Select"),
            indices=("MSCI USA Index", "S&P 500 Equal Weight Index", "NASDAQ-100 Index"),
            weight=18,
        ),
        Archetype(
            "global", "Global", "Equity", "in shares of companies anywhere in the world",
            {"Information Technology": 25, "Financials": 16, "Health Care": 10,
             "Consumer Discretionary": 10, "Industrials": 11, "Communication Services": 8,
             "Consumer Staples": 6, "Energy": 4, "Materials": 3.5, "Utilities": 2.6,
             "Real Estate": 2},
            {"North America": 70, "Europe ex UK": 13, "Japan": 6, "UK": 4,
             "Developed Asia Pacific": 3, "Emerging Asia": 4},
            {"Equity": 0.98, "Cash": 0.02}, US + EUROPE[:10] + JAPAN[:4],
            ("Global Equity", "Global Growth", "World Opportunities", "Global Select",
             "Global Leaders", "Global Sustainable", "Worldwide", "Global Alpha",
             "Global Focus", "Global Core"),
            indices=("FTSE All-World Index", "MSCI ACWI Index", "FTSE Developed Index",
                     "MSCI World ESG Leaders Index"),
            weight=30,
        ),
        Archetype(
            "global_income", "Global Equity Income", "Equity",
            "in dividend-paying shares of companies worldwide",
            {"Financials": 20, "Health Care": 13, "Consumer Staples": 12,
             "Information Technology": 14, "Industrials": 11, "Utilities": 6, "Energy": 7,
             "Consumer Discretionary": 7, "Communication Services": 5, "Materials": 3,
             "Real Estate": 2},
            {"North America": 50, "Europe ex UK": 22, "UK": 12, "Japan": 6,
             "Developed Asia Pacific": 5, "Emerging Asia": 5},
            {"Equity": 0.97, "Cash": 0.03}, US + EUROPE + UK_LARGE[:8],
            ("Global Equity Income", "Global Dividend", "Global Income", "World Income"),
            goals=INCOME_GOALS, indices=("FTSE All-World High Dividend Yield Index",),
            weight=12,
        ),
        Archetype(
            "europe", "Europe Excluding UK", "Equity",
            "in shares of companies in continental Europe",
            {"Financials": 20, "Industrials": 18, "Health Care": 15, "Consumer Staples": 9,
             "Consumer Discretionary": 10, "Information Technology": 8, "Materials": 6,
             "Energy": 4, "Utilities": 5, "Communication Services": 4, "Real Estate": 1},
            {"Europe ex UK": 98, "UK": 2}, EQUITY_ASSETS, EUROPE,
            ("European", "Europe ex UK", "European Opportunities", "Continental European",
             "European Select"),
            indices=("FTSE Developed Europe ex UK Index", "MSCI Europe ex UK Index"),
            weight=14,
        ),
        Archetype(
            "japan", "Japan", "Equity", "in shares of Japanese companies",
            {"Industrials": 23, "Consumer Discretionary": 18, "Information Technology": 14,
             "Financials": 14, "Communication Services": 8, "Health Care": 7, "Materials": 6,
             "Consumer Staples": 5, "Real Estate": 3, "Utilities": 1, "Energy": 1},
            {"Japan": 99, "Developed Asia Pacific": 1}, EQUITY_ASSETS, JAPAN,
            ("Japan", "Japanese Equity", "Japan Opportunities", "Japan Growth"),
            indices=("FTSE Japan Index", "MSCI Japan Index"), weight=10,
        ),
        Archetype(
            "asia", "Asia Pacific Excluding Japan", "Equity",
            "in shares of companies in Asia Pacific, excluding Japan",
            {"Information Technology": 25, "Financials": 25, "Consumer Discretionary": 12,
             "Communication Services": 9, "Materials": 8, "Industrials": 7, "Energy": 4,
             "Real Estate": 4, "Health Care": 3, "Consumer Staples": 3},
            {"Developed Asia Pacific": 35, "Emerging Asia": 65}, EQUITY_ASSETS, ASIA_EM[:16],
            ("Asian", "Asia Pacific", "Pacific Growth", "Asian Opportunities"),
            indices=("FTSE Developed Asia Pacific ex Japan Index",), weight=10,
        ),
        Archetype(
            "em", "Global Emerging Markets", "Equity",
            "in shares of companies in emerging markets",
            {"Financials": 24, "Information Technology": 23, "Consumer Discretionary": 13,
             "Communication Services": 9, "Materials": 7, "Energy": 5, "Industrials": 7,
             "Consumer Staples": 5, "Health Care": 3, "Utilities": 2.5, "Real Estate": 1.5},
            {"Emerging Asia": 78, "Emerging EMEA": 12, "Latin America": 10}, EQUITY_ASSETS,
            ASIA_EM,
            ("Emerging Markets", "Global Emerging Markets", "EM Opportunities",
             "Emerging Markets Growth"),
            ocf=(0.7, 1.2), indices=("FTSE Emerging Index", "MSCI Emerging Markets Index"),
            weight=14,
        ),
        Archetype(
            "tech", "Technology and Technology Innovation", "Equity",
            "in shares of technology companies worldwide",
            {"Information Technology": 72, "Communication Services": 16,
             "Consumer Discretionary": 10, "Industrials": 2},
            {"North America": 82, "Emerging Asia": 7, "Europe ex UK": 6, "Japan": 3, "UK": 2},
            EQUITY_ASSETS, TECH, ("Technology", "Digital Innovation", "Future Tech"),
            ocf=(0.75, 1.1), top_weight=(0.06, 0.09),
            indices=("MSCI World Information Technology Index",), weight=8,
        ),
        Archetype(
            "strat_bond", "£ Strategic Bond", "Fixed Income",
            "flexibly across government and corporate bonds",
            {}, {"UK": 60, "North America": 22, "Europe ex UK": 18},
            {"Corporate Bonds": 0.6, "Government Bonds": 0.32, "Cash": 0.08},
            CORP_BONDS + GILTS[:4] + GLOBAL_GOVT[:3],
            ("Strategic Bond", "Optimal Income", "Flexible Bond", "Total Return Bond"),
            goals=BOND_GOALS, styles=BOND_STYLES, ocf=(0.4, 0.75), top_weight=(0.015, 0.04),
            weight=14,
        ),
        Archetype(
            "corp_bond", "£ Corporate Bond", "Fixed Income",
            "mainly in sterling-denominated investment grade corporate bonds",
            {}, {"UK": 70, "North America": 12, "Europe ex UK": 18},
            {"Corporate Bonds": 0.88, "Government Bonds": 0.08, "Cash": 0.04}, CORP_BONDS,
            ("Corporate Bond", "Sterling Corporate Bond", "Investment Grade Bond",
             "Sterling Credit"),
            goals=BOND_GOALS, styles=BOND_STYLES, ocf=(0.35, 0.65), top_weight=(0.01, 0.03),
            indices=("Markit iBoxx GBP Non-Gilts Index",), weight=10,
        ),
        Archetype(
            "gilts", "UK Gilts", "Fixed Income", "in UK government bonds (gilts)",
            {}, {"UK": 100}, {"Government Bonds": 0.98, "Cash": 0.02}, GILTS,
            ("Gilt", "UK Government Bond", "Long Gilt"),
            goals=BOND_GOALS, styles=BOND_STYLES, ocf=(0.15, 0.5), top_weight=(0.03, 0.06),
            indices=("FTSE Actuaries UK Index-Linked Gilts All Stocks Index",), weight=6,
        ),
        Archetype(
            "global_bond", "Global Mixed Bond", "Fixed Income",
            "in government and corporate bonds from around the world",
            {}, {"North America": 42, "Europe ex UK": 25, "Japan": 12, "UK": 5,
                 "Developed Asia Pacific": 4, "Emerging Asia": 8, "Latin America": 2,
                 "Emerging EMEA": 2},
            {"Government Bonds": 0.6, "Corporate Bonds": 0.35, "Cash": 0.05},
            GLOBAL_GOVT + CORP_BONDS[:6],
            ("Global Bond", "Global Aggregate Bond", "International Bond"),
            goals=BOND_GOALS, styles=BOND_STYLES, ocf=(0.35, 0.7), top_weight=(0.01, 0.03),
            indices=("Bloomberg Global Treasury Index",), weight=8,
        ),
        Archetype(
            "mixed_40_85", "Mixed Investment 40-85% Shares", "Mixed Assets",
            "in a mix of global shares and bonds, with 40-85% in shares",
            {"Information Technology": 22, "Financials": 17, "Health Care": 11,
             "Consumer Discretionary": 10, "Industrials": 11, "Consumer Staples": 8,
             "Communication Services": 7, "Energy": 6, "Materials": 4, "Utilities": 3,
             "Real Estate": 1},
            {"North America": 40, "UK": 30, "Europe ex UK": 12, "Japan": 5,
             "Emerging Asia": 8, "Developed Asia Pacific": 5},
            {"Equity": 0.65, "Government Bonds": 0.15, "Corporate Bonds": 0.12, "Cash": 0.04,
             "Property": 0.02, "Alternatives": 0.02},
            MIXED, ("Balanced Managed", "Growth Portfolio", "Managed Growth", "Adventurous"),
            styles=MIXED_STYLES, ocf=(0.3, 1.0), top_weight=(0.015, 0.04), weight=16,
        ),
        Archetype(
            "mixed_20_60", "Mixed Investment 20-60% Shares", "Mixed Assets",
            "in a mix of shares and bonds, with 20-60% in shares",
            {"Information Technology": 20, "Financials": 18, "Health Care": 12,
             "Consumer Discretionary": 9, "Industrials": 11, "Consumer Staples": 9,
             "Communication Services": 7, "Energy": 6, "Materials": 4, "Utilities": 3,
             "Real Estate": 1},
            {"UK": 40, "North America": 32, "Europe ex UK": 14, "Japan": 5,
             "Emerging Asia": 6, "Developed Asia Pacific": 3},
            {"Equity": 0.45, "Government Bonds": 0.22, "Corporate Bonds": 0.22, "Cash": 0.05,
             "Property": 0.03, "Alternatives": 0.03},
            MIXED, ("Cautious Managed", "Balanced Portfolio", "Distribution", "Moderate"),
            styles=MIXED_STYLES, ocf=(0.3, 0.95), top_weight=(0.015, 0.04), weight=12,
        ),
        Archetype(
            "mixed_0_35", "Mixed Investment 0-35% Shares", "Mixed Assets",
            "mainly in bonds with up to 35% in shares",
            {"Financials": 20, "Information Technology": 18, "Health Care": 13,
             "Consumer Staples": 11, "Industrials": 10, "Consumer Discretionary": 8,
             "Communication Services": 7, "Energy": 6, "Utilities": 4, "Materials": 3},
            {"UK": 50, "North America": 28, "Europe ex UK": 15, "Japan": 4, "Emerging Asia": 3},
            {"Equity": 0.25, "Government Bonds": 0.35, "Corporate Bonds": 0.3, "Cash": 0.06,
             "Alternatives": 0.04},
            MIXED, ("Defensive", "Conservative Portfolio", "Cautious Income"),
            styles=MIXED_STYLES, ocf=(0.3, 0.9), top_weight=(0.02, 0.05), weight=6,
        ),
        Archetype(
            "property", "Property Other", "Property",
            "in shares of property companies and real estate investment trusts",
            {"Real Estate": 95, "Industrials": 3, "Communication Services": 2},
            {"UK": 45, "North America": 30, "Europe ex UK": 15, "Developed Asia Pacific": 10},
            {"Property": 0.94, "Cash": 0.06}, PROPERTY,
            ("Global Property", "Property Securities", "Real Estate"),
            ocf=(0.7, 1.1), indices=("FTSE EPRA Nareit Developed Index",), weight=5,
        ),
        Archetype(
            "resources", "Commodities and Natural Resources", "Equity",
            "in shares of mining and energy companies worldwide",
            {"Materials": 50, "Energy": 45, "Industrials": 3, "Utilities": 2},
            {"North America": 40, "UK": 20, "Developed Asia Pacific": 15, "Latin America": 10,
             "Europe ex UK": 8, "Emerging EMEA": 7},
            EQUITY_ASSETS, RESOURCES, ("Natural Resources", "Global Resources", "Energy"),
            ocf=(0.8, 1.2), weight=5,
        ),
        Archetype(
            "money_market", "Standard Money Market", "Money Market",
            "in short-term sterling deposits, treasury bills and certificates of deposit",
            {}, {"UK": 80, "Europe ex UK": 10, "North America": 10},
            {"Cash": 0.85, "Government Bonds": 0.15}, MONEY_MARKET,
            ("Sterling Liquidity", "Cash", "Money Market"),
            goals=("{preserve capital|maintain capital} and provide income in line with "
                   "money market rates",),
            styles=("The fund holds only high-quality, short-dated instruments.",),
            ocf=(0.1, 0.25), top_weight=(0.04, 0.08), weight=5,
        ),
        Archetype(
            "abs_return", "Targeted Absolute Return", "Mixed Assets",
            "across equities, bonds, currencies and derivatives",
            {"Financials": 20, "Information Technology": 20, "Industrials": 15,
             "Health Care": 15, "Consumer Discretionary": 15, "Energy": 15},
            {"UK": 40, "North America": 25, "Europe ex UK": 20, "Japan": 5, "Emerging Asia": 10},
            {"Equity": 0.3, "Government Bonds": 0.3, "Cash": 0.25, "Corporate Bonds": 0.1,
             "Alternatives": 0.05},
            ABS_RETURN, ("Absolute Return", "Multi-Strategy", "Targeted Return"),
            goals=("{deliver|achieve} a positive return in all market conditions over rolling "
                   "three-year periods",),
            styles=("The fund uses derivatives extensively, including short positions.",),
            ocf=(0.7, 1.1), top_weight=(0.04, 0.1), weight=6,
        ),
    ]
}  # fmt: skip

# ----------------------------------------------------------- deliberate clusters


@dataclass(frozen=True)
class TrackerCluster:
    key: str
    index: str
    archetype: str
    stems: tuple[str, ...]
    holdings: tuple[tuple[str, float], ...]
    sectors: dict[str, float] | None = None  # overrides archetype centroid
    regions: dict[str, float] | None = None
    size: int = 5


@dataclass(frozen=True)
class ActiveCluster:
    key: str
    archetype: str
    stems: tuple[str, ...]
    objective: str  # {a|b} alternations vary per member
    core: tuple[str, ...]
    extras: tuple[str, ...]
    size: int = 4


@dataclass(frozen=True)
class Outlier:
    key: str
    name: str
    ia_sector: str
    asset_class: str
    objective: str
    sectors: dict[str, float]
    regions: dict[str, float]
    assets: dict[str, float]
    holdings: tuple[str, ...]
    ocf: float
    extra: dict = field(default_factory=dict)


TRACKERS = (
    TrackerCluster(
        "trk_ftse100", "FTSE 100 Index", "uk_large",
        ("FTSE 100 Index Fund", "UK 100 Tracker", "FTSE 100 Tracker", "UK Large Cap Index"),
        (("Shell", .085), ("AstraZeneca", .08), ("HSBC Holdings", .075), ("Unilever", .055),
         ("RELX", .04), ("BP", .035), ("British American Tobacco", .035), ("GSK", .03),
         ("Diageo", .028), ("Rio Tinto", .027)),
        sectors={"Financials": 22, "Consumer Staples": 15, "Health Care": 13, "Energy": 12,
                 "Industrials": 13, "Materials": 8, "Consumer Discretionary": 7,
                 "Utilities": 4, "Communication Services": 3, "Information Technology": 1,
                 "Real Estate": 1},
        regions={"UK": 100},
    ),
    TrackerCluster(
        "trk_ftse_allshare", "FTSE All-Share Index", "uk_large",
        ("FTSE All-Share Index Fund", "UK All Share Tracker", "UK Equity Index",
         "All-Share Index"),
        (("Shell", .072), ("AstraZeneca", .068), ("HSBC Holdings", .064), ("Unilever", .047),
         ("RELX", .034), ("BP", .03), ("British American Tobacco", .03), ("GSK", .026),
         ("Diageo", .024), ("Rio Tinto", .023)),
        sectors={"Financials": 24, "Consumer Staples": 13, "Health Care": 11, "Energy": 10,
                 "Industrials": 15, "Materials": 7, "Consumer Discretionary": 9,
                 "Utilities": 4, "Communication Services": 3, "Information Technology": 2,
                 "Real Estate": 3},
        regions={"UK": 100},
    ),
    TrackerCluster(
        "trk_sp500", "S&P 500 Index", "us",
        ("S&P 500 Index Fund", "US 500 Tracker", "US Equity Index", "S&P 500 Tracker"),
        (("Apple", .07), ("Microsoft", .065), ("Nvidia", .065), ("Amazon", .04),
         ("Meta Platforms", .025), ("Alphabet Class A", .022), ("Broadcom", .022),
         ("Alphabet Class C", .018), ("Berkshire Hathaway", .017), ("Tesla", .016)),
        regions={"North America": 100},
    ),
    TrackerCluster(
        "trk_msci_world", "MSCI World Index", "global",
        ("MSCI World Index Fund", "World Equity Tracker", "Developed World Index",
         "Global Equity Index"),
        (("Apple", .05), ("Nvidia", .048), ("Microsoft", .046), ("Amazon", .028),
         ("Meta Platforms", .018), ("Alphabet Class A", .016), ("Broadcom", .015),
         ("Alphabet Class C", .014), ("Tesla", .012), ("JPMorgan Chase", .011)),
        regions={"North America": 73, "Europe ex UK": 12.5, "Japan": 5.5, "UK": 3.5,
                 "Developed Asia Pacific": 3.5},
    ),
    TrackerCluster(
        "trk_global_agg", "Bloomberg Global Aggregate Index (GBP Hedged)", "global_bond",
        ("Global Aggregate Bond Index", "Global Bond Tracker", "Global Bond Index"),
        (("US Treasury 4.0% 2034", .006), ("US Treasury 4.125% 2032", .0055),
         ("Japan Govt 0.8% 2033", .005), ("Bund 2.5% 2033", .0045),
         ("China Govt 2.6% 2033", .0045), ("France OAT 3% 2034", .004),
         ("US Treasury 2.875% 2028", .004), ("Italy BTP 4% 2031", .0035),
         ("UK Treasury 4.25% 2032", .003), ("Canada 3.25% 2033", .0025)),
        regions={"North America": 43, "Europe ex UK": 24, "Japan": 11, "UK": 4,
                 "Developed Asia Pacific": 4, "Emerging Asia": 10, "Latin America": 2,
                 "Emerging EMEA": 2},
    ),
    TrackerCluster(
        "trk_ftse_gilts", "FTSE Actuaries UK Conventional Gilts All Stocks Index", "gilts",
        ("UK Gilt Index", "Gilt Tracker", "UK Government Bond Index", "All Stocks Gilt Index"),
        (("UK Treasury 4.25% 2032", .042), ("UK Treasury 4.5% 2034", .04),
         ("UK Treasury 0.875% 2033", .038), ("UK Treasury 4.125% 2029", .036),
         ("UK Treasury 3.75% 2038", .033), ("UK Treasury 4.75% 2030", .032),
         ("UK Treasury 1.25% 2041", .03), ("UK Treasury 0.625% 2035", .028),
         ("UK Treasury 3.5% 2045", .025), ("UK Treasury 1.5% 2047", .022)),
    ),
)  # fmt: skip

NEAR_DUPES = (
    ActiveCluster(
        "act_uk_income", "uk_income",
        ("UK Equity Income", "UK Dividend", "Income & Growth", "UK Income Plus"),
        "The fund aims to {deliver|provide} {a growing income|an income that rises over time} "
        "{together with|and} capital growth over {rolling five-year periods|any five-year "
        "period}, targeting a yield {above|in excess of} that of the FTSE All-Share. It invests "
        "in {high-quality|quality} UK companies with {sustainable|resilient} dividends, using a "
        "{disciplined|patient} value-focused process.",
        ("British American Tobacco", "Imperial Brands", "Legal & General", "Aviva",
         "National Grid", "SSE", "Shell", "HSBC Holdings", "GSK", "Unilever"),
        ("Phoenix Group", "M&G", "Tesco", "Lloyds Banking Group", "Rio Tinto"),
    ),
    ActiveCluster(
        "act_global_tech", "tech",
        ("Global Technology", "Technology Leaders", "Digital Future", "Tech Innovators"),
        "The fund {seeks|aims} to {achieve|deliver} long-term capital growth by investing in "
        "{companies at the forefront of|leading companies driving} technological change, "
        "{including|such as} artificial intelligence, semiconductors, cloud software and "
        "cybersecurity. It is {concentrated|high conviction}, typically holding "
        "{30 to 40|25 to 40} stocks worldwide.",
        ("Nvidia", "Microsoft", "Broadcom", "TSMC", "ASML", "Meta Platforms", "Alphabet",
         "CrowdStrike", "ServiceNow", "AMD"),
        ("Palantir", "Arista Networks", "Synopsys", "Datadog", "Snowflake"),
    ),
    ActiveCluster(
        "act_uk_smaller", "uk_smaller",
        ("UK Smaller Companies", "UK Small Cap Growth", "UK Discovery", "UK Emerging Leaders"),
        "The fund aims to {achieve|generate} capital growth over {five years|the long term} by "
        "investing in {smaller|small and mid-sized} UK companies, {typically|usually} those "
        "outside the FTSE 350 at the time of purchase. The managers {look for|seek} "
        "{founder-led|owner-managed} businesses with {niche|dominant} market positions and "
        "strong cash generation.",
        ("Bloomsbury Publishing", "Volution Group", "Gamma Communications",
         "Judges Scientific", "Craneware", "Treatt", "Bytes Technology", "Alpha Group",
         "XPS Pensions", "CVS Group"),
        ("FD Technologies", "Hollywood Bowl", "Cranswick", "Chemring"),
    ),
    ActiveCluster(
        "act_strat_bond", "strat_bond",
        ("Strategic Bond", "Dynamic Bond", "Unconstrained Bond", "Strategic Income"),
        "The fund aims to {maximise|deliver} total return {(income plus capital)|through "
        "income and capital growth} over {rolling three-year periods|any three-year period} by "
        "investing {flexibly|without constraints} across government bonds, investment grade "
        "and high yield corporate bonds, {actively managing|dynamically managing} duration and "
        "credit risk.",
        ("UK Treasury 4.25% 2032", "US Treasury 4.0% 2034", "HSBC 6.8% 2031",
         "Barclays 7.09% 2029", "Aviva 6.875% 2058", "Lloyds 5.25% 2029",
         "Vodafone 5.9% 2032", "Legal & General 5.625% 2049", "AT&T 4.375% 2029",
         "Bund 2.5% 2033"),
        ("NatWest 5.125% 2030", "Orsted 5.125% 2034", "Tesco 6% 2029"),
    ),
    ActiveCluster(
        "act_japan_value", "japan",
        ("Japan Value", "Japan Recovery", "Japan Governance", "Japanese Value Opportunities"),
        "The fund aims to {achieve|deliver} capital growth over {five years|the long term} by "
        "investing in {undervalued|out-of-favour} Japanese companies {that are|which are} "
        "improving {corporate governance|shareholder returns}, {including|through} buybacks "
        "and unwinding cross-shareholdings.",
        ("Mitsubishi UFJ", "Sumitomo Mitsui", "Toyota Motor", "Mitsubishi Corp", "Itochu",
         "Honda Motor", "Tokio Marine", "Hitachi", "Takeda", "KDDI"),
        ("Inpex", "Sumitomo Corp", "Mizuho Financial", "Nippon Steel"),
    ),
)  # fmt: skip

OUTLIERS = (
    Outlier(
        "outlier_gold", "Kestrel Gold & Precious Metals", "Commodities and Natural Resources",
        "Equity",
        "The fund aims to achieve capital growth by investing in gold and silver mining "
        "companies and royalty and streaming businesses worldwide.",
        {"Materials": 100}, {"North America": 65, "Developed Asia Pacific": 15,
                             "Emerging EMEA": 15, "Latin America": 5},
        {"Equity": 0.97, "Commodities": 0.03},
        ("Newmont", "Agnico Eagle", "Barrick Gold", "Wheaton Precious Metals",
         "Franco-Nevada", "Gold Fields", "Northern Star", "Kinross Gold", "Endeavour Mining",
         "Royal Gold"), 0.95,
    ),
    Outlier(
        "outlier_frontier", "Saltmarsh Frontier Markets", "Specialist", "Equity",
        "The fund aims to achieve long-term capital growth by investing in frontier markets "
        "such as Vietnam, Kazakhstan, Nigeria, Egypt and Peru, outside the mainstream "
        "emerging markets indices.",
        {"Financials": 35, "Real Estate": 12, "Materials": 12, "Consumer Staples": 10,
         "Consumer Discretionary": 8, "Information Technology": 8,
         "Communication Services": 6, "Industrials": 5, "Energy": 4},
        {"Emerging Asia": 45, "Emerging EMEA": 40, "Latin America": 15},
        {"Equity": 0.96, "Cash": 0.04},
        ("Kaspi.kz", "FPT Corp", "Vietcombank", "Hoa Phat Group", "Halyk Bank",
         "Dangote Cement", "Commercial International Bank", "Credicorp", "Masan Group",
         "Zenith Bank"), 1.45,
    ),
    Outlier(
        "outlier_india", "Wexford India Opportunities", "India/Indian Subcontinent", "Equity",
        "The fund aims to achieve capital growth by investing in shares of Indian companies, "
        "benefiting from the country's long-term domestic consumption and infrastructure "
        "growth.",
        {"Financials": 30, "Information Technology": 13, "Consumer Discretionary": 11,
         "Energy": 10, "Industrials": 9, "Consumer Staples": 8, "Materials": 8,
         "Health Care": 6, "Communication Services": 4, "Utilities": 1},
        {"Emerging Asia": 100}, {"Equity": 0.97, "Cash": 0.03},
        ("HDFC Bank", "ICICI Bank", "Reliance Industries", "Infosys", "Bharti Airtel",
         "Larsen & Toubro", "Axis Bank", "Mahindra & Mahindra", "Sun Pharma",
         "Tata Consultancy Services"), 1.05,
    ),
    Outlier(
        "outlier_biotech", "Lowther Biotechnology", "Specialist", "Equity",
        "The fund aims to achieve capital growth by investing in biotechnology companies "
        "developing novel therapies, including gene editing and rare disease treatments.",
        {"Health Care": 100}, {"North America": 85, "Europe ex UK": 10, "UK": 5},
        {"Equity": 0.98, "Cash": 0.02},
        ("Vertex Pharmaceuticals", "Regeneron", "Amgen", "Gilead Sciences", "Argenx",
         "Alnylam", "BioMarin", "Insmed", "Ascendis Pharma", "Intellia Therapeutics"), 1.1,
    ),
    Outlier(
        "outlier_direct_property", "Pennine UK Commercial Property", "UK Direct Property",
        "Property",
        "The fund aims to provide income and capital growth by investing directly in UK "
        "commercial property: logistics warehouses, offices and retail parks.",
        {"Real Estate": 100}, {"UK": 100}, {"Property": 0.85, "Cash": 0.15},
        ("Logistics warehouse, Daventry", "Retail park, Leeds", "Office, Manchester",
         "Distribution centre, Milton Keynes", "Industrial estate, Bristol",
         "Office, Edinburgh", "Retail park, Glasgow", "Logistics warehouse, Doncaster",
         "Trade park, Reading", "Office, Birmingham"), 1.3,
    ),
)  # fmt: skip

# ---------------------------------------------------------------------- helpers

_ALT = re.compile(r"\{([^{}]*)\}")


def _variant(text: str, rng: random.Random) -> str:
    return _ALT.sub(lambda m: rng.choice(m.group(1).split("|")), text)


def _normalise(d: dict[str, float]) -> dict[str, float]:
    total = sum(d.values())
    return {k: v / total for k, v in d.items() if v > 0} if total > 0 else {}


def _perturb(
    base: dict[str, float],
    sigma: float,
    rng: random.Random,
    keys: tuple[str, ...] = (),
    leak: int = 0,
) -> dict[str, float]:
    """Multiplicative log-normal noise; optionally leak small weight into unused keys."""
    out = {k: v * rng.lognormvariate(0, sigma) for k, v in base.items() if v > 0}
    unused = [k for k in keys if k not in out]
    for k in rng.sample(unused, min(leak, len(unused))):
        out[k] = rng.uniform(0.005, 0.04) * sum(out.values())
    return _normalise(out)


def _round(d: dict[str, float], scale: float = 1.0) -> dict[str, float]:
    return {k: round(v * scale, 4) for k, v in sorted(d.items()) if round(v * scale, 4) > 0}


def _weights_desc(n: int, top: float, rng: random.Random) -> list[float]:
    weights, w = [], top
    for _ in range(n):
        weights.append(round(w, 4))
        w *= rng.uniform(0.8, 0.95)
    return weights


def _gics_share(assets: dict[str, float]) -> float:
    return assets.get("Equity", 0.0) + assets.get("Property", 0.0)


def _ocf(lo: float, hi: float, rng: random.Random) -> float:
    return round(rng.uniform(lo, hi), 2)


class _Names:
    def __init__(self) -> None:
        self.used: set[str] = set()

    def make(self, provider: str, stem: str) -> str:
        name = f"{provider} {stem}"
        for suffix in ("", " Fund", " II", " Plus", " Select"):
            if name + suffix not in self.used:
                self.used.add(name + suffix)
                return name + suffix
        raise ValueError(f"cannot make unique name for {name}")


def _build(
    *,
    name: str,
    provider: str,
    arch: Archetype,
    objective: str,
    sectors: dict[str, float],
    regions: dict[str, float],
    assets: dict[str, float],
    holdings: list[tuple[str, float]],
    ocf: float,
    is_passive: bool = False,
    tracked_index: str | None = None,
    cluster_id: str | None = None,
    ia_sector: str | None = None,
    asset_class: str | None = None,
) -> Fund:
    assets = _normalise(assets)
    return Fund(
        id="",
        name=name,
        provider=provider,
        ia_sector=ia_sector or arch.ia_sector,
        asset_class=asset_class or arch.asset_class,
        ocf=ocf,
        is_passive=is_passive,
        tracked_index=tracked_index,
        objective=objective,
        top_holdings=[Holding(name=n, weight=w) for n, w in sorted(holdings, key=lambda h: -h[1])],
        sector_weights=_round(_normalise(sectors), _gics_share(assets)) if sectors else {},
        region_weights=_round(regions),
        asset_class_weights=_round(assets),
        cluster_id=cluster_id,
    )


def _tracker_objective(index: str, rng: random.Random) -> str:
    return _variant(
        f"The fund aims to {{track|replicate}} the performance of the {index} "
        "{before charges|as closely as possible}. "
        "{It uses full physical replication, holding all index constituents in their index "
        "weights.|It uses optimised sampling to hold a representative selection of index "
        "constituents.}",
        rng,
    )


# --------------------------------------------------------------------- generator


def _trackers(rng: random.Random, names: _Names) -> list[Fund]:
    funds = []
    for spec in TRACKERS:
        arch = ARCHETYPES[spec.archetype]
        for provider in rng.sample(PROVIDERS, spec.size):
            funds.append(
                _build(
                    name=names.make(provider, rng.choice(spec.stems)),
                    provider=provider,
                    arch=arch,
                    objective=_tracker_objective(spec.index, rng),
                    sectors=_perturb(spec.sectors or arch.sectors, TRACKER_NOISE, rng),
                    regions=_perturb(spec.regions or arch.regions, TRACKER_NOISE, rng),
                    assets=_perturb(arch.assets, TRACKER_NOISE, rng),
                    holdings=[
                        (n, round(w * rng.lognormvariate(0, 0.02), 4)) for n, w in spec.holdings
                    ],
                    ocf=_ocf(0.04, 0.25, rng),
                    is_passive=True,
                    tracked_index=spec.index,
                    cluster_id=spec.key,
                )
            )
    return funds


def _near_dupes(rng: random.Random, names: _Names) -> list[Fund]:
    funds = []
    for spec in NEAR_DUPES:
        arch = ARCHETYPES[spec.archetype]
        # Shared centroid, distinct from the archetype's background funds.
        c_sectors = _perturb(arch.sectors, DUPE_CENTROID_NOISE, rng) if arch.sectors else {}
        c_regions = _perturb(arch.regions, DUPE_CENTROID_NOISE, rng)
        lead = rng.choice(PROVIDERS)
        providers = [lead, lead] + rng.sample([p for p in PROVIDERS if p != lead], spec.size - 2)
        for i, provider in enumerate(providers):
            held = rng.sample(spec.core, 8) + rng.sample(spec.extras, 2)
            funds.append(
                _build(
                    name=names.make(provider, spec.stems[i % len(spec.stems)]),
                    provider=provider,
                    arch=arch,
                    objective=_variant(spec.objective, rng),
                    sectors=_perturb(c_sectors, DUPE_MEMBER_NOISE, rng) if c_sectors else {},
                    regions=_perturb(c_regions, DUPE_MEMBER_NOISE, rng),
                    assets=_perturb(arch.assets, DUPE_MEMBER_NOISE / 2, rng),
                    holdings=list(
                        zip(
                            held, _weights_desc(10, rng.uniform(*arch.top_weight), rng), strict=True
                        )
                    ),
                    ocf=_ocf(*arch.ocf, rng),
                    cluster_id=spec.key,
                )
            )
    return funds


def _outliers(rng: random.Random, names: _Names) -> list[Fund]:
    funds = []
    for o in OUTLIERS:
        provider = o.name.split()[0]
        names.used.add(o.name)
        funds.append(
            _build(
                name=o.name,
                provider=provider,
                arch=ARCHETYPES["global"],  # only used for defaults we override
                objective=o.objective,
                sectors=o.sectors,
                regions=_normalise(o.regions),
                assets=o.assets,
                holdings=list(zip(o.holdings, _weights_desc(10, 0.08, rng), strict=True)),
                ocf=o.ocf,
                cluster_id=o.key,
                ia_sector=o.ia_sector,
                asset_class=o.asset_class,
            )
        )
    return funds


def _background(n: int, rng: random.Random, names: _Names) -> list[Fund]:
    archs = list(ARCHETYPES.values())
    weights = [a.weight for a in archs]
    unused_indices = {a.key: list(a.indices) for a in archs}
    funds = []
    for _ in range(n):
        arch = rng.choices(archs, weights)[0]
        provider = rng.choice(PROVIDERS)
        sectors = (
            _perturb(arch.sectors, BACKGROUND_NOISE, rng, GICS_SECTORS, leak=1)
            if arch.sectors
            else {}
        )
        regions = _perturb(arch.regions, BACKGROUND_NOISE, rng, REGIONS, leak=rng.randint(0, 2))
        assets = _perturb(arch.assets, BACKGROUND_NOISE / 2, rng)
        held = rng.sample(arch.holdings, 10)
        holdings = list(
            zip(held, _weights_desc(10, rng.uniform(*arch.top_weight), rng), strict=True)
        )

        indices = unused_indices[arch.key]
        if indices and rng.random() < 0.25:
            index = indices.pop(rng.randrange(len(indices)))
            stem = index.removesuffix(" Index") + " Index Fund"
            funds.append(
                _build(
                    name=names.make(provider, stem), provider=provider, arch=arch,
                    objective=_tracker_objective(index, rng), sectors=sectors,
                    regions=regions, assets=assets, holdings=holdings,
                    ocf=_ocf(0.05, 0.3, rng), is_passive=True, tracked_index=index,
                )
            )  # fmt: skip
            continue

        objective = (
            f"The fund aims to {_variant(rng.choice(arch.goals), rng)} over "
            f"{rng.choice(HORIZONS)} by investing {arch.universe}. "
            f"{_variant(rng.choice(arch.styles), rng)}"
        )
        funds.append(
            _build(
                name=names.make(provider, rng.choice(arch.stems)), provider=provider,
                arch=arch, objective=objective, sectors=sectors, regions=regions,
                assets=assets, holdings=holdings, ocf=_ocf(*arch.ocf, rng),
            )
        )  # fmt: skip
    return funds


def generate_funds(n: int = DEFAULT_N, seed: int = DEFAULT_SEED) -> list[Fund]:
    """Deterministic for a given (n, seed). Clusters are always included in full."""
    rng = random.Random(seed)
    names = _Names()
    funds = _trackers(rng, names) + _near_dupes(rng, names) + _outliers(rng, names)
    if n < len(funds):
        raise ValueError(f"n must be at least {len(funds)} to fit the deliberate clusters")
    funds += _background(n - len(funds), rng, names)
    rng.shuffle(funds)
    return [f.model_copy(update={"id": f"F{i:04d}"}) for i, f in enumerate(funds, start=1)]


class SyntheticSource:
    """FundSource backed by the deterministic generator."""

    def __init__(self, n: int = DEFAULT_N, seed: int = DEFAULT_SEED) -> None:
        self.n, self.seed = n, seed

    def fetch(self) -> list[Fund]:
        return generate_funds(self.n, self.seed)
