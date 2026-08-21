"""data.rows — the 10 row dataclasses (contract C2.0).

Every field name is the EXACT column name of the corresponding table;
``to_dict()`` returns a ``{column: value}`` mapping in the same order
so repositories can hand rows straight to ``sqlite3``'s named
placeholders.  Skeleton only (card P-05): fields + ``to_dict()``;
no I/O, no repository logic.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass
class ProjectRow:
    """Table ``project`` (C2.0)."""

    code: str
    name: str
    status: str
    charter: str | None
    target: str | None
    target_date: str | None
    status_rag: str | None
    red_flags: str | None
    escalation: str | None
    sponsor: str | None
    created_at: str
    updated_at: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "code": self.code,
            "name": self.name,
            "status": self.status,
            "charter": self.charter,
            "target": self.target,
            "target_date": self.target_date,
            "status_rag": self.status_rag,
            "red_flags": self.red_flags,
            "escalation": self.escalation,
            "sponsor": self.sponsor,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
        }


@dataclass
class CharterRow:
    """Table ``charter`` (C2.0)."""

    id: int
    project_code: str
    revision: int
    body: str
    key_dates: str | None
    created_at: str
    reason: str | None

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "project_code": self.project_code,
            "revision": self.revision,
            "body": self.body,
            "key_dates": self.key_dates,
            "created_at": self.created_at,
            "reason": self.reason,
        }


@dataclass
class EventRow:
    """Table ``event`` (C2.0)."""

    id: int
    project_code: str
    kind: str
    ref_table: str | None
    ref_id: int | None
    title: str
    body: str | None
    occurred_at: str
    created_at: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "project_code": self.project_code,
            "kind": self.kind,
            "ref_table": self.ref_table,
            "ref_id": self.ref_id,
            "title": self.title,
            "body": self.body,
            "occurred_at": self.occurred_at,
            "created_at": self.created_at,
        }


@dataclass
class EvidenceRow:
    """Table ``evidence`` (C2.0)."""

    id: str
    project_code: str
    ref_table: str | None
    ref_id: int | None
    original_name: str
    source_type: str
    rel_path: str
    size_bytes: int
    sha256: str
    attached_at: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "project_code": self.project_code,
            "ref_table": self.ref_table,
            "ref_id": self.ref_id,
            "original_name": self.original_name,
            "source_type": self.source_type,
            "rel_path": self.rel_path,
            "size_bytes": self.size_bytes,
            "sha256": self.sha256,
            "attached_at": self.attached_at,
        }


@dataclass
class DecisionRow:
    """Table ``decision`` (C2.0)."""

    id: int
    project_code: str
    event_id: int
    revision: int
    body: str
    created_at: str
    reason: str | None

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "project_code": self.project_code,
            "event_id": self.event_id,
            "revision": self.revision,
            "body": self.body,
            "created_at": self.created_at,
            "reason": self.reason,
        }


@dataclass
class ActionRow:
    """Table ``action`` (C2.0)."""

    id: int
    project_code: str
    description: str
    owner: str
    priority: int
    due: str | None
    status: str
    event_id: int
    reopen_count: int
    created_at: str
    updated_at: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "project_code": self.project_code,
            "description": self.description,
            "owner": self.owner,
            "priority": self.priority,
            "due": self.due,
            "status": self.status,
            "event_id": self.event_id,
            "reopen_count": self.reopen_count,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
        }


@dataclass
class CycleRow:
    """Table ``cycle`` (C2.0)."""

    id: int
    project_code: str
    name: str
    gate_id: int | None
    closed_at: str | None
    validated: int
    validated_at: str | None
    created_at: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "project_code": self.project_code,
            "name": self.name,
            "gate_id": self.gate_id,
            "closed_at": self.closed_at,
            "validated": self.validated,
            "validated_at": self.validated_at,
            "created_at": self.created_at,
        }


@dataclass
class CycleItemRow:
    """Table ``cycle_item`` (C2.0)."""

    id: int
    cycle_id: int
    project_code: str
    action_id: int
    rank: int
    created_at: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "cycle_id": self.cycle_id,
            "project_code": self.project_code,
            "action_id": self.action_id,
            "rank": self.rank,
            "created_at": self.created_at,
        }


@dataclass
class GateRow:
    """Table ``gate`` (C2.0)."""

    id: int
    project_code: str
    event_id: int
    name: str
    outcome: str
    planned_date: str | None
    actual_date: str | None
    created_at: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "project_code": self.project_code,
            "event_id": self.event_id,
            "name": self.name,
            "outcome": self.outcome,
            "planned_date": self.planned_date,
            "actual_date": self.actual_date,
            "created_at": self.created_at,
        }


@dataclass
class GateItemRow:
    """Table ``gate_item`` (C2.0)."""

    id: int
    gate_id: int
    project_code: str
    text: str
    passed: int
    created_at: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "gate_id": self.gate_id,
            "project_code": self.project_code,
            "text": self.text,
            "passed": self.passed,
            "created_at": self.created_at,
        }


__all__ = [
    "ActionRow",
    "CharterRow",
    "CycleItemRow",
    "CycleRow",
    "DecisionRow",
    "EventRow",
    "EvidenceRow",
    "GateItemRow",
    "GateRow",
    "ProjectRow",
]
