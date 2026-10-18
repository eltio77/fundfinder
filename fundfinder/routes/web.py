"""Serves the built React app (web/dist) when present. Without a build (tests,
or `npm run dev` with Vite proxying the API) the app is API-only."""

from pathlib import Path

from fastapi import FastAPI
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

WEB_DIST = Path(__file__).resolve().parents[2] / "web" / "dist"


def mount_web(app: FastAPI, dist: Path = WEB_DIST) -> bool:
    index = dist / "index.html"
    if not index.is_file():
        return False

    app.mount("/assets", StaticFiles(directory=dist / "assets"), name="assets")

    # Client-side routes. They don't overlap the API paths (/search, /funds/...).
    @app.get("/", include_in_schema=False)
    @app.get("/fund/{fund_id}", include_in_schema=False)
    async def spa(fund_id: str | None = None) -> FileResponse:
        return FileResponse(index)

    @app.get("/favicon.svg", include_in_schema=False)
    async def favicon() -> FileResponse:
        return FileResponse(dist / "favicon.svg")

    return True
