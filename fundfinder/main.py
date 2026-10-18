import logging
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from pymongo.errors import OperationFailure, PyMongoError

from fundfinder.config import get_settings
from fundfinder.db import make_client
from fundfinder.routes import api, health
from fundfinder.routes.web import WEB_DIST, mount_web

log = logging.getLogger("fundfinder")


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    settings = get_settings()
    app.state.settings = settings
    app.state.mongo = make_client(settings)
    try:
        yield
    finally:
        await app.state.mongo.close()


def create_app(web_dist: Path | None = WEB_DIST) -> FastAPI:
    """web_dist=None gives an API-only app."""
    app = FastAPI(title="Fund Finder", lifespan=lifespan)
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
