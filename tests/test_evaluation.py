import math

import pytest

from fundfinder.evaluation import (
    mean,
    overlap_at_k,
    percentile,
    precision_at_k,
    precision_ceiling,
    recall_at_k,
)


def test_precision_at_k():
    assert precision_at_k(["a", "x", "b", "y", "z"], {"a", "b"}, 5) == pytest.approx(0.4)
    assert precision_at_k(["a"], {"a"}, 5) == pytest.approx(0.2)  # short lists still divide by k
    with pytest.raises(ValueError):
        precision_at_k(["a"], {"a"}, 0)


def test_recall_at_k():
    assert recall_at_k(["a", "x", "b"], {"a", "b", "c", "d"}, 10) == pytest.approx(0.5)
    assert recall_at_k(["x"] * 10 + ["a"], {"a"}, 10) == 0
    assert math.isnan(recall_at_k(["a"], set(), 10))


def test_precision_ceiling():
    assert precision_ceiling(3, 5) == pytest.approx(0.6)
    assert precision_ceiling(8, 5) == 1


def test_overlap_at_k():
    assert overlap_at_k(["a", "b", "c"], ["c", "b", "z"], 3) == pytest.approx(2 / 3)
    assert overlap_at_k(["a", "b"], ["a", "b"], 2) == 1


def test_percentile_matches_linear_interpolation():
    xs = [10, 20, 30, 40, 50]
    assert percentile(xs, 50) == 30
    assert percentile(xs, 95) == pytest.approx(48)
    assert percentile([5], 95) == 5
    assert math.isnan(percentile([], 50))


def test_mean_ignores_nan():
    assert mean([1, math.nan, 3]) == 2
    assert math.isnan(mean([math.nan]))
