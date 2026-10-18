from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI

from fundfinder.config import get_settings
from fundfinder.db import make_client
from fundfinder.routes import health


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    settings = get_settings()
    app.state.settings = settings
    app.state.mongo = make_client(settings)
    try:
        yield
    finally:
        await app.state.mongo.close()


def create_app() -> FastAPI:
    app = FastAPI(title="Fund Finder", lifespan=lifespan)
    app.include_router(health.router)
    return app


app = create_app()
