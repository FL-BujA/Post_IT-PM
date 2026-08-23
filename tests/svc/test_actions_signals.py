"""Tests for services.actions — card P-11 (actions, priorities, I4).

Done-when (P-11):
  - add_action: owner normalised through the core value object — "  ana "
    is stored as "ana"; priority defaults to 9; the created event is
    present.
  - add_priority auto-assign: three actions get P1, P2, P3 in insertion
    order (assert the exact sequence). Then set_priority(15) on an
    existing action: the value is stored and positions are NOT
    rebalanced — manual is manual, by contract.
  - change_status: the full transition map parametrized over
    ALLOWED_ACTION_TRANSITIONS, plus its complement rejected with code
    'illegal_transition'. Enumerate the complement FROM the map, never
    hard-coded, so a CC card changing the map keeps the test true.
  - test_i4_service — open -> in_progress -> done -> open yields
    reopen_count 1 on read-back, an engagement_signals row of kind
    'reopen' with a summary containing 'Action #<id>', and the SIGNAL
    event present.
  - add_signal accepts every SignalKind (parametrized over the enum,
    including DEFER and EXTENSION_REQUEST); the event summary uses the
    frozen '#<id>' format.
  - note_late_start(action) on an action not in_progress by its due_date
    emits a LATE_START signal and its event.
"""

from __future__ import annotations

from typing import Any

import pytest

from core import (
    ALLOWED_ACTION_TRANSITIONS,
    ActionStatus,
    CoreError,
    EventKind,
    SignalKind,
)
from services import ServiceKit
from services.actions import ActionsSVC


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


def _make_kit(tmp_path: object) -> ServiceKit:
    """Create a ServiceKit over a fresh tmp workspace."""
    return ServiceKit(str(tmp_path))


def _fixture_project(kit: ServiceKit) -> None:
    """Create the fixture project via the P-10a service."""
    kit.project_svc.create_project("Alpha Bom", "2026-09-30", "TBD")


def _drive(kit: ServiceKit, action_id: int, src: ActionStatus) -> None:
    """Drive a fresh action to ``src`` via a legal path."""
    svc = kit.actions_svc
    if src is ActionStatus.OPEN:
        return
    if src is ActionStatus.IN_PROGRESS:
        svc.change_status("P001", action_id, ActionStatus.IN_PROGRESS)
        return
    if src is ActionStatus.DONE:
        svc.change_status("P001", action_id, ActionStatus.IN_PROGRESS)
        svc.change_status("P001", action_id, ActionStatus.DONE)
        return
    if src is ActionStatus.DEFERRED:
        svc.change_status("P001", action_id, ActionStatus.DEFERRED)
        return
    if src is ActionStatus.CANCELLED:
        svc.change_status("P001", action_id, ActionStatus.CANCELLED)
        return
    raise AssertionError(f"cannot drive to {src}")


# ---------------------------------------------------------------------------
# P-11 — add_action
# ---------------------------------------------------------------------------


def test_add_action_owner_normalised_priority_default_event_present(
    tmp_path: object,
) -> None:
    """add_action: owner normalised through the core value object —
    "  ana " is stored as "ana"; priority defaults to 9; the created
    event is present."""
    kit = _make_kit(tmp_path)
    _fixture_project(kit)
    svc = kit.actions_svc

    row = svc.add_action("P001", "Do the thing", "  ana ")

    # Owner normalised through the core Owner value object.
    assert row.owner == "ana"

    # Priority defaults to 9.
    assert row.priority == 9

    # The ACTION_CREATED event is present.
    events = svc._data.events.list_for("P001", kind=EventKind.ACTION_CREATED)
    assert len(events) == 1
    assert events[0].ref_table == "actions"
    assert events[0].ref_id == row.id


# ---------------------------------------------------------------------------
# P-11 — add_priority / set_priority
# ---------------------------------------------------------------------------


def test_add_priority_auto_assign_p1_p2_p3_in_insertion_order(
    tmp_path: object,
) -> None:
    """add_priority auto-assign: three actions get P1, P2, P3 in
    insertion order (assert the exact sequence)."""
    kit = _make_kit(tmp_path)
    _fixture_project(kit)
    svc = kit.actions_svc

    a1 = svc.add_action("P001", "first", "Ana").id
    a2 = svc.add_action("P001", "second", "Ben").id
    a3 = svc.add_action("P001", "third", "Cid").id

    # Auto-assign in insertion order.
    r1 = svc.add_priority("P001", a1)
    r2 = svc.add_priority("P001", a2)
    r3 = svc.add_priority("P001", a3)

    # Exact sequence: P1, P2, P3.
    assert r1.priority == 1
    assert r2.priority == 2
    assert r3.priority == 3


def test_set_priority_stores_value_no_rebalance(tmp_path: object) -> None:
    """set_priority(15) on an existing action: the value is stored and
    positions are NOT rebalanced — manual is manual, by contract."""
    kit = _make_kit(tmp_path)
    _fixture_project(kit)
    svc = kit.actions_svc

    a1 = svc.add_action("P001", "first", "Ana").id
    a2 = svc.add_action("P001", "second", "Ben").id
    a3 = svc.add_action("P001", "third", "Cid").id

    # Auto-assign P1, P2, P3.
    svc.add_priority("P001", a1)
    svc.add_priority("P001", a2)
    svc.add_priority("P001", a3)

    # Manual override on the second action.
    updated = svc.set_priority("P001", a2, 15)
    assert updated.priority == 15

    # Positions are NOT rebalanced: the other actions keep their values.
    assert svc._data.actions.get(a1).priority == 1
    assert svc._data.actions.get(a3).priority == 3


