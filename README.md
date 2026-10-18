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

## Development

```bash
uv run ruff check . && uv run ruff format --check . && uv run pytest
```
