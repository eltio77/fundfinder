import pytest

from fundfinder.intent import Sort, cost_intent, resolve_sort, wants_high_cost, wants_low_cost


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
    assert not wants_high_cost(q)


@pytest.mark.parametrize(
    "q",
    [
        "high cost funds",
        "highest cost equity",
        "hightest cost",  # common typo
        "Highest-cost active fund",
        "higher fees",
        "high charges",
        "the most expensive tracker",
        "priciest UK fund",
    ],
)
def test_detects_high_cost(q):
    assert wants_high_cost(q)
    assert not wants_low_cost(q)


@pytest.mark.parametrize("q", ["high yield bonds", "high income UK equity", "highly rated"])
def test_high_without_cost_word_is_not_cost(q):
    assert cost_intent(q) is None


def test_first_mention_wins_when_both():
    assert cost_intent("low cost, not expensive") is Sort.cost
    assert cost_intent("expensive rather than cheap") is Sort.cost_desc


@pytest.mark.parametrize(
    ("q", "order"),
    [
        ("not too expensive", Sort.cost),
        ("not high cost, global equity", Sort.cost),
        ("isn't expensive", Sort.cost),
        ("not cheap", None),  # not a request for any order
        ("not cheap, most expensive first", Sort.cost_desc),
    ],
)
def test_negated_cost_words(q, order):
    assert cost_intent(q) is order


def test_resolve_sort():
    assert resolve_sort(Sort.auto, "lowest cost tracker") is Sort.cost
    assert resolve_sort(Sort.auto, "japan value") is Sort.relevance
    assert resolve_sort(Sort.relevance, "lowest cost tracker") is Sort.relevance
    assert resolve_sort(Sort.cost, "japan value") is Sort.cost
    assert resolve_sort(Sort.auto, "highest cost japan") is Sort.cost_desc
