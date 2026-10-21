"""Load real UK OEICs from Morningstar into their own collection (funds_morningstar by
default), leaving the synthetic `funds` collection alone. Idempotent, like scripts.seed.

    uv run python -m scripts.seed_morningstar [--limit 300 | --all] [--cache DIR] [--dry-run]

Then build its indexes and point the app at it:

    uv run python -m scripts.indexes --collection funds_morningstar
    FUNDS_COLLECTION=funds_morningstar uv run uvicorn fundfinder.main:app
"""

import argparse
import asyncio
import json
import sys
from collections import Counter
from pathlib import Path

from fundfinder.data.morningstar import DEFAULT_LIMIT, DEFAULT_SEED, MorningstarSource
from fundfinder.db import MORNINGSTAR_FUNDS
from fundfinder.documents import to_document
from scripts.seed import write


def summarise(docs: list[dict]) -> str:
    by_class = Counter(d["asset_class"] for d in docs)
    passive = sum(d["is_passive"] for d in docs)
    sectors = len({d["ia_sector"] for d in docs})
    return (
        f"{len(docs)} funds | passive={passive} | IA sectors={sectors} | "
        f"by asset class: {dict(by_class)}"
    )


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    size = parser.add_mutually_exclusive_group()
    size.add_argument("--limit", type=int, default=DEFAULT_LIMIT, help="funds to load")
    size.add_argument("--all", action="store_true", help="load every fund, no cap")
    parser.add_argument("--seed", type=int, default=DEFAULT_SEED, help="which funds get picked")
    parser.add_argument("--collection", default=MORNINGSTAR_FUNDS)
    parser.add_argument("--cache", type=Path, help="keep API responses here for re-runs")
    parser.add_argument("--dry-run", action="store_true", help="print a sample, don't write")
    args = parser.parse_args()

    source = MorningstarSource(None if args.all else args.limit, args.seed, args.cache)
    docs = [to_document(f) for f in source.fetch()]
    print(summarise(docs))
    if source.skipped:
        print(f"skipped {len(source.skipped)}: {dict(Counter(source.skipped.values()))}")
    if args.dry_run:
        sample = {k: v for k, v in docs[0].items() if k != "exposure_vector"}
        print(json.dumps(sample, indent=2, ensure_ascii=False))
        return 0
    asyncio.run(write(docs, args.collection))
    return 0


if __name__ == "__main__":
    sys.exit(main())