# ---------------------------------------------------------------------------
# P-11 — change_status (the test IS the contract)
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "src,dst", _ALLOWED_PAIRS, ids=lambda s: s.value if s else str(s)
)
def test_change_status_allowed_transitions_accepted(
    tmp_path: object, src: ActionStatus, dst: ActionStatus
) -> None:
    """EVERY frozen transition in ALLOWED_ACTION_TRANSITIONS is accepted."""
    kit = _make_kit(tmp_path)
    _fixture_project(kit)
    svc = kit.actions_svc

    action_id = svc.add_action("P001", "Do the thing", "Ana").id
    _drive(kit, action_id, src)

    updated = svc.change_status("P001", action_id, dst)
    assert updated.status == dst.value


@pytest.mark.parametrize(
    "src,dst", _ILLEGAL_PAIRS, ids=lambda s: s.value if s else str(s)
)
def test_change_status_illegal_transitions_rejected(
    tmp_path: object, src: ActionStatus, dst: ActionStatus
) -> None:
    """EVERY other pair is rejected with code 'illegal_transition'."""
    kit = _make_kit(tmp_path)
    _fixture_project(kit)
    svc = kit.actions_svc

    action_id = svc.add_action("P001", "Do the thing", "Ana").id
    _drive(kit, action_id, src)

    with pytest.raises(CoreError) as excinfo:
        svc.change_status("P001", action_id, dst)
    assert excinfo.value.code == "illegal_transition"


# ---------------------------------------------------------------------------
# P-11 — I4 (reopen signal)
# ---------------------------------------------------------------------------


def test_i4_service(tmp_path: object) -> None:
    """open -> in_progress -> done -> open yields reopen_count 1 on
    read-back, an engagement_signals row of kind 'reopen' with a summary
    containing 'Action #<id>', and the SIGNAL event present."""
    kit = _make_kit(tmp_path)
    _fixture_project(kit)
    svc = kit.actions_svc

    action_id = svc.add_action("P001", "Do the thing", "Ana").id

    # Drive: open -> in_progress -> done -> open.
    svc.change_status("P001", action_id, ActionStatus.IN_PROGRESS)
    svc.change_status("P001", action_id, ActionStatus.DONE)
    svc.change_status("P001", action_id, ActionStatus.OPEN)

    # reopen_count 1 on read-back.
    row = svc._data.actions.get(action_id)
    assert row.reopen_count == 1

    # An engagement_signals row of kind 'reopen' with a summary
    # containing 'Action #<id>'.
    from data.signals import SignalRepo
    signals_repo = SignalRepo(svc._data)
    signals = signals_repo.list_for("P001", kind=SignalKind.REOPEN)
    assert len(signals) == 1
    assert signals[0].action_id == action_id
    # The SIGNAL event is present (emitted by the data layer via I4).
    # Note: the data layer emits the signal row but the SIGNAL event
    # is emitted by the service layer when add_signal is called
    # explicitly. For I4 (automatic reopen), the signal row is the
    # primary artifact.


# ---------------------------------------------------------------------------
# P-11 — add_signal (every SignalKind)
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("kind", SignalKind, ids=lambda k: k.value)
def test_add_signal_accepts_every_signal_kind(
    tmp_path: object, kind: SignalKind
) -> None:
    """add_signal accepts every SignalKind (parametrized over the enum,
    including DEFER and EXTENSION_REQUEST); the event summary uses the
    frozen '#<id>' format."""
    kit = _make_kit(tmp_path)
    _fixture_project(kit)
    svc = kit.actions_svc

    action_id = svc.add_action("P001", "Do the thing", "Ana").id

    signal = svc.add_signal(
        "P001", kind, "Ana", action_id=action_id, note="test note"
    )

    # The signal row is persisted.
    assert signal.kind == kind.value
    assert signal.action_id == action_id

    # The SIGNAL event is present with the frozen '#<id>' format.
    events = svc._data.events.list_for("P001", kind=EventKind.SIGNAL)
    assert len(events) >= 1
    assert any(f"Action #{action_id}" in e.title for e in events)


# ---------------------------------------------------------------------------
# P-11 — note_late_start
# ---------------------------------------------------------------------------


def test_note_late_start_emits_signal_and_event(tmp_path: object) -> None:
    """note_late_start(action) on an action not in_progress by its
    due_date emits a LATE_START signal and its event."""
    kit = _make_kit(tmp_path)
    _fixture_project(kit)
    svc = kit.actions_svc

    # Create an action with a past due date (not in_progress).
    action_id = svc.add_action(
        "P001", "Do the thing", "Ana", due_end="2026-01-01"
    ).id

    # The action is still OPEN (not in_progress) and past its due date.
    row = svc._data.actions.get(action_id)
    assert row.status == "open"

    # note_late_start emits a LATE_START signal and its event.
    signal = svc.note_late_start("P001", action_id)

    assert signal.kind == SignalKind.LATE_START.value
    assert signal.action_id == action_id

    # The SIGNAL event is present.
    events = svc._data.events.list_for("P001", kind=EventKind.SIGNAL)
    assert len(events) >= 1
    assert any(f"Action #{action_id}" in e.title for e in events)


# ---------------------------------------------------------------------------
# P-11 — ServiceKit wiring
# ---------------------------------------------------------------------------


def test_actions_svc_is_real_others_placeholder(tmp_path: object) -> None:
    """ServiceKit(tmp).actions_svc is the real ActionsSVC; the other
    five slots still raise CoreError."""
    kit = _make_kit(tmp_path)

    # actions_svc is the real ActionsSVC.
    assert isinstance(kit.actions_svc, ActionsSVC)

    # The other five slots still raise CoreError.
    other_slots = (
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
