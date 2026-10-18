import math

import pytest

from fundfinder.exposure import exposure_vector, l2_normalise, normalise_weights
from fundfinder.taxonomy import EXPOSURE_DIMS, GICS_SECTORS, REGIONS
from tests.factories import make_fund


def test_normalise_weights_dense_and_sums_to_one():
    vec = normalise_weights({"UK": 2.0, "Japan": 2.0}, REGIONS)
    assert len(vec) == len(REGIONS)
    assert sum(vec) == pytest.approx(1.0)
    assert vec[REGIONS.index("UK")] == pytest.approx(0.5)


def test_normalise_weights_clips_negatives_and_keeps_zero_block():
    assert normalise_weights({"UK": -1.0}, REGIONS) == [0.0] * len(REGIONS)
    vec = normalise_weights({"UK": 1.0, "Japan": -0.5}, REGIONS)
    assert vec[REGIONS.index("UK")] == 1.0
    assert vec[REGIONS.index("Japan")] == 0.0


def test_l2_normalise():
    assert l2_normalise([3.0, 4.0]) == [0.6, 0.8]
    assert l2_normalise([0.0, 0.0]) == [0.0, 0.0]


def test_exposure_vector_shape_and_unit_length():
    vec = exposure_vector(make_fund())
    assert len(vec) == EXPOSURE_DIMS
    assert math.sqrt(sum(x * x for x in vec)) == pytest.approx(1.0, abs=1e-5)


def test_exposure_vector_layout():
    vec = exposure_vector(make_fund())
    energy = vec[GICS_SECTORS.index("Energy")]
    uk = vec[len(GICS_SECTORS) + REGIONS.index("UK")]
    assert energy > 0 and uk > 0
    assert vec[GICS_SECTORS.index("Utilities")] == 0


def test_bond_fund_sector_block_is_empty():
    bond = make_fund(sector_weights={}, asset_class_weights={"Government Bonds": 1.0})
    vec = exposure_vector(bond)
    assert all(x == 0 for x in vec[: len(GICS_SECTORS)])


def test_similar_funds_score_higher_than_different_ones():
    def cos(a, b):
        return sum(x * y for x, y in zip(a, b, strict=True))

    base = exposure_vector(make_fund())
    near = exposure_vector(make_fund(region_weights={"UK": 0.95, "North America": 0.05}))
    far = exposure_vector(
        make_fund(
            sector_weights={"Information Technology": 1.0}, region_weights={"North America": 1.0}
        )
    )
    assert cos(base, near) > cos(base, far)
