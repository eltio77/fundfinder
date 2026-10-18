import math
from collections.abc import Mapping

from fundfinder.models import Fund
from fundfinder.taxonomy import ASSET_CLASS_BREAKDOWN, GICS_SECTORS, REGIONS


def normalise_weights(weights: Mapping[str, float], keys: tuple[str, ...]) -> list[float]:
    """Dense vector in `keys` order, negatives clipped, rescaled to sum to 1.
    An all-zero block stays all-zero."""
    raw = [max(0.0, float(weights.get(k, 0.0))) for k in keys]
    total = sum(raw)
    return [w / total for w in raw] if total > 0 else raw


def l2_normalise(vec: list[float]) -> list[float]:
    norm = math.sqrt(sum(x * x for x in vec))
    return [x / norm for x in vec] if norm > 0 else vec


def exposure_vector(fund: Fund) -> list[float]:
    """Concatenated sector | region | asset-class weights, L2-normalised.

    The sector block is kept in whole-portfolio terms (not rescaled) so a bond
    fund's near-empty sector block stays near-empty instead of being inflated.
    """
    sectors = [max(0.0, fund.sector_weights.get(k, 0.0)) for k in GICS_SECTORS]
    regions = normalise_weights(fund.region_weights, REGIONS)
    assets = normalise_weights(fund.asset_class_weights, ASSET_CLASS_BREAKDOWN)
    return [round(x, 6) for x in l2_normalise(sectors + regions + assets)]
