"""Create or update the vector search indexes, then wait until they're queryable.
Idempotent; run after seeding (the collection must exist).

    uv run python -m scripts.indexes [--no-wait]
"""

import argparse
import asyncio
import sys

from fundfinder.config import get_settings
from fundfinder.db import FUNDS, make_client
from fundfinder.indexes import ensure_indexes, index_definitions, wait_until_ready


async def run(wait: bool) -> None:
    settings = get_settings()
    client = make_client(settings)
    try:
        coll = client[settings.mongodb_db][FUNDS]
        actions = await ensure_indexes(coll, settings.embed_model)
        for name, action in actions.items():
            print(f"{name}: {action}")
        if wait:
            print("waiting for indexes to be READY ...")
            await wait_until_ready(coll, list(index_definitions(settings.embed_model)))
            print("all indexes READY")
    finally:
        await client.close()


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--no-wait", action="store_true")
    asyncio.run(run(wait=not parser.parse_args().no_wait))
    return 0


if __name__ == "__main__":
    sys.exit(main())
