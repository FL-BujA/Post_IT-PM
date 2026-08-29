"""api.app — create_app and the C4.2 error envelope.

C4.0: create_app(kit) is the ONLY construction path. The kit lives in
app.state; there is no module-level database and no global singleton.

C4.2: every error leaves as {"error": {"code": ..., "message": ...}}, with
the HTTP class chosen by one frozen mapping. A route never builds an error
response itself — it raises, and the handler shapes it.
"""

from __future__ import annotations

from typing import Any

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse

from core import (
    CoreError,
    EvidenceConflict,
    UnknownProjectData,
)

#: C4.2 error codes that map to 404 rather than 400.
NOT_FOUND_CODES = frozenset(
    {"unknown_project", "not_found", "signal_unknown", "evidence_unknown"}
)

#: C4.2: EvidenceConflict is the one 409.
CONFLICT_CODES = frozenset({"evidence_conflict"})


def _envelope(code: str, message: str) -> dict[str, Any]:
    """The single error shape. Nothing else may construct one."""
    return {"error": {"code": code, "message": message}}


def _status_for(err: CoreError) -> int:
    """C4.2's frozen mapping from a CoreError to its HTTP class."""
    code = getattr(err, "code", "core")
    if isinstance(err, UnknownProjectData) or code in NOT_FOUND_CODES:
        return 404
    if isinstance(err, EvidenceConflict) or code in CONFLICT_CODES:
        return 409
    return 400


def create_app(kit: Any) -> FastAPI:
    """C4.0 — the only construction path.

    The kit is stored on app.state and reached by routes through
    request.app.state.kit. The api never imports DataKit: the kit is the
    boundary (C4.1 health note).
    """
    app = FastAPI(title="PM Cockpit", version="1.0.0")
    app.state.kit = kit

    # -- C4.2 handlers -----------------------------------------------------

    @app.exception_handler(CoreError)
    async def _core_error(request: Request, exc: CoreError) -> JSONResponse:
        return JSONResponse(
            status_code=_status_for(exc),
            content=_envelope(getattr(exc, "code", "core"), str(exc)),
        )

    @app.exception_handler(RequestValidationError)
    async def _validation(
        request: Request, exc: RequestValidationError
    ) -> JSONResponse:
        return JSONResponse(
            status_code=422,
            content=_envelope("validation", str(exc)),
        )

    @app.exception_handler(404)
    async def _not_found(request: Request, exc: Any) -> JSONResponse:
        """C4.2: an unknown route returns the envelope, not HTML."""
        return JSONResponse(
            status_code=404,
            content=_envelope("not_found", f"no route for {request.url.path}"),
        )

    @app.exception_handler(Exception)
    async def _internal(request: Request, exc: Exception) -> JSONResponse:
        return JSONResponse(
            status_code=500,
            content=_envelope("internal", str(exc)),
        )

    # -- health ------------------------------------------------------------

    @app.get("/api/health")
    async def health(request: Request) -> dict[str, Any]:
        """C4.1 health. Counts projects through the kit — the api never
        touches DataKit directly."""
        kit = request.app.state.kit
        return {
            "ok": True,
            "schema_version": "1",
            "projects": len(kit.data.projects.list()),
        }

    from api.routes_projects import router as projects_router
    app.include_router(projects_router)
    from api.routes_actions import router as actions_router
    app.include_router(actions_router)
    from api.routes_reports import router as reports_router
    app.include_router(reports_router)
    from api.static import mount as mount_ui
    mount_ui(app)

    return app
