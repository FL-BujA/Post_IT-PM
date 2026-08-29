"""api.routes_reports — minutes, signals, report, search, backup and
integrity routes (C4.1).

Everything the PM reads out of the tool rather than types into it, plus the
three operations that move data in and out: backup, restore and handover.
"""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Query, Request
from pydantic import BaseModel

from api.views import (
    hit_view,
    integrity_view,
    minutes_view,
    owner_health_view,
    report_view,
    signal_view,
)

router = APIRouter(prefix="/api")

#: C4.1 minutes: 20 by default, 100 ceiling.
MINUTES_DEFAULT = 20
MINUTES_MAX = 100

#: C4.1 reports: newest 20.
REPORTS_LIMIT = 20

#: C4.1 report response hint. The api never launches anything itself.
OPEN_INTENT = "explorer"


def _kit(request: Request) -> Any:
    return request.app.state.kit


# -- request bodies --------------------------------------------------------


class CreateMinutesBody(BaseModel):
    held_at: str
    attendees: str | None = None
    decisions: str | None = None
    agreed_actions: str | None = None
    risks: str | None = None
    minutes_text: str
    cycle_id: int | None = None


class CreateSignalBody(BaseModel):
    kind: str
    owner: str
    action_id: int | None = None
    note: str = ""


class ResolveSignalBody(BaseModel):
    resolved: bool


class ReportBody(BaseModel):
    prepared_for: str | None = None


class BackupBody(BaseModel):
    label: str | None = None
    dest_dir: str | None = None


class RestoreBody(BaseModel):
    backup_dir: str


class HandoverBody(BaseModel):
    dest_dir: str | None = None


# -- minutes ---------------------------------------------------------------


@router.post("/projects/{code}/minutes", status_code=201)
async def add_minutes(
    request: Request, code: str, body: CreateMinutesBody
) -> dict[str, Any]:
    """C4.1 — minutes_text is stored verbatim; agreed_actions is free text
    and creates no action rows (C3.3 frozen)."""
    kit = _kit(request)
    row = kit.flow.add_minutes(
        code,
        body.held_at,
        body.attendees,
        body.decisions,
        body.agreed_actions,
        body.risks,
        body.minutes_text,
        cycle_id=body.cycle_id,
    )
    return {"minutes": minutes_view(row)}


@router.get("/projects/{code}/minutes")
async def list_minutes(
    request: Request,
    code: str,
    limit: int = Query(MINUTES_DEFAULT, ge=1, le=MINUTES_MAX),
) -> dict[str, Any]:
    """C4.1 — held_at descending, 20 by default, 100 maximum."""
    kit = _kit(request)
    rows = sorted(
        kit.data.minutes.list_for(code),
        key=lambda m: m.held_at,
        reverse=True,
    )[:limit]
    return {"minutes": [minutes_view(m) for m in rows]}


# -- engagement ------------------------------------------------------------


@router.post("/projects/{code}/signals", status_code=201)
async def add_signal(
    request: Request, code: str, body: CreateSignalBody
) -> dict[str, Any]:
    """C4.1 — the PM logs a defer, extension request, late start or
    reopen."""
    kit = _kit(request)
    row = kit.engagement.record(
        code, body.kind, body.owner, action_id=body.action_id, note=body.note
    )
    return {"signal": signal_view(row)}


@router.patch("/projects/{code}/signals/{signal_id}/resolved")
async def resolve_signal(
    request: Request, code: str, signal_id: int, body: ResolveSignalBody
) -> dict[str, Any]:
    """C4.1 — resolve or un-resolve. Signals are never deleted."""
    kit = _kit(request)
    row = kit.engagement.mark_resolved(code, signal_id, body.resolved)
    return {"signal": signal_view(row)}


