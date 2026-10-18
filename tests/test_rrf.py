import pytest

from fundfinder.rrf import reciprocal_rank_fusion


def test_single_list_preserves_order():
    fused = reciprocal_rank_fusion([["a", "b", "c"]])
    assert [x for x, _ in fused] == ["a", "b", "c"]
    assert fused[0][1] == pytest.approx(1 / 61)


def test_item_in_both_lists_beats_item_top_of_one():
    # b is 2nd in both; a is 1st in one list only.
    fused = dict(reciprocal_rank_fusion([["a", "b"], ["c", "b"]]))
    assert fused["b"] == pytest.approx(2 / 62)
    assert fused["b"] > fused["a"] == fused["c"]


def test_scores_are_sum_of_reciprocal_ranks():
    fused = dict(reciprocal_rank_fusion([["x", "y"], ["y", "x"]], k=10))
    assert fused["x"] == pytest.approx(1 / 11 + 1 / 12)
    assert fused["x"] == pytest.approx(fused["y"])


def test_ties_keep_first_seen_order():
    fused = reciprocal_rank_fusion([["a", "b"], ["b", "a"]])
    assert [x for x, _ in fused] == ["a", "b"]


def test_empty_inputs():
    assert reciprocal_rank_fusion([]) == []
    assert reciprocal_rank_fusion([[], []]) == []


def test_k_must_be_positive():
    with pytest.raises(ValueError):
        reciprocal_rank_fusion([["a"]], k=0)
