"""Contract tests for core.enums (C1.1).

Acceptance (00-ARCHITECTURE.md, core module):
  - Enum values serialize to lowercase strings and back without loss.
  - ALLOWED_ACTION_TRANSITIONS matches the C1.1 addendum exactly.
"""

from __future__ import annotations

from core.enums import (
    ALLOWED_ACTION_TRANSITIONS,
    ActionStatus,
    EventKind,
    GateOutcome,
    ProjectStatus,
    SignalKind,
    SourceType,
)

ALL_ENUMS = (ProjectStatus, EventKind, ActionStatus, GateOutcome, SourceType, SignalKind)


def test_all_members_lowercase_strings() -> None:
    for enum in ALL_ENUMS:
        for member in enum:
            assert isinstance(member.value, str)
            assert member.value == member.value.lower(), f"{member.name} not lowercase"


def test_roundtrip_serialize_back_without_loss() -> None:
    for enum in ALL_ENUMS:
        for member in enum:
            serialized = str(member.value)
            assert enum[member.name].value == serialized
            assert enum(serialized) is member


def test_exact_member_values_per_contract() -> None:
    assert [m.value for m in ProjectStatus] == [
        "charter",
        "active",
        "in_review",
        "delivered",
        "closed",
    ]
    assert [m.value for m in EventKind] == [
        "charter",
        "gate",
        "decision",
        "action_created",
        "action_status",
        "evidence",
        "meeting",
        "signal",
        "report",
        "note",
        "phase",
    ]
    assert [m.value for m in ActionStatus] == [
        "open",
        "in_progress",
        "done",
        "deferred",
        "cancelled",
    ]
    assert [m.value for m in GateOutcome] == [
        "planned",
        "passed",
        "conditionally_passed",
        "failed",
        "skipped",
    ]
    assert [m.value for m in SourceType] == [
        "email",
        "spreadsheet",
        "screenshot",
        "doc",
        "other",
    ]
    assert [m.value for m in SignalKind] == [
        "defer",
        "extension_request",
        "late_start",
        "reopen",
    ]


def test_enums_subclass_str() -> None:
    for enum in ALL_ENUMS:
        for member in enum:
            assert isinstance(member, str)
            assert member == member.value


def test_allowed_action_transitions_exact() -> None:
    expected = {
        ActionStatus.OPEN: (
            ActionStatus.IN_PROGRESS,
            ActionStatus.DONE,
            ActionStatus.DEFERRED,
            ActionStatus.CANCELLED,
        ),
        ActionStatus.IN_PROGRESS: (
            ActionStatus.DONE,
            ActionStatus.DEFERRED,
            ActionStatus.CANCELLED,
            ActionStatus.OPEN,
        ),
        ActionStatus.DONE: (ActionStatus.OPEN,),
        ActionStatus.DEFERRED: (
            ActionStatus.OPEN,
            ActionStatus.IN_PROGRESS,
            ActionStatus.CANCELLED,
        ),
        ActionStatus.CANCELLED: (),
    }
    assert ALLOWED_ACTION_TRANSITIONS == expected
    assert set(ALLOWED_ACTION_TRANSITIONS) == set(ActionStatus)
    for targets in ALLOWED_ACTION_TRANSITIONS.values():
        assert all(isinstance(t, ActionStatus) for t in targets)


def test_cancelled_is_terminal_and_done_only_reopens_to_open() -> None:
    assert ALLOWED_ACTION_TRANSITIONS[ActionStatus.CANCELLED] == ()
    assert ALLOWED_ACTION_TRANSITIONS[ActionStatus.DONE] == (ActionStatus.OPEN,)
