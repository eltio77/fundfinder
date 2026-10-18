"""Evaluate similarity search against the deliberate clusters in the synthetic data.

For ~20 labelled query funds (members of tracker and near-duplicate clusters; the
expected neighbours are the other members of the same cluster) this reports:

  * precision@5 and recall@10 per mode (text, exposure, both)
  * ANN vs exact (ENN) overlap@10 at several numCandidates values
  * p50 / p95 latency per call type, measured from this machine
  * top-1 similarity of outliers vs clustered funds

"both" is fused locally from the text and exposure lists with the same RRF the
API uses (each list 2 x limit deep), and cross-checked against real
mode=both calls. Writes a markdown report and the raw numbers as JSON.

    uv run python -m scripts.eval [--out reports/eval.md] [--per-cluster 2]
"""

import argparse
import asyncio
import json
import math
import platform
import sys
import time
from collections import defaultdict
from dataclasses import asdict, dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from pymongo.errors import OperationFailure

from fundfinder.config import get_settings
from fundfinder.db import FUNDS, make_client
from fundfinder.evaluation import (
    mean,
    overlap_at_k,
    percentile,
    precision_at_k,
    precision_ceiling,
    recall_at_k,
)
from fundfinder.rrf import reciprocal_rank_fusion
from fundfinder.search import (
    FUSION_DEPTH_FACTOR,
    FundSearch,
    Hit,
    Mode,
    default_num_candidates,
)

LIMIT = 10
P_K, R_K = 5, 10
DEFAULT_NCS = [10, 20, 50, 100, 200, 500]
MODES = ("text", "exposure", "both")
KIND_LABELS = {"trk": "Index trackers", "act": "Near-duplicate active funds"}
MAX_RETRIES = 6


@dataclass
class Call:
    kind: str  # e.g. "text", "exposure", "both (API)"
    search: str  # "ANN nc=200" or "exact"
    ms: float


@dataclass
class QueryResult:
    fund_id: str
    name: str
    cluster_id: str
    expected: list[str]
    ranked: dict[str, list[str]]
    precision: dict[str, float]
    recall: dict[str, float]
    overlap: dict[str, dict[str, float]] = field(default_factory=dict)  # mode -> nc -> overlap
    fused_matches_api: bool | None = None


class Runner:
    def __init__(self, search: FundSearch) -> None:
        self.search = search
        self.calls: list[Call] = []
        self.rate_limited = 0

    async def _timed(self, kind: str, label: str, coro_fn) -> Any:
        """Run one search, retrying on Voyage throttling; only the successful attempt is timed."""
        for attempt in range(MAX_RETRIES):
            t0 = time.perf_counter()
            try:
                result = await coro_fn()
            except OperationFailure as exc:
                if "rate limit" not in str(exc).lower() or attempt == MAX_RETRIES - 1:
                    raise
                self.rate_limited += 1
                wait = 15 * (attempt + 1)
                print(f"    rate limited; retrying in {wait}s", flush=True)
                await asyncio.sleep(wait)
                continue
            self.calls.append(Call(kind, label, (time.perf_counter() - t0) * 1000))
            return result
        raise RuntimeError("unreachable")

    async def neighbours(
        self, fund: dict, mode: str, limit: int, nc: int | None = None, exact: bool = False
    ) -> list[Hit]:
        label = "exact" if exact else f"ANN nc={nc}"
        return await self._timed(
            mode,
            label,
            lambda: self.search.neighbours(
                fund, Mode(mode), limit=limit, num_candidates=nc, filters=None, exact=exact
            ),
        )

    async def api_both(self, fund_id: str, nc: int) -> list[Hit]:
        return await self._timed(
            "both (API)",
            f"ANN nc={nc}",
            lambda: self.search.similar(fund_id, Mode.both, limit=LIMIT, num_candidates=nc),
        )


def ids(hits: list[Hit]) -> list[str]:
    return [h.id for h in hits]


