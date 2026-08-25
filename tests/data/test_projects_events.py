"""Tests for data.projects + data.events and the C2.1 assembly — card P-06.

Done-when (P-06):
  - Project: create -> get -> list order; code UNIQUE (second create
    'P001' raises DataError 'unique_violation'); get by unknown id/code
    raises UnknownProjectData (isinstance DataError AND code check);
  - set_status validates against enums (good + bad — bad raises
    ServiceError code 'invalid_status');
  - Event: emit with ref_table 'actions' + ref_id; list_for returns
    occurred_at ASC, id ASC (3 out-of-order inserts); list_for with kind
    filter; limit honored; 'note'/'charter' events allowed with
    ref_table None (I1 shape, both allowed forms asserted);
  - DataKit(tmp): data.projects and data.events are the real classes
    (type assertion); data.cycles etc. still the placeholder — and a test
    confirms the placeholder raises CoreError not AttributeError;
  - single connection: DataKit holds ONE sqlite3.Connection (test
    inspects the attribute) — no repo opens its own handle (C2.1).
"""

from __future__ import annotations

import sqlite3
from typing import Any

import pytest

from core.enums import EventKind, ProjectStatus
from core.errors import (
    DataError,
    ServiceError,
    UnknownProjectData,
)
from data.db import DataKit
from data.events import EventRepo
from data.migrate import migrate
from data.projects import ProjectRepo


def _kit(tmp_path: Any) -> DataKit:
    db = str(tmp_path / "app.db")
    migrate(db)
    return DataKit(db)


# ---------------------------------------------------------------------------
# P-06 — ProjectRepo
# ---------------------------------------------------------------------------


def test_project_create_get_roundtrip(tmp_path: Any) -> None:
    kit = _kit(tmp_path)
    row = kit.projects.create("P001", "Alpha", ProjectStatus.CHARTER)
    assert row.code == "P001"
    assert row.name == "Alpha"
    assert row.status == "charter"

    got = kit.projects.get("P001")
    assert got.code == row.code
    assert got.name == row.name
    assert got.status == row.status
    assert got.created_at == row.created_at
    assert got.updated_at == row.updated_at


def test_project_list_is_code_ascending(tmp_path: Any) -> None:
    kit = _kit(tmp_path)
    for code in ("P003", "P001", "P002"):
        kit.projects.create(code, f"proj {code}")
    codes = [row.code for row in kit.projects.list()]
    assert codes == ["P001", "P002", "P003"]


def test_project_second_create_same_code_raises_unique_violation(tmp_path: Any) -> None:
    kit = _kit(tmp_path)
    kit.projects.create("P001", "Alpha")
    with pytest.raises(DataError) as excinfo:
        kit.projects.create("P001", "Alpha again")
    assert excinfo.value.code == "unique_violation"
    assert isinstance(excinfo.value, DataError)


def test_project_get_unknown_code_raises_unknown_project_data(tmp_path: Any) -> None:
    kit = _kit(tmp_path)
    kit.projects.create("P001", "Alpha")
    with pytest.raises(UnknownProjectData) as excinfo:
        kit.projects.get("NOPE")
    assert isinstance(excinfo.value, DataError)
    assert excinfo.value.code == "unknown_project"


def test_project_set_status_good_value(tmp_path: Any) -> None:
    kit = _kit(tmp_path)
    kit.projects.create("P001", "Alpha", ProjectStatus.CHARTER)
    updated = kit.projects.set_status("P001", ProjectStatus.ACTIVE)
    assert updated.status == "active"
    assert kit.projects.get("P001").status == "active"


def test_project_set_status_bad_value_raises_invalid_status(tmp_path: Any) -> None:
    kit = _kit(tmp_path)
    kit.projects.create("P001", "Alpha")
    with pytest.raises(ServiceError) as excinfo:
        kit.projects.set_status("P001", "sideways")
    assert excinfo.value.code == "invalid_status"
    # The bad value must not have been written.
    assert kit.projects.get("P001").status == "charter"


def test_project_set_status_unknown_project(tmp_path: Any) -> None:
    kit = _kit(tmp_path)
    with pytest.raises(UnknownProjectData) as excinfo:
        kit.projects.set_status("NOPE", ProjectStatus.ACTIVE)
    assert isinstance(excinfo.value, DataError)
    assert excinfo.value.code == "unknown_project"


# ---------------------------------------------------------------------------
# P-06 — EventRepo
# ---------------------------------------------------------------------------


def test_event_emit_with_ref_table_actions(tmp_path: Any) -> None:
    kit = _kit(tmp_path)
    kit.projects.create("P001", "Alpha")
    row = kit.events.emit(
        "P001",
        EventKind.ACTION_STATUS,
        "action moved",
        ref_table="actions",
        ref_id=3,
        body="open -> done",
        occurred_at="2026-08-21T01:00:00+00:00",
    )
    assert row.id > 0
    assert row.ref_table == "actions"
    assert row.ref_id == 3
    assert row.kind == "action_status"

    stored = kit.conn.execute(
        "SELECT ref_table, ref_id FROM event WHERE id = ?", (row.id,)
    ).fetchone()
    assert stored == ("actions", 3)


