from fastapi import Request
from pymongo import AsyncMongoClient
from pymongo.asynchronous.database import AsyncDatabase

from fundfinder.config import Settings

FUNDS = "funds"


def make_client(settings: Settings) -> AsyncMongoClient:
    # Construction is lazy: no network I/O until the first operation.
    return AsyncMongoClient(
        settings.mongodb_uri.get_secret_value(),
        appname="fund-finder",
        serverSelectionTimeoutMS=settings.mongodb_timeout_ms,
    )


def get_client(request: Request) -> AsyncMongoClient:
    return request.app.state.mongo


def get_db(request: Request) -> AsyncDatabase:
    return request.app.state.mongo[request.app.state.settings.mongodb_db]
