"""Tests for data.actions + data.evidence — card P-08.

Done-when (P-08):
  - create emits ACTION_CREATED event (ref actions/id); defaults:
    priority 9, status open, reopen_count 0 (asserted on the stored row).
  - state machine: EVERY frozen transition in ALLOWED_ACTION_TRANSITIONS
    accepted (parametrized over the dict — the test IS the contract),
    EVERY other pair rejected with code 'illegal_transition'
    (parametrized over the complement — enumerated from the dict, not
    hard-coded, so the test stays true if a CC card changes the map).
  - I4: open->in_progress->done->open results in reopen_count == 1,
    last_reopened_at set, AND one engagement_signals row kind 'reopen'
    for the action — named test_i4_reopen_emits_signal.
  - started_at set on first in_progress, not on later re-entries;
    closed_at set exactly on the done/deferred/cancelled arrivals
    (assert NULL on open).
  - Evidence: record() persists ALL glue fields; duplicate rel_path ->
    EvidenceConflict (error path AND the FIRST row survives untouched);
    get_by_path round-trip; list_for by project_code.
  - rel_path stored exactly as the input string (no normalization side
    effects — a contract-valid path is passed and equality asserted on
    read-back).
"""

from __future__ import annotations

from typing import Any

import pytest

from core.enums import (
    ALLOWED_ACTION_TRANSITIONS,
    ActionStatus,
    EventKind,
    ProjectStatus,
    SourceType,
)
from core.errors import CoreError, EvidenceConflict, UnknownProjectData
from core.hash import short_id, sha256_bytes
from core.paths import normalize_relpath
from data.actions import ActionRepo
from data.db import DataKit
from data.evidence import EvidenceRepo
from data.migrate import migrate
from data.rows import EvidenceRow

# ---------------------------------------------------------------------------
# parametrization — enumerated from the frozen map, never hard-coded, so
# the tests stay true if a CC card changes ALLOWED_ACTION_TRANSITIONS.
# ---------------------------------------------------------------------------

_ALLOWED_PAIRS: list[tuple[ActionStatus, ActionStatus]] = [
    (src, dst)
    for src, targets in ALLOWED_ACTION_TRANSITIONS.items()
    for dst in targets
]

_ALL_PAIRS: list[tuple[ActionStatus, ActionStatus]] = [
    (src, dst)
    for src in ActionStatus
    for dst in ActionStatus
]

_ILLEGAL_PAIRS: list[tuple[ActionStatus, ActionStatus]] = [
    pair for pair in _ALL_PAIRS if pair not in _ALLOWED_PAIRS
]


def _kit(tmp_path: Any) -> DataKit:
    db = str(tmp_path / "app.db")
    migrate(db)
    return DataKit(db)


def _project(kit: DataKit, code: str = "P001") -> None:
    kit.projects.create(code, f"proj {code}", ProjectStatus.ACTIVE)


def _action(kit: DataKit, code: str = "P001") -> int:
    return kit.actions.create(code, "Do the thing", "Ana").id


def _drive(kit: DataKit, action_id: int, src: ActionStatus) -> None:
    """Drive a fresh action to ``src`` via a legal path."""
    if src is ActionStatus.OPEN:
        return
    if src is ActionStatus.IN_PROGRESS:
        kit.actions.set_status(action_id, ActionStatus.IN_PROGRESS)
        return
    if src is ActionStatus.DONE:
        kit.actions.set_status(action_id, ActionStatus.IN_PROGRESS)
        kit.actions.set_status(action_id, ActionStatus.DONE)
        return
    if src is ActionStatus.DEFERRED:
        kit.actions.set_status(action_id, ActionStatus.DEFERRED)
        return
    if src is ActionStatus.CANCELLED:
        kit.actions.set_status(action_id, ActionStatus.CANCELLED)
        return
    raise AssertionError(f"cannot drive to {src}")


def _stored(kit: DataKit, action_id: int) -> tuple[str, int, str | None, str | None, str | None]:
    """(status, reopen_count, started_at, closed_at, last_reopened_at)."""
    return kit.conn.execute(
        "SELECT status, reopen_count, started_at, closed_at, "
        "last_reopened_at FROM action WHERE id = ?",
        (action_id,),
    ).fetchone()


