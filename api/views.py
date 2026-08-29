"""api.views — the C4.2 view shapes.

Every route returns one of these, never a raw row. The api's JSON surface is
frozen here so a row change cannot silently alter a response.

DEVIATION (logged in BUILD_STATE.md): five view fields have no source in the
C2 rows and are emitted as null pending a data backfill. The api honours
C4.2's shape; the data behind these keys does not exist yet.

    ActionView.cycle_id, due_start, due_end, started_at, closed_at
        ActionRow carries a single `due` and no cycle link.
    EvidenceView.mime, note
        EvidenceRow carries neither.
    GateView.exit_criteria, notes
        GateRow carries neither; C2.2 specifies them on GateRepo.create.

Two fields are renames rather than gaps, mapped here:
    ActionView.title      <- ActionRow.description
    CycleView.opened_at   <- CycleRow.created_at
"""

from __future__ import annotations

from typing import Any

__all__ = [
    "action_view",
    "cycle_view",
    "evidence_view",
    "gate_view",
    "hit_view",
    "integrity_view",
    "minutes_view",
    "owner_health_view",
    "project_view",
    "report_view",
    "signal_view",
    "snapshot_view",
]

#: Snapshot event cap, per C4.1.
SNAPSHOT_EVENTS = 20


def _enum_str(value: Any) -> Any:
    """Enum members serialise as their value; everything else passes."""
    return getattr(value, "value", value)


def project_view(row: Any) -> dict[str, Any]:
    """C4.2 ProjectView."""
    return {
        "code": row.code,
        "name": row.name,
        "sponsor": row.sponsor,
        "target_date": row.target_date,
        "status": _enum_str(row.status),
        "objective": row.target,          # C2.0 stores the objective as `target`
        "created_at": row.created_at,
    }


def action_view(row: Any) -> dict[str, Any]:
    """C4.2 ActionView. Five keys are null — see the module docstring."""
    return {
        "id": row.id,
        "project_code": row.project_code,
        "cycle_id": None,
        "title": row.description,
        "owner": row.owner,
        "description": row.description,
        "priority": row.priority,
        "due_start": None,
        "due_end": row.due,
        "started_at": None,
        "closed_at": None,
        "status": _enum_str(row.status),
        "reopen_count": row.reopen_count,
    }


def evidence_view(row: Any) -> dict[str, Any]:
    """C4.2 EvidenceView. mime and note are null — see the docstring."""
    return {
        "id": row.id,
        "project_code": row.project_code,
        "rel_path": row.rel_path,
        "sha256": row.sha256,
        "size": row.size_bytes,
        "mime": None,
        "source_type": _enum_str(row.source_type),
        "note": None,
        "attached_at": row.attached_at,
    }


def cycle_view(row: Any) -> dict[str, Any]:
    """C4.2 CycleView."""
    return {
        "id": row.id,
        "project_code": row.project_code,
        "name": row.name,
        "opened_at": row.created_at,
        "closed_at": row.closed_at,
        "gate_id": row.gate_id,
    }


def gate_view(row: Any) -> dict[str, Any]:
    """C4.2 GateView. exit_criteria and notes are null — see the docstring."""
    return {
        "id": row.id,
        "project_code": row.project_code,
        "name": row.name,
        "planned_date": row.planned_date,
        "actual_date": row.actual_date,
        "outcome": _enum_str(row.outcome),
        "exit_criteria": None,
        "notes": None,
    }


def minutes_view(row: Any) -> dict[str, Any]:
    """C4.2 MinutesView."""
    return {
        "id": row.id,
        "project_code": row.project_code,
        "cycle_id": row.cycle_id,
        "held_at": row.held_at,
        "attendees": row.attendees,
        "decisions": row.decisions,
        "agreed_actions": row.agreed_actions,
        "risks": row.risks,
        "minutes_text": row.minutes_text,
    }


def signal_view(row: Any) -> dict[str, Any]:
    """C4.2 SignalView. resolved is emitted as a bool, not the stored int."""
    return {
        "id": row.id,
        "project_code": row.project_code,
        "owner": row.owner,
        "kind": _enum_str(row.kind),
        "action_id": row.action_id,
        "occurred_at": row.occurred_at,
        "note": row.note,
        "resolved": bool(row.resolved),
        "resolved_at": row.resolved_at,
    }


def report_view(row: Any) -> dict[str, Any]:
    """C4.2 ReportView."""
    return {
        "id": row.id,
        "project_code": row.project_code,
        "generated_at": row.generated_at,
        "pdf_rel_path": row.pdf_rel_path,
        "html_rel_path": row.html_rel_path,
        "prepared_for": row.prepared_for,
        "snapshot_sha256": row.snapshot_sha256,
    }


def event_view(row: Any) -> dict[str, Any]:
    """Timeline entry. C4.2 names events inside SnapshotView but does not
    give the shape separately; this is the row, flattened."""
    return {
        "id": row.id,
        "project_code": row.project_code,
        "kind": _enum_str(row.kind),
        "ref_table": row.ref_table,
        "ref_id": row.ref_id,
        "title": row.title,
        "body": row.body,
        "occurred_at": row.occurred_at,
    }


def snapshot_view(snapshot: Any) -> dict[str, Any]:
    """C4.2 SnapshotView — every element a sub-view, events capped at 20."""
    return {
        "project": project_view(snapshot.project),
        "current_cycle": (
            cycle_view(snapshot.current_cycle)
            if snapshot.current_cycle is not None
            else None
        ),
        "actions": [action_view(a) for a in snapshot.actions],
        "gates": [gate_view(g) for g in snapshot.open_gates],
        "events": [event_view(e) for e in snapshot.events[:SNAPSHOT_EVENTS]],
        "minutes": [minutes_view(m) for m in snapshot.minutes],
        "signals": [signal_view(s) for s in snapshot.signals],
    }


def owner_health_view(health: Any) -> dict[str, Any]:
    """C4.1 OwnerHealthView — counts keyed by the kind's string value."""
    return {
        "owner": health.owner,
        "counts": {
            _enum_str(kind): count for kind, count in health.counts.items()
        },
        "total": health.total,
        "open_total": health.open_total,
    }


def hit_view(hit: Any) -> dict[str, Any]:
    """C4.1 HitView."""
    return {
        "table": hit.table,
        "row_id": hit.row_id,
        "snippet": hit.snippet,
    }


def integrity_view(report: Any, cap: int = 50) -> dict[str, Any]:
    """C4.1 IntegrityView — counts plus the first `cap` of each list."""
    return {
        "ok": report.ok,
        "missing": len(report.missing),
        "mismatched": len(report.mismatched),
        "orphans": len(report.orphans),
        "missing_list": [r.rel_path for r in report.missing[:cap]],
        "orphan_list": list(report.orphans[:cap]),
    }
