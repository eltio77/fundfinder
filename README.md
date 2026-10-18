# Fund Finder

Prototype similarity search over (synthetic) UK funds using MongoDB Atlas Vector Search.

> Work in progress: Atlas setup, seeding, indexes, eval and deploy sections land in later phases.

## Local run

Prerequisites: [uv](https://docs.astral.sh/uv/), Docker, an Atlas Free cluster.

```bash
cp .env.example .env          # then fill in MONGODB_URI (and VOYAGE_API_KEY if using the fallback)
uv sync
uv run uvicorn fundfinder.main:app --reload    # http://localhost:8000/health
# or
docker compose up --build
```

## Checking Automated Embedding on your cluster

```bash
uv run python -m scripts.check_autoembed
```

Creates a scratch autoEmbed index, runs an ANN and an exact query, and drops it again.

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

## Development

```bash
uv run ruff check . && uv run ruff format --check . && uv run pytest
```