# ---------------------------------------------------------------------------
# P-08 — assembly
# ---------------------------------------------------------------------------


def test_datakit_assembles_real_actions_and_evidence(tmp_path: Any) -> None:
    kit = _kit(tmp_path)
    assert type(kit.actions) is ActionRepo
    assert type(kit.evidence) is EvidenceRepo
    assert kit.actions._conn is kit.conn
    assert kit.evidence._conn is kit.conn


# ---------------------------------------------------------------------------
# P-08 — ActionRepo.create
# ---------------------------------------------------------------------------


def test_action_create_defaults_and_stored_row(tmp_path: Any) -> None:
    kit = _kit(tmp_path)
    _project(kit)
    row = kit.actions.create("P001", "Do the thing", "Ana")

    assert row.id > 0
    assert row.status == "open"
    assert row.priority == 9
    assert row.reopen_count == 0

    stored = kit.conn.execute(
        "SELECT status, priority, reopen_count, started_at, closed_at, "
        "last_reopened_at FROM action WHERE id = ?",
        (row.id,),
    ).fetchone()
    assert stored == ("open", 9, 0, None, None, None)


def test_action_create_emits_action_created_event_ref_actions_id(
    tmp_path: Any,
) -> None:
    kit = _kit(tmp_path)
    _project(kit)
    row = kit.actions.create("P001", "Do the thing", "Ana")

    events = kit.events.list_for("P001", kind=EventKind.ACTION_CREATED)
    assert len(events) == 1
    event = events[0]
    assert event.ref_table == "actions"
    assert event.ref_id == row.id


def test_action_create_unknown_project(tmp_path: Any) -> None:
    kit = _kit(tmp_path)
    with pytest.raises(UnknownProjectData) as excinfo:
        kit.actions.create("NOPE", "Do the thing", "Ana")
    assert excinfo.value.code == "unknown_project"


def test_action_get_unknown_id(tmp_path: Any) -> None:
    kit = _kit(tmp_path)
    _project(kit)
    with pytest.raises(CoreError) as excinfo:
        kit.actions.get(99999)
    assert excinfo.value.code == "action_unknown"


def test_action_list_for_project(tmp_path: Any) -> None:
    kit = _kit(tmp_path)
    _project(kit)
    a = kit.actions.create("P001", "first", "Ana").id
    b = kit.actions.create("P001", "second", "Ben").id
    kit.projects.create("P002", "proj P002", ProjectStatus.ACTIVE)
    kit.actions.create("P002", "other project", "Ana")

    rows = kit.actions.list_for("P001")
    assert [r.id for r in rows] == [a, b]
    assert all(r.project_code == "P001" for r in rows)


# ---------------------------------------------------------------------------
# P-08 — state machine (the test IS the contract)
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "src,dst", _ALLOWED_PAIRS, ids=lambda s: s.value if s else str(s)
)
def test_allowed_transitions_accepted(tmp_path: Any, src: ActionStatus, dst: ActionStatus) -> None:
    """EVERY frozen transition in ALLOWED_ACTION_TRANSITIONS is accepted."""
    kit = _kit(tmp_path)
    _project(kit)
    action_id = _action(kit)
    _drive(kit, action_id, src)

    updated = kit.actions.set_status(action_id, dst)
    assert updated.status == dst.value
    assert _stored(kit, action_id)[0] == dst.value


@pytest.mark.parametrize(
    "src,dst", _ILLEGAL_PAIRS, ids=lambda s: s.value if s else str(s)
)
def test_illegal_transitions_rejected(tmp_path: Any, src: ActionStatus, dst: ActionStatus) -> None:
    """EVERY other pair is rejected with code 'illegal_transition'."""
    kit = _kit(tmp_path)
    _project(kit)
    action_id = _action(kit)
    _drive(kit, action_id, src)

    with pytest.raises(CoreError) as excinfo:
        kit.actions.set_status(action_id, dst)
    assert excinfo.value.code == "illegal_transition"

    # The row is left untouched by the rejected attempt.
    assert _stored(kit, action_id)[0] == src.value


