"""Tests for services.phase — card P-10b (phase lifecycle, I3 guard).

Done-when (P-10b):
  - open_cycle creates an open cycle row for the project and emits its
    event (fixture project from the P-10a service, one assertion each).
  - close_cycle happy path: open cycle -> gate 'acceptance' recorded
    PASSED -> close_cycle -> the cycle row is closed and a GATE event is
    present (I3, service side).
  - test_i3_guard_before_data — close_cycle with NO gate raises
    GateMissing and the cycle remains open. The test patches
    data.close_cycle with a spy and asserts the spy was NEVER called:
    the guard runs before the data layer is reached, not after it
    refuses.
  - close_cycle on an already-closed cycle raises ServiceError (not a
    silent no-op).
"""

from __future__ import annotations

from unittest.mock import patch

import pytest

from core import CoreError, GateMissing, GateOutcome, ServiceError
from services import ServiceKit
from services.phase import PhaseSVC


def _make_kit(tmp_path: object) -> ServiceKit:
    """Create a ServiceKit over a fresh tmp workspace."""
    return ServiceKit(str(tmp_path))


def _fixture_project(kit: ServiceKit) -> None:
    """Create the fixture project via the P-10a service and close its
    initial 'Charter cycle' so the tests can open their own cycle."""
    kit.project_svc.create_project("Alpha Bom", "2026-09-30", "TBD")
    # Close the initial 'Charter cycle' (the P-10a service opens it).
    data = kit.project_svc._data
    gate = data.gates.create("P001", "charter gate")
    data.gates.record_outcome(gate.id, GateOutcome.PASSED)
    kit.phase_svc.close_cycle("P001", gate.id)


def test_open_cycle_creates_row_and_emits_event(tmp_path: object) -> None:
    """open_cycle creates an open cycle row and emits its event."""
    kit = _make_kit(tmp_path)
    _fixture_project(kit)
    svc = kit.phase_svc

    cycle = svc.open_cycle("P001", "Delivery cycle")

    # One assertion: the cycle row is open.
    assert cycle.closed_at is None
    assert cycle.name == "Delivery cycle"

    # One assertion: the phase event is present.
    events = svc._data.events.list_for("P001")
    phase_events = [e for e in events if e.kind == "phase"]
    assert len(phase_events) >= 1
    assert any("Delivery cycle" in e.title for e in phase_events)


def test_close_cycle_happy_path(tmp_path: object) -> None:
    """open cycle -> gate recorded PASSED -> close_cycle -> closed row
    and a GATE event present (I3, service side)."""
    kit = _make_kit(tmp_path)
    _fixture_project(kit)
    svc = kit.phase_svc

    cycle = svc.open_cycle("P001", "Delivery cycle")

    # Record the 'acceptance' gate PASSED (via the data layer).
    gate = svc._data.gates.create("P001", "acceptance")
    svc._data.gates.record_outcome(gate.id, GateOutcome.PASSED)

    closed = svc.close_cycle("P001", gate.id)

    # The cycle row is closed.
    assert closed.closed_at is not None
    assert closed.gate_id == gate.id

    # A GATE event is present (I3, service side).
    events = svc._data.events.list_for("P001")
    gate_events = [e for e in events if e.kind == "gate"]
    assert len(gate_events) >= 1


def test_i3_guard_before_data(tmp_path: object) -> None:
    """close_cycle with NO gate raises GateMissing and the cycle remains
    open. data.close_cycle is spied and must NEVER be called: the guard
    runs before the data layer is reached, not after it refuses."""
    kit = _make_kit(tmp_path)
    _fixture_project(kit)
    svc = kit.phase_svc

    svc.open_cycle("P001", "Delivery cycle")

    # A gate exists but has NO recorded outcome (still PLANNED).
    gate = svc._data.gates.create("P001", "acceptance")

    # No gate outcome recorded for this cycle.
    with patch("data.cycles.CycleRepo.close_cycle") as spy:
        with pytest.raises(GateMissing):
            svc.close_cycle("P001", gate.id)
        spy.assert_not_called()

    # The cycle remains open.
    current = svc._data.cycles.current_for("P001")
    assert current is not None
    assert current.closed_at is None


def test_close_cycle_already_closed_raises_serviceerror(
    tmp_path: object,
) -> None:
    """close_cycle on an already-closed cycle raises ServiceError (not a
    silent no-op)."""
    kit = _make_kit(tmp_path)
    _fixture_project(kit)
    svc = kit.phase_svc

    cycle = svc.open_cycle("P001", "Delivery cycle")

    # Record the gate PASSED and close the cycle.
    gate = svc._data.gates.create("P001", "acceptance")
    svc._data.gates.record_outcome(gate.id, GateOutcome.PASSED)
    svc.close_cycle("P001", gate.id)

    # Closing again raises ServiceError (not a silent no-op).
    with pytest.raises(ServiceError):
        svc.close_cycle("P001", gate.id)


def test_phase_svc_is_real_others_placeholder(tmp_path: object) -> None:
    """ServiceKit(tmp).phase_svc is the real PhaseSVC; the other six
    slots still raise CoreError."""
    kit = _make_kit(tmp_path)

    # phase_svc is the real PhaseSVC.
    assert isinstance(kit.phase_svc, PhaseSVC)

    # The other six slots still raise CoreError.
    other_slots = (
        "actions_svc",
        "evidence_svc",
        "minutes_svc",
        "report_svc",
        "backup_svc",
        "integrity_svc",
    )
    for slot in other_slots:
        placeholder = getattr(kit, slot)
        with pytest.raises(CoreError):
            _ = placeholder.any_attribute
