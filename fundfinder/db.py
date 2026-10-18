from fastapi import HTTPException, Request
from pymongo import AsyncMongoClient
from pymongo.asynchronous.database import AsyncDatabase

from fundfinder.config import Settings

FUNDS = "funds"


NOT_CONFIGURED = "database not configured: set MONGODB_URI"


def make_client(settings: Settings) -> AsyncMongoClient:
    # Construction is lazy: no network I/O until the first operation.
    if settings.mongodb_uri is None:
        raise RuntimeError(NOT_CONFIGURED)
    return AsyncMongoClient(
        settings.mongodb_uri.get_secret_value(),
        appname="fund-finder",
        serverSelectionTimeoutMS=settings.mongodb_timeout_ms,
    )


def get_client(request: Request) -> AsyncMongoClient:
    if request.app.state.mongo is None:
        raise HTTPException(503, NOT_CONFIGURED)
    return request.app.state.mongo


def get_db(request: Request) -> AsyncDatabase:
    return get_client(request)[request.app.state.settings.mongodb_db]
