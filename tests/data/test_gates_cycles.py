"""Tests for data.gates + data.cycles — card P-07.

Done-when (P-07):
  - Gate lifecycle: create (planned_date NULL allowed) ->
    record_outcome(PASSED) sets outcome + actual_date + emits a GATE
    event (ref_table 'gates', ref_id gate id) — asserted by reading
    the event table.
  - record_outcome on an already-outcomed gate: raises ServiceError
    code 'gate_already_outcomed' (frozen: idempotence is NOT silent).
  - close_cycle(gate PASSED) -> closed_at set, gate linked, cycle's
    GATE event present, cycle row returned.
  - close_cycle on a PLANNED gate -> GateMissing raised, cycle
    UNCHANGED (closed_at still NULL, gate_id still NULL) — the I3
    test, named test_i3_close_requires_outcome.
  - close_cycle with a gate from ANOTHER project -> GateMissing.
  - current_for: one open + one closed -> returns the open one;
    none open -> None.
  - open() emits a PHASE event 'Cycle opened: <name>'.
"""

from __future__ import annotations

from typing import Any

import pytest

from core.enums import EventKind, GateOutcome, ProjectStatus
from core.errors import GateMissing, ServiceError, UnknownProjectData
from data.cycles import CycleRepo
from data.db import DataKit
from data.gates import GateRepo
from data.migrate import migrate


def _kit(tmp_path: Any) -> DataKit:
    db = str(tmp_path / "app.db")
    migrate(db)
    return DataKit(db)


def _project(kit: DataKit, code: str = "P001") -> None:
    kit.projects.create(code, f"proj {code}", ProjectStatus.ACTIVE)


# ---------------------------------------------------------------------------
# P-07 — assembly
# ---------------------------------------------------------------------------


def test_datakit_assembles_real_gates_and_cycles(tmp_path: Any) -> None:
    kit = _kit(tmp_path)
    assert type(kit.gates) is GateRepo
    assert type(kit.cycles) is CycleRepo
    assert kit.gates._conn is kit.conn
    assert kit.cycles._conn is kit.conn


# ---------------------------------------------------------------------------
# P-07 — GateRepo lifecycle
# ---------------------------------------------------------------------------


def test_gate_create_allows_planned_date_null(tmp_path: Any) -> None:
    kit = _kit(tmp_path)
    _project(kit)
    row = kit.gates.create("P001", "Release gate")
    assert row.id > 0
    assert row.outcome == "planned"
    assert row.planned_date is None
    assert row.actual_date is None

    stored = kit.conn.execute(
        "SELECT outcome, planned_date, actual_date FROM gate WHERE id = ?",
        (row.id,),
    ).fetchone()
    assert stored == ("planned", None, None)


def test_gate_create_with_planned_date(tmp_path: Any) -> None:
    kit = _kit(tmp_path)
    _project(kit)
    row = kit.gates.create(
        "P001", "Release gate", planned_date="2026-09-01"
    )
    assert row.planned_date == "2026-09-01"
    stored = kit.conn.execute(
        "SELECT planned_date FROM gate WHERE id = ?", (row.id,)
    ).fetchone()
    assert stored == ("2026-09-01",)


def test_gate_create_unknown_project(tmp_path: Any) -> None:
    kit = _kit(tmp_path)
    with pytest.raises(UnknownProjectData) as excinfo:
        kit.gates.create("NOPE", "Release gate")
    assert excinfo.value.code == "unknown_project"


def test_gate_record_outcome_sets_outcome_and_actual_date(tmp_path: Any) -> None:
    kit = _kit(tmp_path)
    _project(kit)
    gate = kit.gates.create("P001", "Release gate")

    updated = kit.gates.record_outcome(gate.id, GateOutcome.PASSED)
    assert updated.id == gate.id
    assert updated.outcome == "passed"
    assert updated.actual_date is not None

    stored = kit.conn.execute(
        "SELECT outcome, actual_date FROM gate WHERE id = ?", (gate.id,)
    ).fetchone()
    assert stored[0] == "passed"
    assert stored[1] == updated.actual_date


