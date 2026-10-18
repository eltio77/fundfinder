from collections import Counter

import pytest

from fundfinder.data.synthetic import NEAR_DUPES, OUTLIERS, TRACKERS, generate_funds
from fundfinder.documents import to_document


@pytest.fixture(scope="module")
def funds():
    return generate_funds()


def test_deterministic():
    assert generate_funds(n=120, seed=7) == generate_funds(n=120, seed=7)


def test_count_and_unique_ids_and_names(funds):
    assert len(funds) == 300
    assert len({f.id for f in funds}) == 300
    assert len({f.name for f in funds}) == 300


def test_clusters_present_in_full(funds):
    sizes = Counter(f.cluster_id for f in funds if f.cluster_id)
    for spec in TRACKERS + NEAR_DUPES:
        assert sizes[spec.key] == spec.size
    for o in OUTLIERS:
        assert sizes[o.key] == 1


def test_tracker_clusters_share_index(funds):
    for spec in TRACKERS:
        members = [f for f in funds if f.cluster_id == spec.key]
        assert {f.tracked_index for f in members} == {spec.index}
        assert all(f.is_passive for f in members)
        assert len({f.provider for f in members}) == spec.size


def test_background_trackers_never_duplicate_an_index(funds):
    background = Counter(f.tracked_index for f in funds if f.is_passive and not f.cluster_id)
    assert all(count == 1 for count in background.values())


def test_weights_are_sane(funds):
    for f in funds:
        assert sum(f.region_weights.values()) == pytest.approx(1.0, abs=0.005)
        assert sum(f.asset_class_weights.values()) == pytest.approx(1.0, abs=0.005)
        assert len(f.top_holdings) == 10
        weights = [h.weight for h in f.top_holdings]
        assert weights == sorted(weights, reverse=True)


def test_too_small_n_rejected():
    with pytest.raises(ValueError):
        generate_funds(n=10)


def test_document_has_derived_fields(funds):
    doc = to_document(funds[0])
    assert doc["_id"] == funds[0].id and "id" not in doc
    # Must match MongoDB's stored order, or every re-seed counts as a modification.
    assert next(iter(doc)) == "_id"
    assert doc["profile"].startswith(funds[0].name)
    assert len(doc["exposure_vector"]) == 26