def test_event_list_for_orders_occurred_at_asc_id_asc(tmp_path: Any) -> None:
    kit = _kit(tmp_path)
    kit.projects.create("P001", "Alpha")
    # 3 out-of-order inserts (occurred_at given explicitly).
    e1 = kit.events.emit(
        "P001", EventKind.NOTE, "first", occurred_at="2026-08-21T03:00:00+00:00"
    )
    e2 = kit.events.emit(
        "P001", EventKind.NOTE, "third", occurred_at="2026-08-21T05:00:00+00:00"
    )
    e3 = kit.events.emit(
        "P001", EventKind.NOTE, "second", occurred_at="2026-08-21T04:00:00+00:00"
    )

    rows = kit.events.list_for("P001")
    assert [row.title for row in rows] == ["first", "second", "third"]
    assert [row.id for row in rows] == [e1.id, e3.id, e2.id]


def test_event_list_for_tie_breaks_by_id_asc(tmp_path: Any) -> None:
    kit = _kit(tmp_path)
    kit.projects.create("P001", "Alpha")
    ts = "2026-08-21T02:00:00+00:00"
    a = kit.events.emit("P001", EventKind.NOTE, "a", occurred_at=ts)
    b = kit.events.emit("P001", EventKind.NOTE, "b", occurred_at=ts)
    c = kit.events.emit("P001", EventKind.NOTE, "c", occurred_at=ts)
    rows = kit.events.list_for("P001")
    assert [row.id for row in rows] == [a.id, b.id, c.id]


def test_event_list_for_kind_filter(tmp_path: Any) -> None:
    kit = _kit(tmp_path)
    kit.projects.create("P001", "Alpha")
    kit.events.emit(
        "P001", EventKind.NOTE, "n1", occurred_at="2026-08-21T01:00:00+00:00"
    )
    kit.events.emit(
        "P001", EventKind.GATE, "g1", occurred_at="2026-08-21T02:00:00+00:00"
    )
    kit.events.emit(
        "P001", EventKind.NOTE, "n2", occurred_at="2026-08-21T03:00:00+00:00"
    )
    rows = kit.events.list_for("P001", kind=EventKind.NOTE)
    assert [row.title for row in rows] == ["n1", "n2"]
    assert all(row.kind == "note" for row in rows)
    assert len(kit.events.list_for("P001")) == 3


def test_event_list_for_limit_honored(tmp_path: Any) -> None:
    kit = _kit(tmp_path)
    kit.projects.create("P001", "Alpha")
    for i in range(5):
        kit.events.emit(
            "P001",
            EventKind.NOTE,
            f"note {i}",
            occurred_at=f"2026-08-21T0{i + 1}:00:00+00:00",
        )
    rows = kit.events.list_for("P001", limit=2)
    assert [row.title for row in rows] == ["note 0", "note 1"]


def test_event_note_and_charter_allowed_with_ref_table_none(tmp_path: Any) -> None:
    kit = _kit(tmp_path)
    kit.projects.create("P001", "Alpha")
    # I1 shape: both allowed forms must be legal — paired ref AND
    # ref_table None for note/charter kinds.
    paired = kit.events.emit(
        "P001",
        EventKind.NOTE,
        "paired",
        ref_table="actions",
        ref_id=7,
        occurred_at="2026-08-21T01:00:00+00:00",
    )
    bare_note = kit.events.emit(
        "P001", EventKind.NOTE, "bare note", occurred_at="2026-08-21T02:00:00+00:00"
    )
    bare_charter = kit.events.emit(
        "P001",
        EventKind.CHARTER,
        "charter event",
        occurred_at="2026-08-21T03:00:00+00:00",
    )
    assert paired.ref_table == "actions" and paired.ref_id == 7
    assert bare_note.ref_table is None and bare_note.ref_id is None
    assert bare_charter.ref_table is None and bare_charter.ref_id is None

    stored = kit.conn.execute(
        "SELECT ref_table, ref_id FROM event WHERE id IN (?, ?)",
        (bare_note.id, bare_charter.id),
    ).fetchall()
    assert stored == [(None, None), (None, None)]


# ---------------------------------------------------------------------------
# P-06 — C2.1 assembly on DataKit
# ---------------------------------------------------------------------------


def test_datakit_assembles_real_projects_and_events(tmp_path: Any) -> None:
    kit = _kit(tmp_path)
    assert type(kit.projects) is ProjectRepo
    assert type(kit.events) is EventRepo


def test_datakit_holds_one_sqlite_connection(tmp_path: Any) -> None:
    kit = _kit(tmp_path)
    # The single connection is the one DataKit owns (C2.1 frozen rule).
    assert isinstance(kit.conn, sqlite3.Connection)
    assert kit.projects._conn is kit.conn
    assert kit.events._conn is kit.conn
