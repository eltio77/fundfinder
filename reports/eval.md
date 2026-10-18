# Fund Finder: similarity evaluation

Generated 2026-10-18 09:11 UTC against `fund_finder` (300 synthetic funds), text model `voyage-4`. Client: Darwin arm64, Python 3.12.15.

**Method.** 22 query funds, 11 deliberate clusters. For each query fund, the expected neighbours are the other members of its cluster: 4 for index trackers, 3 for near-duplicates. Each mode returns the top 10, excluding the fund itself. `both` = RRF (k = 60) over the text and exposure lists, each 20 deep, all ANN with numCandidates = 200 (20 × limit).

## Retrieval quality

Precision@5 can't reach 1, because clusters have only 3–4 other members. The ceiling column is the best achievable value.

| Query set | n | Ceiling P@5 | text P@5 | exposure P@5 | both P@5 | text R@10 | exposure R@10 | both R@10 |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| **All** | 22 | 0.71 | 0.65 | 0.62 | 0.68 | 0.98 | 0.92 | 0.98 |
| Index trackers | 12 | 0.80 | 0.80 | 0.75 | 0.80 | 1.00 | 1.00 | 1.00 |
| Near-duplicate active funds | 10 | 0.60 | 0.48 | 0.46 | 0.54 | 0.97 | 0.83 | 0.97 |

### Recall@10 by cluster

| Cluster | Queries | text | exposure | both |
|---|---:|---:|---:|---:|
| `act_global_tech` | 2 | 1.00 | 1.00 | 1.00 |
| `act_japan_value` | 2 | 1.00 | 0.83 | 1.00 |
| `act_strat_bond` | 2 | 0.83 | 0.33 | 0.83 |
| `act_uk_income` | 2 | 1.00 | 1.00 | 1.00 |
| `act_uk_smaller` | 2 | 1.00 | 1.00 | 1.00 |
| `trk_ftse100` | 2 | 1.00 | 1.00 | 1.00 |
| `trk_ftse_allshare` | 2 | 1.00 | 1.00 | 1.00 |
| `trk_ftse_gilts` | 2 | 1.00 | 1.00 | 1.00 |
| `trk_global_agg` | 2 | 1.00 | 1.00 | 1.00 |
| `trk_msci_world` | 2 | 1.00 | 1.00 | 1.00 |
| `trk_sp500` | 2 | 1.00 | 1.00 | 1.00 |

Local fusion matched the API's `mode=both` top 10 exactly for 22/22 queries.

## ANN vs exact search

Mean overlap@10 between ANN results and exact (ENN) results, per numCandidates. Worst single query in brackets.

| numCandidates | text | exposure |
|---:|---:|---:|
| 10 | 1.00 (0.90) | 1.00 (1.00) |
| 20 | 1.00 (1.00) | 1.00 (1.00) |
| 50 | 1.00 (1.00) | 1.00 (1.00) |
| 100 | 1.00 (1.00) | 1.00 (1.00) |
| 200 (default) | 1.00 (1.00) | 1.00 (1.00) |
| 500 | 1.00 (1.00) | 1.00 (1.00) |

## Latency

Wall-clock time per search measured from the client, so it includes the network round trip to Atlas. Text calls also include Voyage embedding of the query text. `both (API)` is a real `/funds/{id}/similar?mode=both` call: text and exposure run concurrently, plus the fund lookup.

| Call | Search | n | p50 ms | p95 ms |
|---|---|---:|---:|---:|
| both (API) | ANN nc=200 | 22 | 240 | 258 |
| exposure | ANN nc=10 | 22 | 35 | 41 |
| exposure | ANN nc=20 | 22 | 35 | 39 |
| exposure | ANN nc=50 | 22 | 34 | 42 |
| exposure | ANN nc=100 | 22 | 34 | 39 |
| exposure | ANN nc=200 | 49 | 35 | 41 |
| exposure | ANN nc=500 | 22 | 34 | 40 |
| exposure | exact | 22 | 34 | 45 |
| text | ANN nc=10 | 22 | 208 | 217 |
| text | ANN nc=20 | 22 | 209 | 220 |
| text | ANN nc=50 | 22 | 210 | 242 |
| text | ANN nc=100 | 22 | 207 | 226 |
| text | ANN nc=200 | 49 | 208 | 220 |
| text | ANN nc=500 | 22 | 210 | 215 |
| text | exact | 22 | 209 | 240 |

## Outliers

