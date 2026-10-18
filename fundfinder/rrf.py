from collections.abc import Hashable, Sequence

DEFAULT_K = 60


def reciprocal_rank_fusion[T: Hashable](
    rankings: Sequence[Sequence[T]], k: int = DEFAULT_K
) -> list[tuple[T, float]]:
    """Fuse ranked lists: score(d) = sum over lists of 1 / (k + rank), rank from 1.

    Items missing from a list contribute nothing for it. Ties keep the order in
    which items were first seen (earlier lists, higher ranks first).
    """
    if k <= 0:
        raise ValueError("k must be positive")
    scores: dict[T, float] = {}
    for ranking in rankings:
        for rank, item in enumerate(ranking, start=1):
            scores[item] = scores.get(item, 0.0) + 1.0 / (k + rank)
    return sorted(scores.items(), key=lambda kv: -kv[1])
