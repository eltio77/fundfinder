from fundfinder.models import Fund

MIN_REGION_SHARE = 0.05
TOP_SECTORS = 3


def _pct(weight: float) -> str:
    return f"{round(weight * 100)}%"


def _ranked(weights: dict[str, float]) -> list[tuple[str, float]]:
    # Ties broken by name so the text is deterministic.
    return sorted(weights.items(), key=lambda kv: (-kv[1], kv[0]))


def build_profile(fund: Fund) -> str:
    """Text that gets embedded: what the fund is, what it holds and where."""
    parts = [f"{fund.name}.", fund.objective.strip()]
    parts.append(f"IA sector: {fund.ia_sector}. Asset class: {fund.asset_class}.")
    if fund.is_passive and fund.tracked_index:
        parts.append(f"Passive index fund tracking the {fund.tracked_index}.")
    else:
        parts.append("Actively managed.")

    if fund.top_holdings:
        parts.append("Top holdings: " + ", ".join(h.name for h in fund.top_holdings) + ".")

    sectors = [(k, w) for k, w in _ranked(fund.sector_weights) if w >= 0.01][:TOP_SECTORS]
    if sectors:
        parts.append("Main sectors: " + ", ".join(f"{k} {_pct(w)}" for k, w in sectors) + ".")

    regions = [(k, w) for k, w in _ranked(fund.region_weights) if w >= MIN_REGION_SHARE]
    if regions:
        parts.append("Region split: " + ", ".join(f"{k} {_pct(w)}" for k, w in regions) + ".")

    return " ".join(parts)
