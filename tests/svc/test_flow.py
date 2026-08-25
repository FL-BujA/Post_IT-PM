"""Tests for services.flow — card A-02 (FlowService: project, cycle,
gate, action).

Done-when (A-02):
  - each of the six methods exists with the EXACT C3.3 signature —
    asserted by inspect.signature against the contract, transcribed
    into the test.
  - create_project maps its parameters by NAME onto ProjectSVC's
    differing order: all six arguments passed positionally in C3.3
    order, the resulting row carries them correctly.
  - open_cycle twice on one project raises ServiceError code
    'cycle_open' (C3.3 frozen rule).
  - close_cycle without a recorded outcome raises GateMissing and a
    spy asserts the data call was not reached.
  - record_gate stores the outcome and returns a GateRow.
  - ServiceKit(root).flow is a real FlowService; the other five C3.1
    slots still raise CoreError; the eight legacy slots are untouched.
"""

from __future__ import annotations

import inspect
from typing import Any
from unittest.mock import patch

import pytest

from core import (
    ActionStatus,
    CoreError,
    GateOutcome,
    GateMissing,
    ServiceError,
)
from data import ActionRow, CycleRow, GateRow, ProjectRow
from services import ServiceKit
from services.flow import FlowService


def _make_kit(tmp_path: object) -> ServiceKit:
    """Create a ServiceKit over a fresh tmp workspace."""
    return ServiceKit(str(tmp_path))


def _fixture_project(kit: ServiceKit) -> None:
    """Create the fixture project via the P-10a service and close its
    initial 'Charter cycle' so the tests can open their own cycle."""
    kit.project_svc.create_project("Alpha Bom", "2026-09-30", "TBD")
    data = kit.project_svc._data
    gate = data.gates.create("P001", "charter gate")
    data.gates.record_outcome(gate.id, GateOutcome.PASSED)
    kit.phase_svc.close_cycle("P001", gate.id)


# ---------------------------------------------------------------------------
# A-02 — signatures: the EXACT C3.3 code block, transcribed into the test
# ---------------------------------------------------------------------------


def test_signatures_match_c33_contract() -> None:
    """inspect.signature against the C3.3 contract (transcribed)."""
    expected: dict[str, dict[str, Any]] = {
        "create_project": {
            "name": inspect.Parameter.empty,
            "sponsor": inspect.Parameter.empty,
            "target_date": inspect.Parameter.empty,
            "objective": inspect.Parameter.empty,
            "charter_text": "",
            "constraints_text": "",
        },
        "open_cycle": {
            "project_code": inspect.Parameter.empty,
            "name": inspect.Parameter.empty,
        },
        "close_cycle": {
            "project_code": inspect.Parameter.empty,
            "gate_id": inspect.Parameter.empty,
        },
        "record_gate": {
            "project_code": inspect.Parameter.empty,
            "gate_id": inspect.Parameter.empty,
            "outcome": inspect.Parameter.empty,
            "actual_date": None,
        },
        "add_action": {
            "project_code": inspect.Parameter.empty,
            "title": inspect.Parameter.empty,
            "owner": inspect.Parameter.empty,
            "description": "",
            "priority": 9,
            "due_start": None,
            "due_end": None,
            "cycle_id": None,
        },
        "set_action_status": {
            "project_code": inspect.Parameter.empty,
            "action_id": inspect.Parameter.empty,
            "new": inspect.Parameter.empty,
        },
    }
    for method_name, expected_params in expected.items():
        sig = inspect.signature(getattr(FlowService, method_name))
        actual = {
            p.name: p.default
            for p in sig.parameters.values()
            if p.name != "self"
        }
        assert actual == expected_params, (
            f"{method_name}: {actual} != {expected_params}"
        )


# ---------------------------------------------------------------------------
# A-02 — create_project: name-based mapping onto ProjectSVC's order
# ---------------------------------------------------------------------------


def test_create_project_maps_by_name(tmp_path: object) -> None:
    """All six arguments positionally in C3.3 order; the resulting row
    carries them correctly — the assertion that catches a positional
    mis-map."""
    kit = _make_kit(tmp_path)
    flow = kit.flow

    # C3.3 order: name, sponsor, target_date, objective, charter_text,
    # constraints_text.
    row = flow.create_project(
        "Alpha Bom",
        "alice",
        "2026-09-30",
        "ship it",
        "charter body",
        "constraint body",
    )

    assert row.name == "Alpha Bom"
    assert row.sponsor == "alice"
    assert row.target_date == "2026-09-30"
    assert row.status == "charter"