async def evaluate(per_cluster: int, ncs: list[int]) -> dict[str, Any]:
    settings = get_settings()
    client = make_client(settings)
    try:
        coll = client[settings.mongodb_db][FUNDS]
        runner = Runner(FundSearch(coll, settings.embed_model))
        docs = await (await coll.aggregate([{"$sort": {"_id": 1}}])).to_list()
        by_id = {d["_id"]: d for d in docs}
        clusters: dict[str, list[str]] = defaultdict(list)
        for d in docs:
            if d.get("cluster_id"):
                clusters[d["cluster_id"]].append(d["_id"])

        depth = LIMIT * FUSION_DEPTH_FACTOR
        main_nc = default_num_candidates(LIMIT)
        queries = [
            (cid, fid)
            for cid in sorted(clusters)
            if cid.split("_")[0] in KIND_LABELS
            for fid in clusters[cid][:per_cluster]
        ]
        outliers = sorted(
            (cid, members[0]) for cid, members in clusters.items() if cid.startswith("outlier_")
        )
        print(
            f"{len(queries)} query funds, {len(outliers)} outliers, {len(docs)} funds", flush=True
        )

        results: list[QueryResult] = []
        top1: dict[str, dict[str, list[float]]] = {"clustered": defaultdict(list)}
        for i, (cid, fid) in enumerate(queries, start=1):
            fund = by_id[fid]
            print(f"[{i}/{len(queries)}] {fid} {fund['name']} ({cid})", flush=True)
            expected = [m for m in clusters[cid] if m != fid]
            text = await runner.neighbours(fund, "text", depth, main_nc)
            exposure = await runner.neighbours(fund, "exposure", depth, main_nc)
            fused = [f for f, _ in reciprocal_rank_fusion([ids(text), ids(exposure)])][:LIMIT]
            ranked = {"text": ids(text)[:LIMIT], "exposure": ids(exposure)[:LIMIT], "both": fused}
            for mode, hits in (("text", text), ("exposure", exposure)):
                if hits:
                    top1["clustered"][mode].append(hits[0].score)

            rel = set(expected)
            res = QueryResult(
                fund_id=fid,
                name=fund["name"],
                cluster_id=cid,
                expected=expected,
                ranked=ranked,
                precision={m: precision_at_k(r, rel, P_K) for m, r in ranked.items()},
                recall={m: recall_at_k(r, rel, R_K) for m, r in ranked.items()},
            )

            # Cross-check the local fusion against the API's mode=both (also times it).
            api = await runner.api_both(fid, main_nc)
            res.fused_matches_api = ids(api or []) == fused

            for mode in ("text", "exposure"):
                exact = ids(await runner.neighbours(fund, mode, LIMIT, exact=True))
                res.overlap[mode] = {}
                for nc in ncs:
                    ann = ids(await runner.neighbours(fund, mode, LIMIT, nc))
                    res.overlap[mode][str(nc)] = overlap_at_k(ann, exact, LIMIT)
            results.append(res)

        outlier_rows = []
        for cid, fid in outliers:
            fund = by_id[fid]
            print(f"[outlier] {fid} {fund['name']}", flush=True)
            text = await runner.neighbours(fund, "text", LIMIT, main_nc)
            exposure = await runner.neighbours(fund, "exposure", LIMIT, main_nc)
            outlier_rows.append(
                {
                    "fund_id": fid,
                    "name": fund["name"],
                    "cluster_id": cid,
                    "text_top1": text[0].score if text else math.nan,
                    "text_top1_name": text[0].name if text else "",
                    "exposure_top1": exposure[0].score if exposure else math.nan,
                    "exposure_top1_name": exposure[0].name if exposure else "",
                }
            )

        return {
            "meta": {
                "generated": datetime.now(UTC).strftime("%Y-%m-%d %H:%M UTC"),
                "database": settings.mongodb_db,
                "embed_model": settings.embed_model,
                "funds": len(docs),
                "limit": LIMIT,
                "fusion_depth": depth,
                "default_num_candidates": main_nc,
                "num_candidates_grid": ncs,
                "client": (
                    f"{platform.system()} {platform.machine()}, Python {platform.python_version()}"
                ),
                "rate_limited_retries": runner.rate_limited,
            },
            "queries": [asdict(r) for r in results],
            "outliers": outlier_rows,
            "clustered_top1": {m: mean(v) for m, v in top1["clustered"].items()},
            "calls": [asdict(c) for c in runner.calls],
        }
    finally:
        await client.close()