def test_illegal_pairs_are_the_complement_of_the_frozen_map() -> None:
    """The parametrized complement is exactly the non-frozen pairs.

    With the current frozen map that is 25 pairs (5x5 minus the 13
    allowed); the count is derived from the map, not hard-coded, so the
    test stays true if a CC card changes ALLOWED_ACTION_TRANSITIONS.
    """
    assert len(_ALLOWED_PAIRS) == sum(
        len(targets) for targets in ALLOWED_ACTION_TRANSITIONS.values()
    )
    assert len(_ILLEGAL_PAIRS) == len(_ALL_PAIRS) - len(_ALLOWED_PAIRS)
    assert not set(_ALLOWED_PAIRS) & set(_ILLEGAL_PAIRS)
    assert set(_ALLOWED_PAIRS) | set(_ILLEGAL_PAIRS) == set(_ALL_PAIRS)


def test_set_status_emits_action_status_event(tmp_path: Any) -> None:
    kit = _kit(tmp_path)
    _project(kit)
    action_id = _action(kit)
    kit.actions.set_status(action_id, ActionStatus.IN_PROGRESS)

    events = kit.events.list_for("P001", kind=EventKind.ACTION_STATUS)
    assert len(events) == 1
    assert events[0].ref_table == "actions"
    assert events[0].ref_id == action_id


# ---------------------------------------------------------------------------
# P-08 — invariant I4
# ---------------------------------------------------------------------------


def test_i4_reopen_emits_signal(tmp_path: Any) -> None:
    """I4: open->in_progress->done->open increments reopen_count, sets
    last_reopened_at, AND auto-emits one engagement_signals row of kind
    'reopen' for the action."""
    kit = _kit(tmp_path)
    _project(kit)
    action_id = _action(kit)

    kit.actions.set_status(action_id, ActionStatus.IN_PROGRESS)
    kit.actions.set_status(action_id, ActionStatus.DONE)
    reopened = kit.actions.set_status(action_id, ActionStatus.OPEN)

    assert reopened.status == "open"
    assert reopened.reopen_count == 1

    status, count, started, closed, last_reopened = _stored(kit, action_id)
    assert status == "open"
    assert count == 1
    assert last_reopened is not None
    assert closed is None  # open again: closed_at cleared

    signals = kit.conn.execute(
        "SELECT project_code, owner, kind, action_id, occurred_at, note "
        "FROM engagement_signals WHERE action_id = ?",
        (action_id,),
    ).fetchall()
    assert len(signals) == 1
    assert signals[0][0] == "P001"
    assert signals[0][1] == "Ana"
    assert signals[0][2] == "reopen"
    assert signals[0][3] == action_id
    assert signals[0][4] is not None


def test_i4_second_reopen_increments_to_two(tmp_path: Any) -> None:
    kit = _kit(tmp_path)
    _project(kit)
    action_id = _action(kit)

    for _ in range(2):
        kit.actions.set_status(action_id, ActionStatus.IN_PROGRESS)
        kit.actions.set_status(action_id, ActionStatus.DONE)
        kit.actions.set_status(action_id, ActionStatus.OPEN)

    assert _stored(kit, action_id)[1] == 2
    signals = kit.conn.execute(
        "SELECT COUNT(*) FROM engagement_signals WHERE action_id = ?",
        (action_id,),
    ).fetchone()
    assert signals[0] == 2


def test_i4_no_signal_on_non_reopen_transitions(tmp_path: Any) -> None:
    kit = _kit(tmp_path)
    _project(kit)
    action_id = _action(kit)

    kit.actions.set_status(action_id, ActionStatus.IN_PROGRESS)
    kit.actions.set_status(action_id, ActionStatus.DONE)
    kit.actions.set_status(action_id, ActionStatus.OPEN)
    kit.actions.set_status(action_id, ActionStatus.DEFERRED)
    kit.actions.set_status(action_id, ActionStatus.OPEN)

    # Only the done->open arrivals emit signals (exactly one here).
    signals = kit.conn.execute(
        "SELECT COUNT(*) FROM engagement_signals WHERE action_id = ?",
        (action_id,),
    ).fetchone()
    assert signals[0] == 1


