"""api.routes_projects — projects and evidence routes (C4.1).

Every handler reaches the kit through request.app.state.kit and returns a
view from api.views. Errors are raised, never constructed: api.app's
handlers shape them into the C4.2 envelope.
"""

from __future__ import annotations

import os
import shutil
import tempfile
from typing import Any

from fastapi import APIRouter, File, Form, Request, UploadFile
from pydantic import BaseModel

from api.views import (
    evidence_view,
    project_view,
    snapshot_view,
)

router = APIRouter(prefix="/api")

#: C4.1 evidence upload default when the client sends no source_type.
DEFAULT_SOURCE_TYPE = "other"


def _kit(request: Request) -> Any:
    return request.app.state.kit


# -- request bodies --------------------------------------------------------


class CreateProjectBody(BaseModel):
    name: str
    sponsor: str | None = None
    target_date: str | None = None
    objective: str = ""
    charter_text: str = ""
    constraints_text: str = ""


class SetStatusBody(BaseModel):
    status: str


class SetSponsorBody(BaseModel):
    sponsor: str


# -- projects --------------------------------------------------------------


@router.get("/projects")
async def list_projects(request: Request) -> dict[str, Any]:
    """C4.1 — every project, any status."""
    kit = _kit(request)
    return {"projects": [project_view(p) for p in kit.data.projects.list()]}


@router.post("/projects", status_code=201)
async def create_project(
    request: Request, body: CreateProjectBody
) -> dict[str, Any]:
    """C4.1 — create through FlowService, which allocates the next code."""
    kit = _kit(request)
    row = kit.flow.create_project(
        name=body.name,
        sponsor=body.sponsor,
        target_date=body.target_date,
        objective=body.objective,
        charter_text=body.charter_text,
        constraints_text=body.constraints_text,
    )
    return {"project": project_view(row)}


@router.get("/projects/{code}")
async def get_project(request: Request, code: str) -> dict[str, Any]:
    """C4.1 — the project plus its snapshot, in one call."""
    kit = _kit(request)
    snapshot = kit.flow.list_for_project(code)
    return {
        "project": project_view(snapshot.project),
        "snapshot": snapshot_view(snapshot),
    }


@router.post("/projects/{code}/set_status")
async def set_status(
    request: Request, code: str, body: SetStatusBody
) -> dict[str, Any]:
    """C4.1 — an invalid status raises ServiceError, which the envelope
    maps to 400 with code 'invalid_status'."""
    kit = _kit(request)
    row = kit.data.projects.set_status(code, body.status)
    return {"project": project_view(row)}


@router.post("/projects/{code}/set_sponsor")
async def set_sponsor(
    request: Request, code: str, body: SetSponsorBody
) -> dict[str, Any]:
    """C4.1 — the sponsor is what a report's Prepared for defaults to."""
    kit = _kit(request)
    row = kit.data.projects.set_sponsor(code, body.sponsor)
    return {"project": project_view(row)}


# -- evidence --------------------------------------------------------------


@router.post("/projects/{code}/evidence", status_code=201)
async def attach_evidence(
    request: Request,
    code: str,
    file: UploadFile = File(...),
    source_type: str = Form(DEFAULT_SOURCE_TYPE),
    note: str = Form(""),
) -> dict[str, Any]:
    """C4.1 — multipart upload.

    EvidenceService.attach copies from a path on disk, so the upload is
    spooled to a temporary file first. The temp file keeps the client's
    filename because the destination name is derived from it (C3.2).

    A duplicate raises EvidenceConflict, which the envelope maps to 409.
    """
    kit = _kit(request)
    tmp_dir = tempfile.mkdtemp()
    tmp_path = os.path.join(tmp_dir, file.filename or "upload")
    try:
        with open(tmp_path, "wb") as fh:
            shutil.copyfileobj(file.file, fh)
        row = kit.evidence.attach(code, tmp_path, source_type, note)
    finally:
        shutil.rmtree(tmp_dir, ignore_errors=True)
    return {"evidence": evidence_view(row)}


@router.get("/projects/{code}/evidence")
async def list_evidence(request: Request, code: str) -> dict[str, Any]:
    """C4.1 — the project's evidence rows.

    DELETE is deliberately absent (C4.1 frozen): the app never deletes
    evidence. A file removed by hand surfaces as a missing-file flag in
    integrity, which is the designed behaviour per I2.
    """
    kit = _kit(request)
    return {
        "evidence": [evidence_view(r) for r in kit.evidence.list_for(code)]
    }
