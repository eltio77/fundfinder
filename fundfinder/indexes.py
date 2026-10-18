"""Atlas Vector Search index definitions and an idempotent `ensure_indexes`.

Free clusters allow 3 search/vector indexes in total; we use 2.
"""

import asyncio
import time
from typing import Any

from pymongo.asynchronous.collection import AsyncCollection
from pymongo.operations import SearchIndexModel

from fundfinder.taxonomy import EXPOSURE_DIMS

PROFILE_INDEX = "profile_auto"
EXPOSURE_INDEX = "exposure_vec"

FILTER_FIELDS = ("asset_class", "ia_sector", "ocf", "is_passive")


def _filters() -> list[dict[str, Any]]:
    return [{"type": "filter", "path": p} for p in FILTER_FIELDS]


def index_definitions(embed_model: str) -> dict[str, dict[str, Any]]:
    return {
        PROFILE_INDEX: {
            "fields": [
                {"type": "autoEmbed", "modality": "text", "path": "profile", "model": embed_model},
                *_filters(),
            ]
        },
        EXPOSURE_INDEX: {
            "fields": [
                {
                    "type": "vector",
                    "path": "exposure_vector",
                    "numDimensions": EXPOSURE_DIMS,
                    "similarity": "cosine",
                },
                *_filters(),
            ]
        },
    }


def definition_matches(desired: dict[str, Any], actual: dict[str, Any] | None) -> bool:
    """True if every desired field appears in `actual` with the same settings.
    Atlas may add defaults to stored definitions, so compare only what we set."""
    if not actual:
        return False
    actual_fields = actual.get("fields", [])
    if len(actual_fields) != len(desired["fields"]):
        return False
    return all(
        any(all(af.get(k) == v for k, v in df.items()) for af in actual_fields)
        for df in desired["fields"]
    )


async def _existing(coll: AsyncCollection) -> dict[str, dict[str, Any]]:
    cursor = await coll.list_search_indexes()
    return {idx["name"]: idx for idx in await cursor.to_list()}


async def ensure_indexes(coll: AsyncCollection, embed_model: str) -> dict[str, str]:
    """Create missing indexes and update changed ones. Returns name -> action."""
    existing = await _existing(coll)
    actions = {}
    for name, definition in index_definitions(embed_model).items():
        current = existing.get(name)
        if current is None:
            await coll.create_search_index(
                SearchIndexModel(definition=definition, name=name, type="vectorSearch")
            )
            actions[name] = "created"
        elif not definition_matches(definition, current.get("latestDefinition")):
            await coll.update_search_index(name, definition)
            actions[name] = "updated"
        else:
            actions[name] = "unchanged"
    return actions


async def wait_until_ready(
    coll: AsyncCollection, names: list[str], timeout_s: float = 900, poll_s: float = 10
) -> dict[str, dict[str, Any]]:
    deadline = time.monotonic() + timeout_s
    while True:
        existing = await _existing(coll)
        states = {n: existing.get(n, {}) for n in names}
        failed = [n for n, s in states.items() if s.get("status") == "FAILED"]
        if failed:
            raise RuntimeError(f"index build failed: {failed}: {states}")
        if all(s.get("status") == "READY" and s.get("queryable") for s in states.values()):
            return states
        if time.monotonic() > deadline:
            raise TimeoutError(f"indexes not ready after {timeout_s}s: {states}")
        print("  " + ", ".join(f"{n}={s.get('status')}" for n, s in states.items()))
        await asyncio.sleep(poll_s)
