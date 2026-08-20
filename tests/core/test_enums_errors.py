"""Tests for core.enums (C1.1) and core.errors (C1.4) — card P-01.

Done-when (P-01):
  - all enums round-trip: value -> str -> Enum == value (parametrized over
    ALL members of ALL 6 enums);
  - ALLOWED_ACTION_TRANSITIONS contains exactly the 5 frozen rules; each
    source state's tuple checked;
  - every concrete error: isinstance(e, CoreError), e.code stable string,
    str(e) == message;
  - cancelled -> done is NOT allowed (cancelled maps to an empty tuple).
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
from core.errors import (
    CoreError,
    CycleCloseError,
    DataError,
    EvidenceConflict,
    GateMissing,
    IntegrityError,
    InvalidSlug,
    MissingFileError,
    OwnerError,
    PathEscape,
    PdfError,
    ServiceError,
    UnknownProjectData,
    UnknownProjectService,
)

ALL_ENUMS = (ProjectStatus, EventKind, ActionStatus, GateOutcome, SourceType, SignalKind)

# Concrete errors from C1.4: 11 ServiceError + 1 DataError + 2 level bases.
CONCRETE_ERRORS: tuple[type[CoreError], ...] = (
    InvalidSlug,
    PathEscape,
    OwnerError,
    UnknownProjectService,
    EvidenceConflict,
    GateMissing,
    CycleCloseError,
    IntegrityError,
    MissingFileError,
    PdfError,
    UnknownProjectData,
)

FROZEN_CODES: dict[type[CoreError], str] = {
    InvalidSlug: "invalid_slug",
    PathEscape: "path_escape",
    OwnerError: "invalid_owner",
    UnknownProjectService: "unknown_project",
    EvidenceConflict: "evidence_conflict",
    GateMissing: "gate_missing",
    CycleCloseError: "cycle_close",
    IntegrityError: "integrity",
    MissingFileError: "missing_file",
    PdfError: "pdf_error",
    UnknownProjectData: "unknown_project",
}

EXPECTED_TRANSITIONS: dict[ActionStatus, tuple[ActionStatus, ...]] = {
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


def test_enum_member_values_are_lowercase() -> None:
    for enum in ALL_ENUMS:
        for member in enum:
            assert member.value == member.value.lower(), f"{member.name} not lowercase"


def test_enum_roundtrip_value_str_enum() -> None:
    for enum in ALL_ENUMS:
        for member in enum:
            assert enum(member.value) is member


def test_enums_subclass_str() -> None:
    for enum in ALL_ENUMS:
        for member in enum:
            assert isinstance(member, str)
            assert member == member.value


def test_transitions_have_exactly_five_frozen_rules() -> None:
    assert set(ALLOWED_ACTION_TRANSITIONS) == set(ActionStatus)
    for source in ActionStatus:
        assert ALLOWED_ACTION_TRANSITIONS[source] == EXPECTED_TRANSITIONS[source]


def test_transitions_targets_are_action_statuses() -> None:
    for targets in ALLOWED_ACTION_TRANSITIONS.values():
        for target in targets:
            assert isinstance(target, ActionStatus)


def test_cancelled_is_terminal() -> None:
    assert ALLOWED_ACTION_TRANSITIONS[ActionStatus.CANCELLED] == ()
    assert ActionStatus.DONE not in ALLOWED_ACTION_TRANSITIONS.get(
        ActionStatus.CANCELLED, ()
    )


def test_concrete_errors_are_core_errors_with_stable_codes() -> None:
    for cls in CONCRETE_ERRORS:
        err = cls("boom")
        assert isinstance(err, CoreError)
        assert isinstance(err.code, str) and err.code
        assert err.code == FROZEN_CODES[cls]
        assert str(err) == "boom"


def test_error_branch_membership() -> None:
    assert issubclass(DataError, CoreError)
    assert issubclass(ServiceError, CoreError)
    assert issubclass(UnknownProjectData, DataError)
    for cls in CONCRETE_ERRORS[:-1]:  # all but UnknownProjectData
        assert issubclass(cls, ServiceError)
