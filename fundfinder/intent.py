"""Cheap, rule-based reading of search intent that embeddings don't capture.

A vector search for "lowest cost tracker" finds trackers, but similarity can't
order them by price: "low cost" is a ranking instruction, not a description.
"""

import re
from enum import StrEnum

# "low cost", "lowest-cost", "lower fees", "low charges", "low OCF", "cheap", "cheapest".
# "low" alone isn't enough ("low risk", "low volatility").
_LOW_COST = re.compile(
    r"\b(?:low(?:er|est)?[\s-]+(?:costs?|fees?|charges?|ocf)|cheap(?:er|est)?)\b",
    re.IGNORECASE,
)


class Sort(StrEnum):
    auto = "auto"  # cost if the query asks for low cost, otherwise relevance
    relevance = "relevance"
    cost = "cost"


def wants_low_cost(q: str) -> bool:
    return _LOW_COST.search(q) is not None


def resolve_sort(sort: Sort, q: str) -> Sort:
    if sort is Sort.auto:
        return Sort.cost if wants_low_cost(q) else Sort.relevance
    return sort
