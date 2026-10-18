from fundfinder.models import Fund, Holding


def make_fund(**overrides) -> Fund:
    data = dict(
        id="F0001",
        name="Kestrel FTSE 100 Index Fund",
        provider="Kestrel",
        ia_sector="UK All Companies",
        asset_class="Equity",
        ocf=0.06,
        is_passive=True,
        tracked_index="FTSE 100 Index",
        objective="The fund aims to track the FTSE 100 Index.",
        top_holdings=[Holding(name="Shell", weight=0.08), Holding(name="AstraZeneca", weight=0.07)],
        sector_weights={"Energy": 0.5, "Health Care": 0.3, "Financials": 0.2},
        region_weights={"UK": 0.97, "North America": 0.03},
        asset_class_weights={"Equity": 0.98, "Cash": 0.02},
    )
    data.update(overrides)
    return Fund(**data)
