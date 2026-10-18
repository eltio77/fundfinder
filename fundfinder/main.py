import logging
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from pathlib import Path

from anthropic import AsyncAnthropic
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from pymongo.errors import OperationFailure, PyMongoError

from fundfinder.config import Settings, get_settings
from fundfinder.db import NOT_CONFIGURED, make_client
from fundfinder.llm_intent import LlmInterpreter
from fundfinder.routes import api, health
from fundfinder.routes.web import WEB_DIST, mount_web

log = logging.getLogger("fundfinder")

API_DESCRIPTION = """
Similarity search over UK funds with MongoDB Atlas Vector Search.

- **Text** similarity: Atlas embeds each fund's description (Voyage `voyage-4`, autoEmbed).
- **Exposure** similarity: cosine over a 26-number vector of sector, region and asset weights.
- **Both**: reciprocal rank fusion (k=60) of the two.

All search endpoints take `limit`, `num_candidates` (ANN breadth, default 20 x limit), `exact`
(exhaustive search) and filters. Data is synthetic. [Back to the app](/)
"""

OPENAPI_TAGS = [
    {"name": "search", "description": "Find funds by description or by similarity to a fund"},
    {"name": "funds", "description": "Fund details"},
    {"name": "reference", "description": "Filter options and evaluation test sets"},
    {"name": "ops", "description": "Health check"},
]


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    settings = get_settings()
    app.state.settings = settings
    app.state.mongo = make_client(settings) if settings.mongodb_uri else None
    if app.state.mongo is None:
        log.error(NOT_CONFIGURED)
    app.state.llm = make_llm(settings)
    try:
        yield
    finally:
        if app.state.mongo is not None:
            await app.state.mongo.close()
        if app.state.llm is not None:
            await app.state.llm.client.close()


def make_llm(settings: Settings) -> LlmInterpreter | None:
    if settings.anthropic_api_key is None or not settings.anthropic_api_key.get_secret_value():
        return None
    client = AsyncAnthropic(api_key=settings.anthropic_api_key.get_secret_value())
    return LlmInterpreter(client, settings.intent_model, settings.intent_timeout_s)


def create_app(web_dist: Path | None = WEB_DIST) -> FastAPI:
    """web_dist=None gives an API-only app."""
    app = FastAPI(
        title="Fund Finder API",
        version="0.1.0",
        description=API_DESCRIPTION,
        openapi_tags=OPENAPI_TAGS,
        lifespan=lifespan,
        swagger_ui_parameters={"tryItOutEnabled": True, "displayRequestDuration": True},
    )
    app.include_router(health.router)
    app.include_router(api.router)
    if web_dist is not None:
        mount_web(app, web_dist)

    @app.exception_handler(PyMongoError)
    async def mongo_error(request: Request, exc: PyMongoError) -> JSONResponse:
        # Atlas surfaces Voyage throttling of query-time embedding as a generic
        # OperationFailure; only the message distinguishes it.
        if isinstance(exc, OperationFailure) and "rate limit" in str(exc).lower():
            log.warning("embedding rate limited on %s", request.url.path)
            return JSONResponse(
                {"detail": "embedding provider rate limit exceeded, retry later"},
                status_code=429,
                headers={"Retry-After": "20"},
            )
        log.exception("database error on %s", request.url.path)
        return JSONResponse({"detail": "database unavailable"}, status_code=503)

    return app


app = create_app()
