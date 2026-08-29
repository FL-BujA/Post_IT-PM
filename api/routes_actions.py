"""api.routes_actions — actions, cycles and gates routes (C4.1).

The loop the PM drives daily: raise an action, move it through its states,
open and close a cycle behind a recorded gate.

Errors are raised, not constructed. An illegal state transition surfaces as
CoreError code 'illegal_transition' -> 400; closing a cycle without a
recorded outcome as GateMissing -> 400 code 'gate_missing'; a second open
cycle as ServiceError code 'cycle_open' -> 400. All three are frozen rules
enforced below this layer, not here.
"""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Request
from pydantic import BaseModel

from api.views import action_view, cycle_view, gate_view

router = APIRouter(prefix="/api")


def _kit(request: Request) -> Any:
    return request.app.state.kit


# -- request bodies --------------------------------------------------------


class CreateActionBody(BaseModel):
    title: str
    owner: str
    description: str = ""
    priority: int = 9
    due_start: str | None = None
    due_end: str | None = None
    cycle_id: int | None = None


class PatchActionBody(BaseModel):
    """C4.1 frozen: status is the ONLY field in v1. Adding another is a
    CC card, not an edit here."""

    status: str


class CreateCycleBody(BaseModel):
    name: str


class CloseCycleBody(BaseModel):
    gate_id: int


class CreateGateBody(BaseModel):
    name: str
    planned_date: str | None = None
    exit_criteria: str = ""
    notes: str = ""


class GateOutcomeBody(BaseModel):
    outcome: str
    actual_date: str | None = None


# -- actions ---------------------------------------------------------------


@router.post("/projects/{code}/actions", status_code=201)
async def create_action(
    request: Request, code: str, body: CreateActionBody
) -> dict[str, Any]:
    """C4.1 — cycle_id defaults to the project's current open cycle."""
    kit = _kit(request)
    row = kit.flow.add_action(
        code,
        body.title,
        body.owner,
        description=body.description,
        priority=body.priority,
        due_start=body.due_start,
        due_end=body.due_end,
        cycle_id=body.cycle_id,
    )
    return {"action": action_view(row)}


@router.patch("/projects/{code}/actions/{action_id}")
async def patch_action(
    request: Request, code: str, action_id: int, body: PatchActionBody
) -> dict[str, Any]:
    """C4.1 — status only. An illegal transition raises CoreError with
    code 'illegal_transition', which the envelope maps to 400."""
    kit = _kit(request)
    row = kit.flow.set_action_status(code, action_id, body.status)
    return {"action": action_view(row)}


@router.get("/projects/{code}/actions")
async def list_actions(request: Request, code: str) -> dict[str, Any]:
    """C4.1 — ordered priority asc, then due, then id.

    C4.1 names due_end as the second sort key. ActionRow carries a single
    `due` field and no due_end (deviation logged in BUILD_STATE.md), so
    `due` is the key used. Rows with no due date sort last.
    """
    kit = _kit(request)
    rows = kit.data.actions.list_for(code)
    rows = sorted(
        rows,
        key=lambda a: (a.priority, a.due is None, a.due or "", a.id),
    )
    return {"actions": [action_view(a) for a in rows]}


# -- cycles ----------------------------------------------------------------


@router.post("/projects/{code}/cycles", status_code=201)
async def open_cycle(
    request: Request, code: str, body: CreateCycleBody
) -> dict[str, Any]:
    """C4.1 — a second cycle while one is open raises ServiceError code
    'cycle_open' -> 400."""
    kit = _kit(request)
    row = kit.flow.open_cycle(code, body.name)
    return {"cycle": cycle_view(row)}


@router.post("/projects/{code}/cycles/{cycle_id}/close")
async def close_cycle(
    request: Request, code: str, cycle_id: int, body: CloseCycleBody
) -> dict[str, Any]:
    """C4.1 — I3: a gate with no recorded outcome raises GateMissing,
    which the envelope maps to 400 code 'gate_missing'.

    The cycle_id in the path identifies the cycle; FlowService.close_cycle
    resolves it from the project, so the body's gate_id is what selects
    the gate.
    """
    kit = _kit(request)
    row = kit.flow.close_cycle(code, body.gate_id)
    return {"cycle": cycle_view(row)}


# -- gates -----------------------------------------------------------------


@router.post("/projects/{code}/gates", status_code=201)
async def create_gate(
    request: Request, code: str, body: CreateGateBody
) -> dict[str, Any]:
    """C4.1 — a new gate starts PLANNED.

    exit_criteria and notes are stored (A-12) but GateRow does not carry
    them, so GateView returns null for both until the row gains the
    fields. Deviation logged in BUILD_STATE.md.
    """
    kit = _kit(request)
    row = kit.data.gates.create(
        code,
        body.name,
        planned_date=body.planned_date,
        exit_criteria=body.exit_criteria,
        notes=body.notes,
    )
    return {"gate": gate_view(row)}


@router.post("/projects/{code}/gates/{gate_id}/outcome")
async def record_gate_outcome(
    request: Request, code: str, gate_id: int, body: GateOutcomeBody
) -> dict[str, Any]:
    """C4.1 — records a real outcome. A gate belonging to another project
    raises CoreError -> 400."""
    kit = _kit(request)
    row = kit.flow.record_gate(
        code, gate_id, body.outcome, actual_date=body.actual_date
    )
    return {"gate": gate_view(row)}


@router.get("/projects/{code}/gates")
async def list_gates(request: Request, code: str) -> dict[str, Any]:
    """C4.1 — every gate for the project, planned_date ascending."""
    kit = _kit(request)
    return {"gates": [gate_view(g) for g in kit.data.gates.list_for(code)]}
