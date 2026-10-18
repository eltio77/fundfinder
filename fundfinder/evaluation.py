"""Retrieval metrics for the evaluation script. Pure functions, no I/O."""

import math
from collections.abc import Sequence


def precision_at_k(ranked: Sequence[str], relevant: set[str], k: int) -> float:
    """Share of the top k that are relevant. Denominator is k even if fewer were returned."""
    if k <= 0:
        raise ValueError("k must be positive")
    return sum(1 for r in ranked[:k] if r in relevant) / k


def recall_at_k(ranked: Sequence[str], relevant: set[str], k: int) -> float:
    """Share of the relevant items found in the top k. NaN when there is nothing to find."""
    if not relevant:
        return math.nan
    return sum(1 for r in ranked[:k] if r in relevant) / len(relevant)


def precision_ceiling(n_relevant: int, k: int) -> float:
    """Best achievable precision@k when only n_relevant items exist."""
    return min(n_relevant, k) / k


def overlap_at_k(a: Sequence[str], b: Sequence[str], k: int) -> float:
    """|top-k(a) ∩ top-k(b)| / k: how far ANN agrees with exact search."""
    if k <= 0:
        raise ValueError("k must be positive")
    return len(set(a[:k]) & set(b[:k])) / k


def percentile(values: Sequence[float], p: float) -> float:
    """Linear-interpolated percentile (p in 0..100), matching numpy's default."""
    if not values:
        return math.nan
    xs = sorted(values)
    pos = (len(xs) - 1) * p / 100
    lo, hi = math.floor(pos), math.ceil(pos)
    return xs[lo] + (xs[hi] - xs[lo]) * (pos - lo)


def mean(values: Sequence[float]) -> float:
    clean = [v for v in values if not math.isnan(v)]
    return sum(clean) / len(clean) if clean else math.nan
