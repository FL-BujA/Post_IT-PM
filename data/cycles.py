"""data.cycles — CycleRepo (contract C2.2, card P-07).

The loop's structural lock — invariant I3 lives here: a cycle cannot be
recorded closed without a gate outcome.  Semantics, frozen by the P-07
card:

- ``open`` inserts a ``cycle`` row and emits a ``PHASE`` event
  ``"Cycle opened: <name>"`` (exact title, asserted by reading the
  event table).
- ``close_cycle(cycle_id, gate_id)`` requires a gate from the SAME
  project with a real outcome; otherwise it raises ``GateMissing`` and
  leaves the cycle untouched (I3 — named test
  ``test_i3_close_requires_outcome``).  On success: ``closed_at``
  stamped, ``gate_id`` linked, the gate's ``GATE`` event present in the
  timeline, the cycle row returned.
- ``current_for`` returns the project's open cycle (``closed_at IS
  NULL``, most recent), or ``None`` when there is none open.
"""

from __future__ import annotations

import sqlite3
from typing import Protocol

from core.enums import EventKind, GateOutcome
from core.errors import DataError, GateMissing, UnknownProjectData
from core.time import now_utc
from data.rows import CycleRow

__all__ = ["CycleRepo"]

#: Outcomes that count as a "real" outcome for invariant I3.
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
    cycle ``data.db -> data.cycles``)."""

    conn: sqlite3.Connection

    events: object  # EventRepo on the same DataKit

    def tx(self, fn: object) -> object: ...


def _ts() -> str:
    return now_utc().isoformat()


class CycleRepo:
    """Cycle lifecycle over the ``cycle`` table; I3 enforced here."""

    def __init__(self, kit: _KitLike) -> None:
        self._kit = kit
        self._conn: sqlite3.Connection = kit.conn

    # ------------------------------------------------------------------
    # open / get
    # ------------------------------------------------------------------

    def open(self, project_code: str, name: str) -> CycleRow:
        """Open a new cycle and emit the ``PHASE`` event
        ``"Cycle opened: <name>"`` (P-07, exact title).

        An unknown project code raises ``UnknownProjectData``.
        """
        self._require_project(project_code)
        ts = _ts()
        row = CycleRow(
            id=0,  # auto-assigned; filled in below
            project_code=project_code,
            name=name,
            gate_id=None,
            closed_at=None,
            validated=0,
            validated_at=None,
            created_at=ts,
        )
        d = row.to_dict()
        new_id = self._kit.tx(
            lambda conn: (
                conn.execute(
                    "INSERT INTO cycle "
                    "(project_code, name, gate_id, closed_at, validated, "
                    "validated_at, created_at) "
                    "VALUES (:project_code, :name, :gate_id, :closed_at, "
                    ":validated, :validated_at, :created_at)",
                    d,
                ).lastrowid
            )
        )
        row.id = int(new_id)
        self._kit.events.emit(  # type: ignore[attr-defined]
            project_code,
            EventKind.PHASE,
            f"Cycle opened: {name}",
            ref_table="cycles",
            ref_id=row.id,
        )
        self._conn.commit()
        return row

    def get(self, cycle_id: int) -> CycleRow:
        """Fetch a cycle by id; unknown id raises ``DataError``."""
        row = self._conn.execute(
            "SELECT id, project_code, name, gate_id, closed_at, validated, "
            "validated_at, created_at FROM cycle WHERE id = ?",
            (cycle_id,),
        ).fetchone()
        if row is None:
            raise DataError(f"no cycle with id {cycle_id!r}", code="cycle_unknown")
        return CycleRow(*row)

    # ------------------------------------------------------------------
    # close (I3 lives here)
    # ------------------------------------------------------------------

    def close_cycle(self, cycle_id: int, gate_id: int) -> CycleRow:
        """Close a cycle, gated on a real gate outcome (invariant I3).

        The gate must exist, belong to the SAME project as the cycle,
        and carry a real outcome (anything but ``planned``).  Any other
        shape raises ``GateMissing`` and the cycle is left unchanged
        (``closed_at`` stays NULL, ``gate_id`` stays NULL).  On success
        the gate is linked to the cycle, ``closed_at`` is stamped, and
        the cycle row is returned.
        """
        cycle = self.get(cycle_id)
        gate_row = self._conn.execute(
            "SELECT id, project_code, outcome FROM gate WHERE id = ?",
            (gate_id,),
        ).fetchone()
        gate_ok = (
            gate_row is not None
            and gate_row[1] == cycle.project_code
            and gate_row[2] in {o.value for o in _REAL_OUTCOMES}
        )
        if not gate_ok:
            raise GateMissing(
                f"gate {gate_id!r} cannot close cycle {cycle_id!r} "
                "(missing, foreign project, or still planned) — invariant I3"
            )
        ts = _ts()
        self._kit.tx(
            lambda conn: conn.execute(
                "UPDATE cycle SET gate_id = ?, closed_at = ? WHERE id = ?",
                (gate_id, ts, cycle_id),
            )
        )
        self._conn.commit()
        return self.get(cycle_id)

    # ------------------------------------------------------------------
    # current_for
    # ------------------------------------------------------------------

    def current_for(self, project_code: str) -> CycleRow | None:
        """The project's open cycle (most recent), or ``None`` (P-07).

        "Open" means ``closed_at IS NULL``; with several open cycles the
        most recent (highest id) wins.
        """
        row = self._conn.execute(
            "SELECT id, project_code, name, gate_id, closed_at, validated, "
            "validated_at, created_at "
            "FROM cycle WHERE project_code = ? AND closed_at IS NULL "
            "ORDER BY id DESC LIMIT 1",
            (project_code,),
        ).fetchone()
        if row is None:
            return None
        return CycleRow(*row)

    # ------------------------------------------------------------------
    # helpers
    # ------------------------------------------------------------------

    def _require_project(self, project_code: str) -> None:
        if self._conn.execute(
            "SELECT 1 FROM project WHERE code = ?", (project_code,)
        ).fetchone() is None:
            raise UnknownProjectData(f"no project with code {project_code!r}")
