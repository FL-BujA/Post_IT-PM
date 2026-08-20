"""core.enums — exact member values, frozen by contract C1.1.

API payloads use these exact lowercase strings. All enums subclass ``str``
so they serialize to plain strings without loss and round-trip via
``Enum[value]``.

The C1.1 addendum: the action state machine (``ALLOWED_ACTION_TRANSITIONS``)
lives here so BOTH the data layer and any future tooling validate
transitions from one place.
"""

from __future__ import annotations

from enum import Enum

__all__ = [
    "ProjectStatus",
    "EventKind",
    "ActionStatus",
    "GateOutcome",
    "SourceType",
    "SignalKind",
    "ALLOWED_ACTION_TRANSITIONS",
]


class ProjectStatus(str, Enum):
    CHARTER = "charter"
    ACTIVE = "active"
    IN_REVIEW = "in_review"
    DELIVERED = "delivered"
    CLOSED = "closed"


class EventKind(str, Enum):
    CHARTER = "charter"
    GATE = "gate"
    DECISION = "decision"
    ACTION_CREATED = "action_created"
    ACTION_STATUS = "action_status"
    EVIDENCE = "evidence"
    MEETING = "meeting"
    SIGNAL = "signal"
    REPORT = "report"
    NOTE = "note"
    PHASE = "phase"


class ActionStatus(str, Enum):
    OPEN = "open"
    IN_PROGRESS = "in_progress"
    DONE = "done"
    DEFERRED = "deferred"
    CANCELLED = "cancelled"


class GateOutcome(str, Enum):
    PLANNED = "planned"
    PASSED = "passed"
    CONDITIONALLY_PASSED = "conditionally_passed"
    FAILED = "failed"
    SKIPPED = "skipped"


class SourceType(str, Enum):
    EMAIL = "email"
    SPREADSHEET = "spreadsheet"
    SCREENSHOT = "screenshot"
    DOC = "doc"
    OTHER = "other"


class SignalKind(str, Enum):
    DEFER = "defer"
    EXTENSION_REQUEST = "extension_request"
    LATE_START = "late_start"
    REOPEN = "reopen"


# C1.1 addendum — the action state machine (frozen):
#   open        -> (in_progress, done, deferred, cancelled)
#   in_progress -> (done, deferred, cancelled, open)
#   done        -> (open,)                       # reopen: see invariant I4
#   deferred    -> (open, in_progress, cancelled)
#   cancelled   -> ()                            # terminal
ALLOWED_ACTION_TRANSITIONS: dict[ActionStatus, tuple[ActionStatus, ...]] = {
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
