from typing import Annotated

from fastapi import APIRouter, Depends
from fastapi.responses import JSONResponse
from pymongo import AsyncMongoClient
from pymongo.errors import PyMongoError

from fundfinder.db import get_client

router = APIRouter()


@router.get("/health", tags=["ops"])
async def health(client: Annotated[AsyncMongoClient, Depends(get_client)]) -> JSONResponse:
    """Pings the database: 200 when reachable, 503 otherwise."""
    try:
        await client.admin.command("ping")
    except PyMongoError as exc:
        return JSONResponse(
            {"status": "degraded", "mongo": "unreachable", "error": type(exc).__name__},
            status_code=503,
        )
    return JSONResponse({"status": "ok", "mongo": "ok"})
