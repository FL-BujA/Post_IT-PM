"""data.gates — GateRepo (contract C2.2, card P-07).

Gate lifecycle over the shared ``DataKit`` connection (frozen rule
C2.1: ONE connection per workspace):

- ``create`` inserts a ``gate`` row with outcome ``planned``; a
  ``planned_date`` may be given or omitted (NULL allowed).  The gate
  row carries the id of its own ``GATE`` event (``ref_table='gates'``,
  ``ref_id`` = gate id) so the timeline tells the story from birth.
- ``record_outcome`` flips the gate to a real outcome and stamps
  ``actual_date``.  Idempotence is NOT silent (frozen, P-07): a second
  outcome on an already-outcomed gate raises ``ServiceError`` with code
  ``gate_already_outcomed`` — a data-integrity event the PM must see.
- Every transition emits a ``GATE`` event, asserted by reading
  ``event`` (timeline_events in the tests).
"""

from __future__ import annotations

import sqlite3
from typing import Protocol

from core.enums import EventKind, GateOutcome
from core.errors import ServiceError, UnknownProjectData
from core.time import now_utc
from data.rows import EventRow, GateRow

__all__ = ["GATE_ALREADY_OUTCOME_CODE", "GateRepo"]

#: Frozen error code (P-07): a second outcome is a data-integrity event.
GATE_ALREADY_OUTCOME_CODE = "gate_already_outcomed"

#: Outcomes that are "real" (anything but the created state).
_REAL_OUTCOMES = frozenset(
    {
        GateOutcome.PASSED,
        GateOutcome.CONDITIONALLY_PASSED,
        GateOutcome.FAILED,
        GateOutcome.SKIPPED,
    }
)


class _KitLike(Protocol):
    """The minimal ``DataKit`` surface a repo needs (avoids the import
    cycle ``data.db -> data.gates``)."""

    conn: sqlite3.Connection

    events: object  # EventRepo on the same DataKit

    def tx(self, fn: object) -> object: ...


def _ts() -> str:
    return now_utc().isoformat()


class GateRepo:
    """CRUD + outcome lifecycle over the ``gate`` table."""

    def __init__(self, kit: _KitLike) -> None:
        self._kit = kit
        self._conn: sqlite3.Connection = kit.conn

    # ------------------------------------------------------------------
    # create / get
    # ------------------------------------------------------------------

    def create(
        self,
        project_code: str,
        name: str,
        *,
        planned_date: str | None = None,
    ) -> GateRow:
        """Insert a new gate in the ``planned`` state and return it.

        ``planned_date`` is optional (NULL allowed, P-07).  An unknown
        project code raises ``UnknownProjectData``.
        """
        self._require_project(project_code)
        ts = _ts()
        event: EventRow = self._kit.events.emit(  # type: ignore[attr-defined]
            project_code,
            EventKind.GATE,
            f"Gate created: {name}",
            ref_table="gates",
            ref_id=0,
            body=f"planned_date={planned_date}",
        )
        row = GateRow(
            id=0,  # auto-assigned; filled in below
            project_code=project_code,
            event_id=event.id,
            name=name,
            outcome=GateOutcome.PLANNED.value,
            planned_date=planned_date,
            actual_date=None,
            created_at=ts,
        )
        d = row.to_dict()
        new_id = self._kit.tx(
            lambda conn: (
                conn.execute(
                    "INSERT INTO gate "
                    "(project_code, event_id, name, outcome, planned_date, "
                    "actual_date, created_at) "
                    "VALUES (:project_code, :event_id, :name, :outcome, "
                    ":planned_date, :actual_date, :created_at)",
                    d,
                ).lastrowid
            )
        )
        row.id = int(new_id)
        # Backfill the gate id into the timeline event.
        self._conn.execute(
            "UPDATE event SET ref_id = ? WHERE id = ?", (row.id, event.id)
        )
        self._conn.commit()
        return row

    def get(self, gate_id: int) -> GateRow:
        """Fetch a gate by id; unknown id raises ``ServiceError``
        (code ``gate_unknown``)."""
        row = self._conn.execute(
            "SELECT id, project_code, event_id, name, outcome, planned_date, "
            "actual_date, created_at FROM gate WHERE id = ?",
            (gate_id,),
        ).fetchone()
        if row is None:
            raise ServiceError(
                f"no gate with id {gate_id!r}", code="gate_unknown"
            )
        return GateRow(*row)

    # ------------------------------------------------------------------
    # outcome
    # ------------------------------------------------------------------

    def record_outcome(self, gate_id: int, outcome: GateOutcome | str) -> GateRow:
        """Record the gate's outcome and stamp ``actual_date`` (P-07).

        Emits a ``GATE`` event with ``ref_table='gates'``,
        ``ref_id`` = the gate's id (the tests assert this by reading
        the event table).  Idempotence is NOT silent: a second outcome
        raises ``ServiceError`` with code ``gate_already_outcomed``.
        """
        if isinstance(outcome, GateOutcome):
            value = outcome.value
        else:
            try:
                value = GateOutcome(outcome).value
            except ValueError as exc:
                raise ServiceError(
                    f"invalid gate outcome {outcome!r}", code="invalid_outcome"
                ) from exc
        if value == GateOutcome.PLANNED.value:
            raise ServiceError(
                "record_outcome requires a real outcome, not 'planned'",
                code="invalid_outcome",
            )
        gate = self.get(gate_id)
        if gate.outcome in _REAL_OUTCOMES:
            raise ServiceError(
                f"gate {gate_id!r} already outcomed as {gate.outcome!r}",
                code=GATE_ALREADY_OUTCOME_CODE,
            )
        ts = _ts()
        self._kit.tx(
            lambda conn: conn.execute(
                "UPDATE gate SET outcome = ?, actual_date = ? WHERE id = ?",
                (value, ts, gate_id),
            )
        )
        event: EventRow = self._kit.events.emit(  # type: ignore[attr-defined]
            gate.project_code,
            EventKind.GATE,
            f"Gate outcome: {gate.name} -> {value}",
            ref_table="gates",
            ref_id=gate.id,
            body=f"actual_date={ts}",
        )
        self._conn.commit()
        return self.get(gate_id)

    # ------------------------------------------------------------------
    # helpers
    # ------------------------------------------------------------------

    def _require_project(self, project_code: str) -> None:
        if self._conn.execute(
            "SELECT 1 FROM project WHERE code = ?", (project_code,)
        ).fetchone() is None:
            raise UnknownProjectData(f"no project with code {project_code!r}")
