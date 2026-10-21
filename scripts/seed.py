"""Load the synthetic fund universe into Atlas (the `funds` collection). Idempotent:
upserts every fund and removes any fund no longer in the source. Never drops the
collection, so search indexes survive a re-seed (autoEmbed re-embeds only changed
profiles).

    uv run python -m scripts.seed [--n 300] [--seed 42] [--dry-run]
"""

import argparse
import asyncio
import json
import sys
from collections import Counter

from pymongo import ReplaceOne

from fundfinder.config import get_settings
from fundfinder.data.source import FundSource
from fundfinder.data.synthetic import DEFAULT_N, DEFAULT_SEED, SyntheticSource
from fundfinder.db import FUNDS, make_client
from fundfinder.documents import to_document


def summarise(docs: list[dict]) -> str:
    clusters = Counter(d["cluster_id"].split("_")[0] for d in docs if d["cluster_id"])
    by_class = Counter(d["asset_class"] for d in docs)
    passive = sum(d["is_passive"] for d in docs)
    return (
        f"{len(docs)} funds | passive={passive} | "
        f"clusters: trackers={clusters['trk']} near-dupes={clusters['act']} "
        f"outliers={clusters['outlier']} | by asset class: {dict(by_class)}"
    )


async def seed(source: FundSource) -> None:
    docs = [to_document(f) for f in source.fetch()]
    print(summarise(docs))
    await write(docs, FUNDS)


async def write(docs: list[dict], collection: str) -> None:
    """Upsert `docs` into `collection` and remove any fund not among them."""
    settings = get_settings()
    client = make_client(settings)
    try:
        coll = client[settings.mongodb_db][collection]
        result = await coll.bulk_write(
            [ReplaceOne({"_id": d["_id"]}, d, upsert=True) for d in docs]
        )
        removed = await coll.delete_many({"_id": {"$nin": [d["_id"] for d in docs]}})
        print(
            f"upserted={result.upserted_count} modified={result.modified_count} "
            f"removed={removed.deleted_count} total={await coll.count_documents({})}"
        )
    finally:
        await client.close()


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--n", type=int, default=DEFAULT_N)
    parser.add_argument("--seed", type=int, default=DEFAULT_SEED)
    parser.add_argument("--dry-run", action="store_true", help="print a sample, don't write")
    args = parser.parse_args()

    source = SyntheticSource(args.n, args.seed)
    if args.dry_run:
        docs = [to_document(f) for f in source.fetch()]
        print(summarise(docs))
        sample = {k: v for k, v in docs[0].items() if k != "exposure_vector"}
        print(json.dumps(sample, indent=2))
        return 0
    asyncio.run(seed(source))
    return 0


if __name__ == "__main__":
    sys.exit(main())
