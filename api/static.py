"""api.static — serve the ui shell (C4.1: GET / and /static)."""

from __future__ import annotations

import os

from fastapi import FastAPI
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

UI_DIR = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "ui"
)


def mount(app: FastAPI) -> None:
    """Mount /static and serve index.html at /."""
    if not os.path.isdir(UI_DIR):
        return
    app.mount("/static", StaticFiles(directory=UI_DIR), name="static")

    @app.get("/", include_in_schema=False)
    async def index() -> FileResponse:
        return FileResponse(os.path.join(UI_DIR, "index.html"))