# ---------------------------------------------------------------------------
# P-08 — started_at / closed_at
# ---------------------------------------------------------------------------


def test_started_at_set_on_first_in_progress_only(tmp_path: Any) -> None:
    kit = _kit(tmp_path)
    _project(kit)
    action_id = _action(kit)

    first = kit.actions.set_status(action_id, ActionStatus.IN_PROGRESS)
    first_started = first.started_at if hasattr(first, "started_at") else None
    assert _stored(kit, action_id)[2] is not None
    started_1 = _stored(kit, action_id)[2]

    # Re-enter in_progress via done->open->in_progress: started_at unchanged.
    kit.actions.set_status(action_id, ActionStatus.DONE)
    kit.actions.set_status(action_id, ActionStatus.OPEN)
    kit.actions.set_status(action_id, ActionStatus.IN_PROGRESS)
    started_2 = _stored(kit, action_id)[2]

    assert started_1 is not None
    assert started_2 == started_1
    assert first_started is None  # ActionRow dataclass has no such field


def test_closed_at_set_exactly_on_closing_arrivals(tmp_path: Any) -> None:
    kit = _kit(tmp_path)
    _project(kit)
    action_id = _action(kit)

    # NULL on open (fresh).
    assert _stored(kit, action_id)[3] is None

    # done arrival: set.
    kit.actions.set_status(action_id, ActionStatus.IN_PROGRESS)
    done_at = kit.actions.set_status(action_id, ActionStatus.DONE)
    assert _stored(kit, action_id)[3] is not None
    closed_done = _stored(kit, action_id)[3]

    # open arrival: cleared again.
    kit.actions.set_status(action_id, ActionStatus.OPEN)
    assert _stored(kit, action_id)[3] is None

    # deferred arrival: set.
    kit.actions.set_status(action_id, ActionStatus.DEFERRED)
    assert _stored(kit, action_id)[3] is not None
    closed_deferred = _stored(kit, action_id)[3]

    # cancelled arrival: set.
    kit.actions.set_status(action_id, ActionStatus.CANCELLED)
    assert _stored(kit, action_id)[3] is not None
    closed_cancelled = _stored(kit, action_id)[3]

    # Each closing arrival stamped its own timestamp.
    assert closed_done is not None
    assert closed_deferred is not None
    assert closed_cancelled is not None


def test_closed_at_null_while_action_open(tmp_path: Any) -> None:
    kit = _kit(tmp_path)
    _project(kit)
    action_id = _action(kit)
    kit.actions.set_status(action_id, ActionStatus.IN_PROGRESS)
    assert _stored(kit, action_id)[3] is None
    kit.actions.set_status(action_id, ActionStatus.DONE)
    kit.actions.set_status(action_id, ActionStatus.OPEN)
    assert _stored(kit, action_id)[3] is None


# ---------------------------------------------------------------------------
# P-08 — EvidenceRepo
# ---------------------------------------------------------------------------


def _glue_row(
    project_code: str = "P001",
    rel_path: str = "evidence/P001/2026-08-01_report.pdf",
    **overrides: Any,
) -> EvidenceRow:
    base = dict(
        id=short_id(),
        project_code=project_code,
        ref_table="actions",
        ref_id=7,
        original_name="Report FINAL (v2).pdf",
        source_type=SourceType.DOC.value,
        rel_path=rel_path,
        size_bytes=12345,
        sha256=sha256_bytes(b"evidence-bytes"),
        attached_at="2026-08-01T09:00:00+00:00",
    )
    base.update(overrides)
    return EvidenceRow(**base)