@router.get("/projects/{code}/signals")
async def list_signals(
    request: Request,
    code: str,
    kind: str | None = None,
    owner: str | None = None,
    resolved: bool | None = None,
) -> dict[str, Any]:
    """C4.1 — filtered by kind, owner and resolved, any combination."""
    kit = _kit(request)
    rows = kit.engagement.list_for(
        code, kind=kind, owner=owner, resolved=resolved
    )
    return {"signals": [signal_view(s) for s in rows]}


@router.get("/projects/{code}/engagement/health")
async def engagement_health(request: Request, code: str) -> dict[str, Any]:
    """C4.1 — per-owner counts. This is the ONE aggregation (C3.4 frozen);
    the report strip calls the same method."""
    kit = _kit(request)
    return {
        "health": [
            owner_health_view(h) for h in kit.engagement.health_by_owner(code)
        ]
    }


# -- report ----------------------------------------------------------------


@router.post("/projects/{code}/report", status_code=201)
async def generate_report(
    request: Request, code: str, body: ReportBody
) -> dict[str, Any]:
    """C4.1 — generate and return the row plus an open hint.

    open_intent is a HINT for the ui, which may shell-execute the file.
    The api never launches anything itself (frozen).
    """
    kit = _kit(request)
    row = kit.report.generate(code, body.prepared_for)
    return {"report": report_view(row), "open_intent": OPEN_INTENT}


@router.get("/projects/{code}/reports")
async def list_reports(request: Request, code: str) -> dict[str, Any]:
    """C4.1 — generated_at descending, newest 20."""
    kit = _kit(request)
    rows = sorted(
        kit.data.reports.list_for(code),
        key=lambda r: r.generated_at,
        reverse=True,
    )[:REPORTS_LIMIT]
    return {"reports": [report_view(r) for r in rows]}


# -- search ----------------------------------------------------------------


@router.get("/search")
async def search(
    request: Request,
    terms: str,
    project: str | None = None,
    limit: int = Query(50, ge=1, le=200),
) -> dict[str, Any]:
    """C4.1 — the single search box. A missing FTS table raises CoreError
    code 'fts_unavailable' -> 400."""
    kit = _kit(request)
    hits = kit.data.search.search(terms, project_code=project, limit=limit)
    return {"hits": [hit_view(h) for h in hits]}


# -- backup / restore / handover -------------------------------------------


@router.post("/backup", status_code=201)
async def create_backup(request: Request, body: BackupBody) -> dict[str, Any]:
    """C4.1 — copy the database and the trees, with a manifest."""
    kit = _kit(request)
    descriptor = kit.backup.create_backup(
        label=body.label, dest_dir=body.dest_dir
    )
    return {
        "backup": {
            "dest": descriptor.dest,
            "files": descriptor.count_files,
            "ok": descriptor.ok,
        }
    }


@router.post("/restore")
async def restore(request: Request, body: RestoreBody) -> dict[str, Any]:
    """C4.1 — I6: the backup is verified before anything is replaced. A
    failed verification returns ok=false with nothing written."""
    kit = _kit(request)
    report = kit.backup.restore(body.backup_dir)
    return {
        "restore": {
            "ok": report.ok,
            "verified_ok": report.verified_ok,
            "missing": report.missing_count,
            "mismatched": report.mismatch_count,
            "orphans": report.orphan_count,
        }
    }


@router.post("/projects/{code}/handover", status_code=201)
async def handover(
    request: Request, code: str, body: HandoverBody
) -> dict[str, Any]:
    """C4.1 — one zip: rows as json, the story as markdown, the files
    themselves, and a manifest."""
    kit = _kit(request)
    dest = body.dest_dir or request.app.state.kit.root
    zip_path = kit.handover.export(code, dest)
    return {"handover": {"zip": zip_path, "ok": True}}


# -- integrity -------------------------------------------------------------


@router.get("/integrity")
async def integrity(request: Request) -> dict[str, Any]:
    """C4.1 — I2: reports, never repairs. Counts plus the first 50 of each
    list."""
    kit = _kit(request)
    report = kit.data.integrity.verify(kit.root)
    return {"integrity": integrity_view(report)}
