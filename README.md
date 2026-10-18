# Fund Finder

Prototype similarity search over (synthetic) UK funds using MongoDB Atlas Vector Search.

> Work in progress: Atlas setup, seeding, indexes, eval and deploy sections land in later phases.

## Local run

Prerequisites: [uv](https://docs.astral.sh/uv/), Node 24, Docker.

### Option A: everything in Docker, with local Atlas (no cloud cluster needed)

`compose.yaml` runs `mongodb/mongodb-atlas-local:preview` (mongod + mongot with Vector Search and
Automated Embedding) alongside the app. Embedding still calls Voyage, so put `VOYAGE_API_KEY` in
`.env` first. For a key created directly at voyageai.com, also set
`VOYAGE_EMBEDDING_PROVIDER_ENDPOINT=https://api.voyageai.com/v1/embeddings`.

```bash
cp .env.example .env                                     # add VOYAGE_API_KEY
docker compose up -d --build                             # mongo + app on http://localhost:8000
docker compose run --rm app python -m scripts.seed
docker compose run --rm app python -m scripts.indexes    # waits until READY
```

With a free Voyage key (3 req/min, 10K tokens/min) the first `profile_auto` build takes about
20 minutes. With a payment method on the key it takes about one minute.

### Option B: develop with hot reload

```bash
uv sync && (cd web && npm install)
uv run uvicorn fundfinder.main:app --reload     # API on :8000 (uses MONGODB_URI from .env)
cd web && npm run dev                           # UI on http://localhost:5173, proxies the API
```

To point the API or scripts at the local Docker Mongo instead of Atlas, prefix commands with
`MONGODB_URI="mongodb://localhost:27017/?directConnection=true"`.

## Frontend

`web/` is a React 19 + TypeScript app built with Vite. The production build is baked into the
same Docker image and served by FastAPI at `/` and `/fund/{id}`. There's no frontend server.

The app is designed for people who don't know fund jargon. The natural-language search is the
centrepiece, set in a calm card layout (Geist; forest, cream, lilac and amber palette; light and
dark themes).

- **Search:** describe a fund in plain English. Results show the fund type, annual cost and a
  plain-language match strength ("Strong", "Good" or "Loose" match). Filters are fund type, asset
  type and cost. All state lives in the URL, so searches can be shared.
- **How it works:** the three methods (description, holdings, combined) shown as coloured blocks.
- **Fund page:** the key facts, what it says it does, what it invests in, its biggest holdings, and
  **Funds like this**. That list is the fused ranking, and each fund says why it matched:
  "Similar description and holdings" (top 10 of both methods), "Similar description" or "Similar
  holdings". "How we found these" turns the same information into a gauge. "Only cheaper" limits
  the list to lower-cost funds.
- **Expert mode** (switch in the top bar, remembered per browser) adds the technical layer:
  - scores, ranks and exposure fingerprints
  - limit, numCandidates and ANN/exact settings
  - an IA sector filter
  - test sets and designed-sibling counts
  - a side-by-side comparison of the three methods
- **Fewer Voyage calls:** a normal fund page makes one Voyage call (fused mode). The comparison
  view adds one more, and only when it's switched on.
- **Rate limits:** a request throttled by Voyage (HTTP 429) retries itself with a visible
  countdown.

```bash
cd web && npm run typecheck && npm test && npm run build
```

## Data and seeding

There is no real vendor data. `fundfinder/data/synthetic.py` generates a deterministic universe of
300 UK funds (fictional providers, made-up weights). The clusters below are built in deliberately,
for evaluation, and labelled with `cluster_id`:

| Kind | `cluster_id` | Members |
|---|---|---|
| Index trackers from different providers | `trk_ftse100`, `trk_ftse_allshare`, `trk_sp500`, `trk_msci_world`, `trk_global_agg`, `trk_ftse_gilts` | 5 each |
| Near-duplicate active funds | `act_uk_income`, `act_global_tech`, `act_uk_smaller`, `act_strat_bond`, `act_japan_value` | 4 each |
| Outliers (no true neighbours) | `outlier_gold`, `outlier_frontier`, `outlier_india`, `outlier_biotech`, `outlier_direct_property` | 1 each |

The other ~245 funds are background noise scattered around 22 IA-sector archetypes. FTSE 100 and
FTSE All-Share trackers are deliberately close to each other (a hard negative).

Each document also stores two derived fields:

- `profile`: text built from name, objective, IA sector, passive/active, top holdings, main GICS
  sectors and region split. This is what Atlas embeds.
- `exposure_vector`: 26 dims = 11 GICS sectors (whole-portfolio terms) | 8 regions | 7 asset
  classes, the last two blocks normalised to sum 1, then the whole vector L2-normalised.

```bash
uv run python -m scripts.seed --dry-run   # summary + sample document, no writes
uv run python -m scripts.seed             # upsert into Atlas
```

Seeding is idempotent: it upserts each fund and deletes funds no longer in the source. It never
drops the collection, so search indexes survive, and unchanged documents aren't re-embedded.
To plug in real data later, implement `FundSource.fetch()` (`fundfinder/data/source.py`) and pass
it to `scripts/seed.py`.

## Indexes

Two of the three search/vector indexes a Free cluster allows:

| Index | Type | Field | Filters |
|---|---|---|---|
| `profile_auto` | `autoEmbed` (Atlas Automated Embedding, `voyage-4`) | `profile` | `asset_class`, `ia_sector`, `ocf`, `is_passive` |
| `exposure_vec` | `vector`, 26 dims, cosine | `exposure_vector` | same |

```bash
uv run python -m scripts.indexes          # create/update, wait until READY (--timeout, default 30 min)
```

The script is idempotent: missing indexes are created, changed definitions are updated in place,
and matching ones are left alone. Run it after seeding, because the collection must exist.

Atlas embeds each `profile` when it indexes it, and embeds query text at query time, using the
Voyage key registered in **Atlas** (not `VOYAGE_API_KEY`). **A Voyage key without a payment
method is limited to 3 requests/minute**, and every text query is one request. The API returns
`429` when it's throttled. Adding a payment method raises the limit to 2,000 RPM; the free-token
allowance still applies.

## API

| Endpoint | Notes |
|---|---|
| `GET /health` | Pings Mongo; 503 if unreachable |
| `GET /search?q=...` | Semantic search on `profile_auto` |
| `GET /funds/{id}` | Fund document |
| `GET /meta` | Filter facets, exposure-vector layout, defaults |
| `GET /clusters` | Synthetic test clusters and their members |
| `GET /funds/{id}/similar?mode=text\|exposure\|both` | Neighbours of a fund, excluding itself |

Common query parameters: `limit` (1-100, default 10), `num_candidates` (default `20 x limit`,
max 10,000), `exact` (ENN instead of ANN), and filters `asset_class`, `ia_sector`, `ocf_max`,
`is_passive`.

- `text` uses the fund's own `profile` as the query text.
- `exposure` uses its stored `exposure_vector` as `queryVector`.
- `both` runs the two concurrently, each `2 x limit` deep, and fuses them with reciprocal rank
  fusion (k=60). Results then include each fund's `ranks` in the two lists.

The fund itself is excluded by requesting `limit + 1` and dropping it. Scores are Atlas
`vectorSearchScore`, so cosine is reported as `(1 + cos) / 2`; in `both` mode the score is the RRF
score.

## Evaluation

```bash
uv run python -m scripts.eval                          # writes reports/eval.md + reports/eval.json
uv run python -m scripts.eval --from-json reports/eval.json   # re-render without querying
```

There are 22 labelled query funds: 2 from each tracker and near-duplicate cluster. Each fund's
expected neighbours are the other members of its cluster. The script reports:

- precision@5 (with its ceiling) and recall@10 for text, exposure and both
- ANN vs exact overlap@10 at numCandidates of 10–500
- p50/p95 latency per call type
- how outliers score against clustered funds

`both` is fused locally with the API's own RRF and cross-checked against real `mode=both` calls.
A full run makes about 200 Voyage calls, so it needs a Voyage key with a payment method.

Latest run ([reports/eval.md](reports/eval.md), Atlas Free cluster):

| | P@5 (ceiling 0.71) | R@10 | p50 latency |
|---|---:|---:|---:|
| text | 0.65 | 0.98 | 208 ms |
| exposure | 0.62 | 0.92 | 35 ms |
| both | **0.68** | **0.98** | 240 ms (API) |

## Deploy (Vercel)

Vercel builds `Dockerfile.vercel` (Container Runtime, beta, available on Hobby) on every push to
`main`. The image includes the built React app. Set these project environment variables
(Settings → Environment Variables, for Production and Preview), then redeploy:

| Variable | Required | Value |
|---|---|---|
| `MONGODB_URI` | yes | Atlas SRV string for a **read-only** database user (role `read` on `fund_finder`) |
| `PORT` | yes | `8000`. Vercel routes to port 80 unless `PORT` is set, and the container runs as a non-root user |
| `MONGODB_DB` | no | defaults to `fund_finder` |
| `EMBED_MODEL` | no | defaults to `voyage-4`; must match the model in the `profile_auto` index |

You don't need `VOYAGE_API_KEY` on Vercel: Atlas embeds query text using the key registered in
Atlas.

**Atlas network access.** Vercel functions use dynamic egress IPs, and Static IPs / Secure Compute
aren't available for custom containers yet. So Atlas has to allow `0.0.0.0/0`. That exposes the
cluster's login endpoint to the internet, with TLS and a password as the only protection. To
reduce the risk:

- use a dedicated, read-only database user with a long random password
- rotate the password if it leaks
- keep anything sensitive out of this cluster

The alternative is to put the API somewhere with a fixed egress IP.

**Region.** Set the function region (Settings → Functions) to the one nearest your Atlas cluster.
The default is `iad1` (US East). Each search makes a round trip to Atlas.

## Development

```bash
uv run ruff check . && uv run ruff format --check . && uv run pytest
(cd web && npm run typecheck && npm test)
```

CI (GitHub Actions) runs both on every PR and on pushes to `main`.