def test_gate_record_outcome_emits_gate_event(tmp_path: Any) -> None:
    kit = _kit(tmp_path)
    _project(kit)
    gate = kit.gates.create("P001", "Release gate")
    kit.gates.record_outcome(gate.id, GateOutcome.PASSED)

    # The GATE event is asserted by reading the event table (timeline).
    rows = kit.conn.execute(
        "SELECT kind, ref_table, ref_id FROM event "
        "WHERE ref_table = 'gates' AND ref_id = ? "
        "AND kind = 'gate' ORDER BY id ASC",
        (gate.id,),
    ).fetchall()
    assert len(rows) >= 1
    assert all(r[0] == "gate" and r[1] == "gates" and r[2] == gate.id for r in rows)
    # The outcome event is the most recent one referencing this gate.
    last = kit.events.list_for("P001", kind=EventKind.GATE)[-1]
    assert last.ref_table == "gates"
    assert last.ref_id == gate.id


def test_gate_second_outcome_raises_already_outcomed(tmp_path: Any) -> None:
    kit = _kit(tmp_path)
    _project(kit)
    gate = kit.gates.create("P001", "Release gate")
    kit.gates.record_outcome(gate.id, GateOutcome.PASSED)

    with pytest.raises(ServiceError) as excinfo:
        kit.gates.record_outcome(gate.id, GateOutcome.FAILED)
    assert excinfo.value.code == "gate_already_outcomed"
    # Frozen: idempotence is NOT silent — the first outcome stands.
    stored = kit.conn.execute(
        "SELECT outcome FROM gate WHERE id = ?", (gate.id,)
    ).fetchone()
    assert stored == ("passed",)


def test_gate_record_outcome_planned_is_rejected(tmp_path: Any) -> None:
    kit = _kit(tmp_path)
    _project(kit)
    gate = kit.gates.create("P001", "Release gate")
    with pytest.raises(ServiceError) as excinfo:
        kit.gates.record_outcome(gate.id, GateOutcome.PLANNED)
    assert excinfo.value.code == "invalid_outcome"


def test_gate_record_outcome_unknown_outcome_value(tmp_path: Any) -> None:
    kit = _kit(tmp_path)
    _project(kit)
    gate = kit.gates.create("P001", "Release gate")
    with pytest.raises(ServiceError) as excinfo:
        kit.gates.record_outcome(gate.id, "sideways")
    assert excinfo.value.code == "invalid_outcome"


def test_gate_get_unknown_id(tmp_path: Any) -> None:
    kit = _kit(tmp_path)
    _project(kit)
    with pytest.raises(ServiceError) as excinfo:
        kit.gates.get(99999)
    assert excinfo.value.code == "gate_unknown"


# ---------------------------------------------------------------------------
# P-07 — CycleRepo
# ---------------------------------------------------------------------------


def test_cycle_open_emits_phase_event(tmp_path: Any) -> None:
    kit = _kit(tmp_path)
    _project(kit)
    row = kit.cycles.open("P001", "Cycle 1")
    assert row.id > 0
    assert row.gate_id is None
    assert row.closed_at is None

    events = kit.events.list_for("P001", kind=EventKind.PHASE)
    assert any(
        e.title == "Cycle opened: Cycle 1" and e.ref_id == row.id for e in events
    )


def test_cycle_open_unknown_project(tmp_path: Any) -> None:
    kit = _kit(tmp_path)
    with pytest.raises(UnknownProjectData) as excinfo:
        kit.cycles.open("NOPE", "Cycle 1")
    assert excinfo.value.code == "unknown_project"


