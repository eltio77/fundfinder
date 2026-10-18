import pytest

from fundfinder.intent import Sort, resolve_sort, wants_low_cost


@pytest.mark.parametrize(
    "q",
    [
        "low cost global equity",
        "lowest cost S&P 500 tracker",
        "Low-cost bond fund",
        "lower fees please",
        "funds with low charges",
        "low OCF index fund",
        "cheapest world tracker",
        "a cheap fund that follows the US stock market",
    ],
)
def test_detects_low_cost(q):
    assert wants_low_cost(q)


@pytest.mark.parametrize(
    "q",
    [
        "low risk UK government bonds",
        "low volatility equity income",
        "costco and walmart",  # word boundaries
        "UK smaller companies",
        "",
    ],
)
def test_ignores_other_queries(q):
    assert not wants_low_cost(q)


def test_resolve_sort():
    assert resolve_sort(Sort.auto, "lowest cost tracker") is Sort.cost
    assert resolve_sort(Sort.auto, "japan value") is Sort.relevance
    assert resolve_sort(Sort.relevance, "lowest cost tracker") is Sort.relevance
    assert resolve_sort(Sort.cost, "japan value") is Sort.cost
