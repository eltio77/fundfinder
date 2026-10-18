"""One-off probe: does Atlas Automated Embedding work on this cluster?

Creates a scratch collection with an autoEmbed index, runs an ANN and an exact
query, prints what worked, then drops the collection (and its index).

    uv run python -m scripts.check_autoembed
"""

import asyncio
import sys
import time

from pymongo.errors import OperationFailure
from pymongo.operations import SearchIndexModel

from fundfinder.config import get_settings
from fundfinder.db import make_client

PROBE = "_autoembed_probe"
INDEX = "probe_auto"
DOCS = [
    {"_id": 1, "text": "FTSE 100 index tracker with large UK companies", "kind": "passive"},
    {"_id": 2, "text": "Global technology growth fund investing in US software", "kind": "active"},
    {"_id": 3, "text": "Short dated UK government bond fund", "kind": "passive"},
]
TIMEOUT_S = 600


async def wait_queryable(coll) -> dict:
    deadline = time.monotonic() + TIMEOUT_S
    while time.monotonic() < deadline:
        cursor = await coll.list_search_indexes(INDEX)
        idx = (await cursor.to_list())[0]
        print(f"  status={idx.get('status')} queryable={idx.get('queryable')}")
        if idx.get("queryable"):
            return idx
        if idx.get("status") == "FAILED":
            raise RuntimeError(f"index build failed: {idx}")
        await asyncio.sleep(10)
    raise TimeoutError("index not queryable in time")


async def run_query(coll, model: str, query, exact: bool) -> list[dict]:
    stage = {"index": INDEX, "path": "text", "query": query, "model": model, "limit": 2}
    if exact:
        stage["exact"] = True
    else:
        stage["numCandidates"] = 10
    pipeline = [
        {"$vectorSearch": stage},
        {"$project": {"text": 1, "score": {"$meta": "vectorSearchScore"}}},
    ]
    cursor = await coll.aggregate(pipeline)
    return await cursor.to_list()


async def main() -> int:
    settings = get_settings()
    client = make_client(settings)
    db = client[settings.mongodb_db]
    coll = db[PROBE]
    try:
        info = await client.admin.command("buildInfo")
        print(f"MongoDB server version: {info['version']}")

        await coll.drop()
        await coll.insert_many(DOCS)
        definition = {
            "fields": [
                {
                    "type": "autoEmbed",
                    "modality": "text",
                    "path": "text",
                    "model": settings.embed_model,
                },
                {"type": "filter", "path": "kind"},
            ]
        }
        print(f"Creating autoEmbed index with model={settings.embed_model} ...")
        try:
            await coll.create_search_index(
                SearchIndexModel(definition=definition, name=INDEX, type="vectorSearch")
            )
        except OperationFailure as exc:
            print(f"RESULT: autoEmbed index creation REJECTED: {exc.details or exc}")
            return 1
        await wait_queryable(coll)

        text = "tracker fund for UK blue chips"
        working_shape = None
        for label, query in (("string", text), ("{text: ...}", {"text": text})):
            try:
                hits = await run_query(coll, settings.embed_model, query, exact=False)
                print(f"ANN query with query as {label}: OK -> {hits}")
                working_shape = query
                break
            except OperationFailure as exc:
                print(f"ANN query with query as {label}: FAILED -> {exc.details or exc}")
        if working_shape is None:
            print("RESULT: index built but text queries fail")
            return 1

        try:
            hits = await run_query(coll, settings.embed_model, working_shape, exact=True)
            print(f"Exact (ENN) query: OK -> {hits}")
        except OperationFailure as exc:
            print(f"Exact (ENN) query: FAILED -> {exc.details or exc}")

        print("RESULT: autoEmbed works on this cluster")
        return 0
    finally:
        await coll.drop()
        await client.close()


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