Outliers have no designed neighbours. Their nearest match should look weaker than a clustered fund's: the mean top-1 score for clustered query funds is 0.873 (text) and 1.000 (exposure). Scores are Atlas `vectorSearchScore`, where 0.5 means unrelated.

| Outlier | text top-1 | nearest by text | exposure top-1 | nearest by exposure |
|---|---:|---|---:|---|
| Lowther Biotechnology | 0.808 | Lowther Worldwide | 0.928 | Ravensworth Worldwide |
| Pennine UK Commercial Property | 0.803 | Fenwick Real Estate | 0.974 | Halden Real Estate |
| Saltmarsh Frontier Markets | 0.797 | Severn Emerging Markets Growth | 0.979 | Fenwick Global Emerging Markets |
| Kestrel Gold & Precious Metals | 0.802 | Holloway Global Resources | 0.949 | Ashcombe Natural Resources |
| Wexford India Opportunities | 0.809 | Halden FTSE Emerging Index Fund | 0.996 | Halden FTSE Emerging Index Fund |

## Per-query results

R@10 per mode, and the expected neighbours the fused list missed.

| Query fund | Cluster | text | exposure | both | missed by both |
|---|---|---:|---:|---:|---|
| Marlowe Tech Innovators (`F0021`) | `act_global_tech` | 1.00 | 1.00 | 1.00 | – |
| Ravensworth Technology Leaders (`F0050`) | `act_global_tech` | 1.00 | 1.00 | 1.00 | – |
| Ravensworth Japan Recovery (`F0016`) | `act_japan_value` | 1.00 | 0.67 | 1.00 | – |
| Saltmarsh Japan Governance (`F0019`) | `act_japan_value` | 1.00 | 1.00 | 1.00 | – |
| Wexford Strategic Income (`F0010`) | `act_strat_bond` | 1.00 | 0.33 | 1.00 | – |
| Holloway Unconstrained Bond (`F0047`) | `act_strat_bond` | 0.67 | 0.33 | 0.67 | `F0010` |
| Brightwater UK Dividend (`F0052`) | `act_uk_income` | 1.00 | 1.00 | 1.00 | – |
| Brightwater UK Equity Income (`F0143`) | `act_uk_income` | 1.00 | 1.00 | 1.00 | – |
| Calder UK Emerging Leaders (`F0095`) | `act_uk_smaller` | 1.00 | 1.00 | 1.00 | – |
| Lowther UK Discovery (`F0097`) | `act_uk_smaller` | 1.00 | 1.00 | 1.00 | – |
| Kestrel UK 100 Tracker (`F0040`) | `trk_ftse100` | 1.00 | 1.00 | 1.00 | – |
| Holloway FTSE 100 Index Fund (`F0099`) | `trk_ftse100` | 1.00 | 1.00 | 1.00 | – |
| Brightwater All-Share Index (`F0085`) | `trk_ftse_allshare` | 1.00 | 1.00 | 1.00 | – |
| Wexford FTSE All-Share Index Fund (`F0161`) | `trk_ftse_allshare` | 1.00 | 1.00 | 1.00 | – |
| Ravensworth UK Government Bond Index (`F0034`) | `trk_ftse_gilts` | 1.00 | 1.00 | 1.00 | – |
| Halden UK Government Bond Index (`F0043`) | `trk_ftse_gilts` | 1.00 | 1.00 | 1.00 | – |
| Lowther Global Aggregate Bond Index (`F0072`) | `trk_global_agg` | 1.00 | 1.00 | 1.00 | – |
| Brightwater Global Bond Tracker (`F0134`) | `trk_global_agg` | 1.00 | 1.00 | 1.00 | – |
| Wexford Developed World Index (`F0033`) | `trk_msci_world` | 1.00 | 1.00 | 1.00 | – |
| Clarendon World Equity Tracker (`F0036`) | `trk_msci_world` | 1.00 | 1.00 | 1.00 | – |
| Kestrel S&P 500 Index Fund (`F0001`) | `trk_sp500` | 1.00 | 1.00 | 1.00 | – |
| Halden US 500 Tracker (`F0044`) | `trk_sp500` | 1.00 | 1.00 | 1.00 | – |

## Caveats

- The data is synthetic, and the clusters were built to be found. These numbers compare the modes with each other; they don't predict quality on real fund data.
- With 300 documents, HNSW is close to exhaustive, so ANN/exact overlap is expected to be near 1 at moderate numCandidates. That will change at real scale.
- Latency is from a single client, on a shared Free cluster (throttled above 100 ops/s), with no warm-up beyond the first query.
- Voyage rate-limit retries during the run: 0 (time spent waiting isn't counted in latency).
