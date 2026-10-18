from typing import Any

from fundfinder.exposure import exposure_vector
from fundfinder.models import Fund
from fundfinder.profile import build_profile


def to_document(fund: Fund) -> dict[str, Any]:
    """MongoDB document: source fields plus the two derived search fields."""
    # _id first: MongoDB stores it first, and a differently ordered replacement
    # counts as a modification (which would re-trigger embedding).
    doc = {"_id": fund.id, **fund.model_dump(exclude={"id"})}
    doc["profile"] = build_profile(fund)
    doc["exposure_vector"] = exposure_vector(fund)
    return doc