def test_close_cycle_with_passed_gate(tmp_path: Any) -> None:
    kit = _kit(tmp_path)
    _project(kit)
    cycle = kit.cycles.open("P001", "Cycle 1")
    gate = kit.gates.create("P001", "Release gate")
    kit.gates.record_outcome(gate.id, GateOutcome.PASSED)

    closed = kit.cycles.close_cycle(cycle.id, gate.id)
    assert closed.id == cycle.id
    assert closed.gate_id == gate.id
    assert closed.closed_at is not None

    # The gate's GATE event is present in the timeline (read the table).
    gate_events = kit.conn.execute(
        "SELECT kind, ref_table, ref_id FROM event "
        "WHERE ref_table = 'gates' AND ref_id = ?",
        (gate.id,),
    ).fetchall()
    assert gate_events and all(r[0] == "gate" for r in gate_events)

    stored = kit.conn.execute(
        "SELECT gate_id, closed_at FROM cycle WHERE id = ?", (cycle.id,)
    ).fetchone()
    assert stored == (gate.id, closed.closed_at)


def test_i3_close_requires_outcome(tmp_path: Any) -> None:
    """Invariant I3: a cycle cannot be recorded closed without a gate
    outcome.  A PLANNED gate must not close a cycle, and the cycle must
    be left UNCHANGED (closed_at still NULL, gate_id still NULL)."""
    kit = _kit(tmp_path)
    _project(kit)
    cycle = kit.cycles.open("P001", "Cycle 1")
    planned_gate = kit.gates.create("P001", "Release gate")  # outcome: planned

    with pytest.raises(GateMissing) as excinfo:
        kit.cycles.close_cycle(cycle.id, planned_gate.id)
    assert excinfo.value.code == "gate_missing"

    unchanged = kit.cycles.get(cycle.id)
    assert unchanged.gate_id is None
    assert unchanged.closed_at is None


def test_close_cycle_gate_from_another_project(tmp_path: Any) -> None:
    kit = _kit(tmp_path)
    kit.projects.create("P001", "proj P001", ProjectStatus.ACTIVE)
    kit.projects.create("P002", "proj P002", ProjectStatus.ACTIVE)
    cycle = kit.cycles.open("P001", "Cycle 1")
    foreign_gate = kit.gates.create("P002", "Foreign gate")
    kit.gates.record_outcome(foreign_gate.id, GateOutcome.PASSED)

    with pytest.raises(GateMissing):
        kit.cycles.close_cycle(cycle.id, foreign_gate.id)

    unchanged = kit.cycles.get(cycle.id)
    assert unchanged.gate_id is None
    assert unchanged.closed_at is None


def test_close_cycle_unknown_gate(tmp_path: Any) -> None:
    kit = _kit(tmp_path)
    _project(kit)
    cycle = kit.cycles.open("P001", "Cycle 1")
    with pytest.raises(GateMissing):
        kit.cycles.close_cycle(cycle.id, 424242)
    unchanged = kit.cycles.get(cycle.id)
    assert unchanged.gate_id is None
    assert unchanged.closed_at is None


def test_current_for_returns_open_cycle(tmp_path: Any) -> None:
    kit = _kit(tmp_path)
    _project(kit)
    open_cycle = kit.cycles.open("P001", "Cycle 1")
    closed_cycle = kit.cycles.open("P001", "Cycle 2")
    gate = kit.gates.create("P001", "Release gate")
    kit.gates.record_outcome(gate.id, GateOutcome.PASSED)
    kit.cycles.close_cycle(closed_cycle.id, gate.id)

    current = kit.cycles.current_for("P001")
    assert current is not None
    assert current.id == open_cycle.id


def test_current_for_none_when_no_open_cycle(tmp_path: Any) -> None:
    kit = _kit(tmp_path)
    _project(kit)
    cycle = kit.cycles.open("P001", "Cycle 1")
    gate = kit.gates.create("P001", "Release gate")
    kit.gates.record_outcome(gate.id, GateOutcome.PASSED)
    kit.cycles.close_cycle(cycle.id, gate.id)

    assert kit.cycles.current_for("P001") is None
    assert kit.cycles.current_for("P999") is None


def test_cycle_get_unknown_id(tmp_path: Any) -> None:
    kit = _kit(tmp_path)
    _project(kit)
    with pytest.raises(Exception) as excinfo:
        kit.cycles.get(99999)
    assert excinfo.value.code == "cycle_unknown"