def test_evidence_record_persists_all_glue_fields(tmp_path: Any) -> None:
    kit = _kit(tmp_path)
    _project(kit)
    row = _glue_row()
    stored = kit.evidence.record(row)

    assert stored.id == row.id
    assert stored.project_code == row.project_code
    assert stored.ref_table == row.ref_table
    assert stored.ref_id == row.ref_id
    assert stored.original_name == row.original_name
    assert stored.source_type == row.source_type
    assert stored.rel_path == row.rel_path
    assert stored.size_bytes == row.size_bytes
    assert stored.sha256 == row.sha256
    assert stored.attached_at == row.attached_at

    db = kit.conn.execute(
        "SELECT id, project_code, ref_table, ref_id, original_name, "
        "source_type, rel_path, size_bytes, sha256, attached_at "
        "FROM evidence WHERE id = ?",
        (row.id,),
    ).fetchone()
    assert db == (
        row.id,
        row.project_code,
        row.ref_table,
        row.ref_id,
        row.original_name,
        row.source_type,
        row.rel_path,
        row.size_bytes,
        row.sha256,
        row.attached_at,
    )


def test_evidence_duplicate_rel_path_raises_and_first_survives(
    tmp_path: Any,
) -> None:
    kit = _kit(tmp_path)
    _project(kit)
    first = _glue_row()
    kit.evidence.record(first)

    second = _glue_row(id=short_id(), size_bytes=99999, original_name="other.pdf")
    with pytest.raises(EvidenceConflict) as excinfo:
        kit.evidence.record(second)
    assert excinfo.value.code == "evidence_conflict"

    # The FIRST row survives untouched.
    survivor = kit.evidence.get_by_path(first.rel_path)
    assert survivor.id == first.id
    assert survivor.size_bytes == first.size_bytes
    assert survivor.original_name == first.original_name
    assert survivor.sha256 == first.sha256

    count = kit.conn.execute("SELECT COUNT(*) FROM evidence").fetchone()
    assert count[0] == 1


def test_evidence_get_by_path_round_trip(tmp_path: Any) -> None:
    kit = _kit(tmp_path)
    _project(kit)
    row = _glue_row()
    kit.evidence.record(row)

    back = kit.evidence.get_by_path(row.rel_path)
    assert back.to_dict() == row.to_dict()


def test_evidence_get_by_path_unknown(tmp_path: Any) -> None:
    kit = _kit(tmp_path)
    _project(kit)
    with pytest.raises(CoreError) as excinfo:
        kit.evidence.get_by_path("evidence/P001/2026-08-01_missing.pdf")
    assert excinfo.value.code == "evidence_unknown"


def test_evidence_list_for_by_project_code(tmp_path: Any) -> None:
    kit = _kit(tmp_path)
    kit.projects.create("P001", "proj P001", ProjectStatus.ACTIVE)
    kit.projects.create("P002", "proj P002", ProjectStatus.ACTIVE)

    a = _glue_row(project_code="P001", rel_path="evidence/P001/2026-08-01_a.pdf")
    b = _glue_row(project_code="P001", rel_path="evidence/P001/2026-08-02_b.pdf")
    c = _glue_row(project_code="P002", rel_path="evidence/P002/2026-08-03_c.pdf")
    for row in (a, b, c):
        kit.evidence.record(row)

    rows = kit.evidence.list_for("P001")
    # ids are random short_ids (C1.5) — membership, not order.
    assert sorted(r.id for r in rows) == sorted([a.id, b.id])
    assert all(r.project_code == "P001" for r in rows)
    assert [r.id for r in kit.evidence.list_for("P002")] == [c.id]


def test_evidence_rel_path_stored_verbatim(tmp_path: Any) -> None:
    """rel_path is stored EXACTLY as the input string — no normalization
    side effects (services validated it; data stores it verbatim)."""
    kit = _kit(tmp_path)
    _project(kit)
    # A contract-valid path (normalize_relpath accepts it unchanged).
    input_path = "evidence/P001/2026-08-01_quarterly_report_final.pdf"
    assert normalize_relpath(input_path) == input_path

    row = _glue_row(rel_path=input_path)
    kit.evidence.record(row)

    stored = kit.conn.execute(
        "SELECT rel_path FROM evidence WHERE id = ?", (row.id,)
    ).fetchone()
    assert stored[0] == input_path
    assert kit.evidence.get_by_path(input_path).rel_path == input_path
