"""Cheap, rule-based reading of search intent that embeddings don't capture.

A vector search for "lowest cost tracker" finds trackers, but similarity can't
order them by price: "low cost" is a ranking instruction, not a description.
"""

import re
from enum import StrEnum

_COST_WORD = r"(?:costs?|fees?|charges?|ocf)"

# "low cost", "lowest-cost", "lower fees", "low charges", "low OCF", "cheap", "cheapest".
# "low" alone isn't enough ("low risk", "low volatility").
_LOW_COST = re.compile(
    rf"\b(?:low(?:er|est)?[\s-]+{_COST_WORD}|cheap(?:er|est)?)\b",
    re.IGNORECASE,
)

# "high cost", "highest-cost" (and the "hightest" typo), "higher fees", "most expensive",
# "priciest". "high" alone isn't enough ("high yield", "high income").
_HIGH_COST = re.compile(
    rf"\b(?:high(?:er|e?st|test)?[\s-]+{_COST_WORD}|expensive|pricier|priciest|pricey)\b",
    re.IGNORECASE,
)


# "not cheap", "not too expensive", "isn't high cost": the cost word is negated.
_NEGATED = re.compile(
    r"\b(?:not|never|isn['’]?t|aren['’]?t)\s+(?:too\s+|very\s+|so\s+|that\s+|overly\s+)?$",
    re.IGNORECASE,
)


class Sort(StrEnum):
    auto = "auto"  # by cost if the query asks for low or high cost, otherwise relevance
    relevance = "relevance"
    cost = "cost"  # ascending OCF
    cost_desc = "cost_desc"  # descending OCF


def cost_intent(q: str) -> Sort | None:
    """Sort.cost / Sort.cost_desc if q asks for low / high cost. If it asks for both,
    the first mention wins. A negated mention counts as its opposite when that is
    still a request about cost ("not expensive" = cheapest first), but "not cheap"
    asks for no particular order."""
    mentions = sorted(
        [(m.start(), Sort.cost) for m in _LOW_COST.finditer(q)]
        + [(m.start(), Sort.cost_desc) for m in _HIGH_COST.finditer(q)]
    )
    for start, order in mentions:
        if not _NEGATED.search(q[:start]):
            return order
        if order is Sort.cost_desc:
            return Sort.cost
    return None


def wants_low_cost(q: str) -> bool:
    return cost_intent(q) is Sort.cost


def wants_high_cost(q: str) -> bool:
    return cost_intent(q) is Sort.cost_desc


def resolve_sort(sort: Sort, q: str) -> Sort:
    if sort is Sort.auto:
        return cost_intent(q) or Sort.relevance
    return sort