# ---------------------------------------------------------------------- report


def fmt(x: float, digits: int = 2) -> str:
    return "–" if x is None or (isinstance(x, float) and math.isnan(x)) else f"{x:.{digits}f}"


def render(data: dict[str, Any]) -> str:
    meta, queries = data["meta"], data["queries"]

    def group(kind: str | None) -> list[dict]:
        return [q for q in queries if kind is None or q["cluster_id"].startswith(kind + "_")]

    def ceiling(qs: list[dict]) -> float:
        return mean([precision_ceiling(len(q["expected"]), P_K) for q in qs])

    lines = [
        "# Fund Finder: similarity evaluation",
        "",
        f"Generated {meta['generated']} against `{meta['database']}` "
        f"({meta['funds']} synthetic funds), text model `{meta['embed_model']}`. "
        f"Client: {meta['client']}.",
        "",
        f"**Method.** {len(queries)} query funds, {len(set(q['cluster_id'] for q in queries))} "
        "deliberate clusters. For each query fund, the expected neighbours are the other members "
        "of its cluster: 4 for index trackers, 3 for near-duplicates. Each mode returns the "
        f"top {meta['limit']}, excluding the fund itself. `both` = RRF (k = 60) over the text and "
        f"exposure lists, each {meta['fusion_depth']} deep, all ANN with numCandidates = "
        f"{meta['default_num_candidates']} (20 × limit).",
        "",
        "## Retrieval quality",
        "",
        f"Precision@{P_K} can't reach 1, because clusters have only 3–4 other members. The ceiling "
        "column is the best achievable value.",
        "",
        f"| Query set | n | Ceiling P@{P_K} | "
        + " | ".join(f"{m} P@{P_K}" for m in MODES)
        + " | "
        + " | ".join(f"{m} R@{R_K}" for m in MODES)
        + " |",
        "|---|---:|---:|" + "---:|" * (2 * len(MODES)),
    ]
    for kind, label in [(None, "**All**"), *KIND_LABELS.items()]:
        qs = group(kind)
        if not qs:
            continue
        p = [fmt(mean([q["precision"][m] for q in qs])) for m in MODES]
        r = [fmt(mean([q["recall"][m] for q in qs])) for m in MODES]
        lines.append(f"| {label} | {len(qs)} | {fmt(ceiling(qs))} | " + " | ".join(p + r) + " |")

    lines += [
        "",
        f"### Recall@{R_K} by cluster",
        "",
        "| Cluster | Queries | text | exposure | both |",
        "|---|---:|---:|---:|---:|",
    ]
    by_cluster: dict[str, list[dict]] = defaultdict(list)
    for q in queries:
        by_cluster[q["cluster_id"]].append(q)
    for cid in sorted(by_cluster):
        qs = by_cluster[cid]
        vals = [fmt(mean([q["recall"][m] for q in qs])) for m in MODES]
        lines.append(f"| `{cid}` | {len(qs)} | " + " | ".join(vals) + " |")

    agree = [q["fused_matches_api"] for q in queries if q["fused_matches_api"] is not None]
    lines += [
        "",
        f"Local fusion matched the API's `mode=both` top {meta['limit']} exactly for "
        f"{sum(agree)}/{len(agree)} queries.",
        "",
        "## ANN vs exact search",
        "",
        f"Mean overlap@{LIMIT} between ANN results and exact (ENN) results, per numCandidates. "
        "Worst single query in brackets.",
        "",
        "| numCandidates | text | exposure |",
        "|---:|---:|---:|",
    ]
    for nc in meta["num_candidates_grid"]:
        cells = []
        for mode in ("text", "exposure"):
            vals = [q["overlap"][mode][str(nc)] for q in queries]
            cells.append(f"{fmt(mean(vals))} ({fmt(min(vals))})")
        marker = " (default)" if nc == meta["default_num_candidates"] else ""
        lines.append(f"| {nc}{marker} | " + " | ".join(cells) + " |")

    lines += [
        "",
        "## Latency",
        "",
        "Wall-clock time per search measured from the client, so it includes the network round "
        "trip to Atlas. Text calls also include Voyage embedding of the query text. `both (API)` "
        "is a real `/funds/{id}/similar?mode=both` call: text and exposure run concurrently, plus "
        "the fund lookup.",
        "",
        "| Call | Search | n | p50 ms | p95 ms |",
        "|---|---|---:|---:|---:|",
    ]
    calls: dict[tuple[str, str], list[float]] = defaultdict(list)
    for c in data["calls"]:
        calls[(c["kind"], c["search"])].append(c["ms"])

    def sort_key(k: tuple[str, str]) -> tuple:
        kind, search = k
        n = int(search.split("=")[1]) if "=" in search else 10**9
        return (kind, n)

    for key in sorted(calls, key=sort_key):
        v = calls[key]
        lines.append(
            f"| {key[0]} | {key[1]} | {len(v)} | {fmt(percentile(v, 50), 0)} | "
            f"{fmt(percentile(v, 95), 0)} |"
        )

    ct = data["clustered_top1"]
    lines += [
        "",
        "## Outliers",
        "",
        "Outliers have no designed neighbours. Their nearest match should look weaker than a "
        f"clustered fund's: the mean top-1 score for clustered query funds is "
        f"{fmt(ct.get('text', math.nan), 3)} (text) and {fmt(ct.get('exposure', math.nan), 3)} "
        "(exposure). Scores are Atlas `vectorSearchScore`, where 0.5 means unrelated.",
        "",
        "| Outlier | text top-1 | nearest by text | exposure top-1 | nearest by exposure |",
        "|---|---:|---|---:|---|",
    ]
    for o in data["outliers"]:
        lines.append(
            f"| {o['name']} | {fmt(o['text_top1'], 3)} | {o['text_top1_name']} | "
            f"{fmt(o['exposure_top1'], 3)} | {o['exposure_top1_name']} |"
        )

    lines += [
        "",
        "## Per-query results",
        "",
        f"R@{R_K} per mode, and the expected neighbours the fused list missed.",
        "",
        "| Query fund | Cluster | text | exposure | both | missed by both |",
        "|---|---|---:|---:|---:|---|",
    ]
    for q in queries:
        missed = [e for e in q["expected"] if e not in q["ranked"]["both"]]
        lines.append(
            f"| {q['name']} (`{q['fund_id']}`) | `{q['cluster_id']}` | "
            + " | ".join(fmt(q["recall"][m]) for m in MODES)
            + f" | {', '.join(f'`{m}`' for m in missed) or '–'} |"
        )

    lines += [
        "",
        "## Caveats",
        "",
        "- The data is synthetic, and the clusters were built to be found. These numbers compare "
        "the modes with each other; they don't predict quality on real fund data.",
        f"- With {meta['funds']} documents, HNSW is close to exhaustive, so ANN/exact overlap is "
        "expected to be near 1 at moderate numCandidates. That will change at real scale.",
        "- Latency is from a single client, on a shared Free cluster (throttled above 100 ops/s), "
        "with no warm-up beyond the first query.",
        f"- Voyage rate-limit retries during the run: {meta['rate_limited_retries']} (time spent "
        "waiting isn't counted in latency).",
        "",
    ]
    return "\n".join(lines)


def main() -> int:
    parser = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawTextHelpFormatter
    )
    parser.add_argument("--out", default="reports/eval.md")
    parser.add_argument("--per-cluster", type=int, default=2, help="query funds per cluster")
    parser.add_argument(
        "--nc", default=",".join(map(str, DEFAULT_NCS)), help="numCandidates grid, comma-separated"
    )
    parser.add_argument("--from-json", help="re-render a previous run's JSON without querying")
    args = parser.parse_args()

    out = Path(args.out)
    if args.from_json:
        data = json.loads(Path(args.from_json).read_text())
    else:
        ncs = sorted({int(x) for x in args.nc.split(",") if int(x) >= LIMIT})
        data = asyncio.run(evaluate(args.per_cluster, ncs))
        out.parent.mkdir(parents=True, exist_ok=True)
        out.with_suffix(".json").write_text(json.dumps(data, indent=1, default=str))
    out.write_text(render(data))
    print(f"wrote {out} and {out.with_suffix('.json')}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
