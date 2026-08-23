"""data.signals — SignalRepo (contract C2.2, card P-09a).

Engagement signals over the shared ``DataKit`` connection.
Signals are append-only: only ``set_resolved`` mutates a row.

Semantics, frozen by the P-09a card:

- ``insert`` adds one ``engagement_signals`` row and emits a ``SIGNAL``
  event whose summary starts with ``'Signal #'`` (the frozen format).
- ``list_for`` filters by ``kind``, ``owner``, and/or ``resolved``.
- ``set_resolved`` toggles the ``resolved`` flag and stamps
  ``resolved_at``.
"""

from __future__ import annotations

import sqlite3
from typing import Protocol

from core.enums import EventKind, SignalKind
from core.time import now_utc
from data.rows import SignalRow

__all__ = ["SignalRepo"]


class _KitLike(Protocol):
    """The minimal ``DataKit`` surface a repo needs."""

    conn: sqlite3.Connection

    def tx(self, fn: object) -> object: ...


def _ts() -> str:
    return now_utc().isoformat()


class SignalRepo:
    """Engagement signals repository on the shared ``DataKit`` connection."""

    def __init__(self, kit: _KitLike) -> None:
        self._kit = kit
        self._conn: sqlite3.Connection = kit.conn

    # ------------------------------------------------------------------
    # insert
    # ------------------------------------------------------------------

    def insert(
        self,
        kind: SignalKind | str,
        project_code: str,
        owner: str,
        action_id: int | None = None,
        note: str = "",
    ) -> int:
        """Insert one signal row and emit a ``SIGNAL`` event.

        Returns the new signal row id.
        """
        if not isinstance(kind, SignalKind):
            kind = SignalKind(kind)
        ts = _ts()
        new_id = self._kit.tx(
            lambda conn: conn.execute(
                "INSERT INTO engagement_signals "
                "(project_code, owner, kind, action_id, occurred_at, note, "
                "resolved, resolved_at) "
                "VALUES (?, ?, ?, ?, ?, ?, 0, NULL)",
                (
                    project_code,
                    owner,
                    kind.value,
                    action_id,
                    ts,
                    note,
                ),
            ).lastrowid
        )
        # Emit the SIGNAL event (ref_table=NULL per C2.2 note).
        summary = f"Signal #{int(new_id)}: {kind.value} (owner {owner})"
        self._kit.tx(
            lambda conn: conn.execute(
                "INSERT INTO event "
                "(project_code, kind, ref_table, ref_id, title, body, "
                "occurred_at, created_at) "
                "VALUES (?, ?, NULL, NULL, ?, ?, ?, ?)",
                (
                    project_code,
                    EventKind.SIGNAL.value,
                    summary,
                    summary,
                    ts,
                    ts,
                ),
            )
        )
        return int(new_id)

    # ------------------------------------------------------------------
    # list_for
    # ------------------------------------------------------------------

    def list_for(
        self,
        project_code: str,
        kind: SignalKind | str | None = None,
        owner: str | None = None,
        resolved: bool | None = None,
    ) -> list[SignalRow]:
        """Signals for a project, optionally filtered.

        Filters: ``kind``, ``owner``, ``resolved`` (each optional).
        Ordered by ``occurred_at ASC, id ASC``.
        """
        sql = (
            "SELECT id, project_code, owner, kind, action_id, occurred_at, "
            "note, resolved, resolved_at "
            "FROM engagement_signals WHERE project_code = ?"
        )
        params: list[object] = [project_code]
        if kind is not None:
            if not isinstance(kind, SignalKind):
                kind = SignalKind(kind)
            sql += " AND kind = ?"
            params.append(kind.value)
        if owner is not None:
            sql += " AND owner = ?"
            params.append(owner)
        if resolved is not None:
            sql += " AND resolved = ?"
            params.append(1 if resolved else 0)
        sql += " ORDER BY occurred_at ASC, id ASC"
        return [
            SignalRow(
                id=r[0],
                project_code=r[1],
                owner=r[2],
                kind=r[3],
                action_id=r[4],
                occurred_at=r[5],
                note=r[6],
                resolved=r[7],
                resolved_at=r[8],
            )
            for r in self._conn.execute(sql, params).fetchall()
        ]

    # ------------------------------------------------------------------
    # set_resolved
    # ------------------------------------------------------------------

    def set_resolved(self, signal_id: int, resolved: bool) -> None:
        """Toggle the ``resolved`` flag and stamp ``resolved_at``."""
        ts = _ts()
        self._kit.tx(
            lambda conn: conn.execute(
                "UPDATE engagement_signals SET resolved = ?, resolved_at = ? "
                "WHERE id = ?",
                (1 if resolved else 0, ts, signal_id),
            )
        )