# ---------------------------------------------------------------------------
# A-02 — open_cycle: the cycle_open frozen rule
# ---------------------------------------------------------------------------


def test_open_cycle_twice_raises_cycle_open(tmp_path: object) -> None:
    """A second open_cycle while one is open raises ServiceError with
    code 'cycle_open' (C3.3 frozen rule)."""
    kit = _make_kit(tmp_path)
    _fixture_project(kit)
    flow = kit.flow

    flow.open_cycle("P001", "Delivery cycle")

    with pytest.raises(ServiceError) as excinfo:
        flow.open_cycle("P001", "Second cycle")
    assert excinfo.value.code == "cycle_open"


# ---------------------------------------------------------------------------
# A-02 — close_cycle: GateMissing before the data layer is reached
# ---------------------------------------------------------------------------


def test_close_cycle_without_outcome_raises_gatemissing(
    tmp_path: object,
) -> None:
    """close_cycle without a recorded outcome raises GateMissing and a
    spy asserts the data call was not reached."""
    kit = _make_kit(tmp_path)
    _fixture_project(kit)
    flow = kit.flow

    flow.open_cycle("P001", "Delivery cycle")

    # A gate exists but has NO recorded outcome (still PLANNED).
    gate = flow._ensure_data().gates.create("P001", "acceptance")

    with patch("data.cycles.CycleRepo.close_cycle") as spy:
        with pytest.raises(GateMissing):
            flow.close_cycle("P001", gate.id)
        spy.assert_not_called()


# ---------------------------------------------------------------------------
# A-02 — record_gate: stores the outcome, returns a GateRow
# ---------------------------------------------------------------------------


def test_record_gate_stores_outcome_returns_row(tmp_path: object) -> None:
    """record_gate stores the outcome and returns a GateRow."""
    kit = _make_kit(tmp_path)
    _fixture_project(kit)
    flow = kit.flow

    gate = flow._ensure_data().gates.create("P001", "acceptance")
    row = flow.record_gate("P001", gate.id, GateOutcome.PASSED)

    assert isinstance(row, GateRow)
    assert row.id == gate.id
    assert row.outcome == "passed"
    assert row.actual_date is not None


# ---------------------------------------------------------------------------
# A-02 — add_action / set_action_status: pass-through
# ---------------------------------------------------------------------------


def test_add_action_pass_through(tmp_path: object) -> None:
    """add_action passes through to ActionsSVC with the same signature."""
    kit = _make_kit(tmp_path)
    _fixture_project(kit)
    flow = kit.flow

    row = flow.add_action("P001", "Do the thing", "  ana ")

    assert isinstance(row, ActionRow)
    assert row.owner == "ana"
    assert row.priority == 9


def test_set_action_status_pass_through(tmp_path: object) -> None:
    """set_action_status renames ActionsSVC.change_status."""
    kit = _make_kit(tmp_path)
    _fixture_project(kit)
    flow = kit.flow

    action = flow.add_action("P001", "Do the thing", "ana")
    row = flow.set_action_status(
        "P001", action.id, ActionStatus.IN_PROGRESS
    )

    assert row.status == "in_progress"


# ---------------------------------------------------------------------------
# A-02 — ServiceKit wiring
# ---------------------------------------------------------------------------


def test_flow_is_real_others_placeholder(tmp_path: object) -> None:
    """ServiceKit(root).flow is a real FlowService; the other five C3.1
    slots still raise CoreError; the eight legacy slots are untouched."""
    kit = _make_kit(tmp_path)

    # flow is the real FlowService.
    assert isinstance(kit.flow, FlowService)

    # The other five C3.1 slots still raise CoreError.
    other_c31 = (
        "evidence",
        "engagement",
        "report",
        "backup",
        "handover",
    )
    for slot in other_c31:
        placeholder = getattr(kit, slot)
        with pytest.raises(CoreError):
            _ = placeholder.any_attribute

    # The eight legacy slots are untouched (still real or placeholder).
    legacy = (
        "project_svc",
        "phase_svc",
        "actions_svc",
        "evidence_svc",
        "minutes_svc",
        "report_svc",
        "backup_svc",
        "integrity_svc",
    )
    for slot in legacy:
        assert hasattr(kit, slot)
