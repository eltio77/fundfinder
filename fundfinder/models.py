from pydantic import BaseModel, Field, field_validator

from fundfinder.taxonomy import ASSET_CLASS_BREAKDOWN, ASSET_CLASSES, GICS_SECTORS, REGIONS


class Holding(BaseModel):
    name: str
    weight: float = Field(ge=0, le=1)


# Provider data is rounded, so allow small overshoot.
ROUNDING_TOLERANCE = 0.005


def _check_weights(value: dict[str, float], allowed: tuple[str, ...]) -> dict[str, float]:
    unknown = set(value) - set(allowed)
    if unknown:
        raise ValueError(f"unknown categories: {sorted(unknown)}")
    if any(w < 0 for w in value.values()):
        raise ValueError("weights must be non-negative")
    if sum(value.values()) > 1 + ROUNDING_TOLERANCE:
        raise ValueError("weights must sum to at most 1")
    return value


class Fund(BaseModel):
    """Source data for one fund, as a data provider would supply it.

    Weights are fractions of the whole portfolio. sector_weights covers only the
    GICS-classifiable part (equities and listed property), so it may sum to < 1;
    region_weights and asset_class_weights should sum to 1.
    """

    id: str
    name: str
    provider: str
    ia_sector: str
    asset_class: str
    ocf: float = Field(ge=0, description="Ongoing charges figure, in percent")
    is_passive: bool
    tracked_index: str | None = None
    objective: str
    top_holdings: list[Holding] = Field(max_length=10)
    sector_weights: dict[str, float]
    region_weights: dict[str, float]
    asset_class_weights: dict[str, float]
    # Synthetic-data label for evaluation only; real data won't have it.
    cluster_id: str | None = None

    @field_validator("asset_class")
    @classmethod
    def _asset_class(cls, v: str) -> str:
        if v not in ASSET_CLASSES:
            raise ValueError(f"unknown asset class {v!r}")
        return v

    @field_validator("sector_weights")
    @classmethod
    def _sectors(cls, v: dict[str, float]) -> dict[str, float]:
        return _check_weights(v, GICS_SECTORS)

    @field_validator("region_weights")
    @classmethod
    def _regions(cls, v: dict[str, float]) -> dict[str, float]:
        return _check_weights(v, REGIONS)

    @field_validator("asset_class_weights")
    @classmethod
    def _assets(cls, v: dict[str, float]) -> dict[str, float]:
        return _check_weights(v, ASSET_CLASS_BREAKDOWN)
