"""Create or update the vector search indexes, then wait until they're queryable.
Idempotent; run after seeding (the collection must exist).

    uv run python -m scripts.indexes [--no-wait] [--collection funds_morningstar]
"""

import argparse
import asyncio
import sys

from fundfinder.config import get_settings
from fundfinder.db import make_client
from fundfinder.indexes import ensure_indexes, index_definitions, wait_until_ready


async def run(wait: bool, timeout_s: float, collection: str | None) -> int:
    settings = get_settings()
    client = make_client(settings)
    try:
        coll = client[settings.mongodb_db][collection or settings.funds_collection]
        actions = await ensure_indexes(coll, settings.embed_model)
        for name, action in actions.items():
            print(f"{name}: {action}")
        if wait:
            print("waiting for indexes to be READY ...")
            try:
                await wait_until_ready(
                    coll, list(index_definitions(settings.embed_model)), timeout_s=timeout_s
                )
            except TimeoutError:
                # Usually Voyage throttling (free keys: 3 RPM / 10K TPM); the build continues.
                print(
                    f"not READY after {timeout_s:.0f}s; the build keeps going in the background. "
                    "Re-run with a longer --timeout, or check again later."
                )
                return 1
            print("all indexes READY")
        return 0
    finally:
        await client.close()


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--no-wait", action="store_true")
    parser.add_argument(
        "--timeout", type=float, default=1800, help="seconds to wait (default 1800)"
    )
    parser.add_argument("--collection", help="default: FUNDS_COLLECTION (funds_morningstar)")
    args = parser.parse_args()
    return asyncio.run(
        run(wait=not args.no_wait, timeout_s=args.timeout, collection=args.collection)
    )


if __name__ == "__main__":
    sys.exit(main())
