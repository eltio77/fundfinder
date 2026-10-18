"""Fixed category orderings. The exposure vector layout depends on these, so
changing them requires re-seeding and rebuilding the exposure_vec index."""

GICS_SECTORS: tuple[str, ...] = (
    "Energy",
    "Materials",
    "Industrials",
    "Consumer Discretionary",
    "Consumer Staples",
    "Health Care",
    "Financials",
    "Information Technology",
    "Communication Services",
    "Utilities",
    "Real Estate",
)

REGIONS: tuple[str, ...] = (
    "UK",
    "North America",
    "Europe ex UK",
    "Japan",
    "Developed Asia Pacific",
    "Emerging Asia",
    "Emerging EMEA",
    "Latin America",
)

ASSET_CLASS_BREAKDOWN: tuple[str, ...] = (
    "Equity",
    "Government Bonds",
    "Corporate Bonds",
    "Cash",
    "Property",
    "Commodities",
    "Alternatives",
)

# Top-level classification used for filtering.
ASSET_CLASSES: tuple[str, ...] = (
    "Equity",
    "Fixed Income",
    "Mixed Assets",
    "Property",
    "Commodities",
    "Money Market",
)

EXPOSURE_DIMS = len(GICS_SECTORS) + len(REGIONS) + len(ASSET_CLASS_BREAKDOWN)
