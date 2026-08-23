"""data.minutes — MinutesRepo (contract C2.2, card P-09a).

Meeting minutes storage over the shared ``DataKit`` connection.
Minutes are stored verbatim (no markdown processing, no normalisation).

Semantics, frozen by the P-09a card:

- ``add`` inserts one ``meeting_minutes`` row and emits a ``MEETING``
  event (``ref_table='minutes'``, ``ref_id`` = the minutes row id).
- ``list_for`` returns all minutes for a project ordered by
  ``held_at ASC, id ASC``.
"""

from __future__ import annotations

import sqlite3
from typing import Protocol

from core.enums import EventKind
from core.time import now_utc

__all__ = ["MinutesRepo"]


class _KitLike(Protocol):
    """The minimal ``DataKit`` surface a repo needs."""

    conn: sqlite3.Connection

    def tx(self, fn: object) -> object: ...


def _ts() -> str:
    return now_utc().isoformat()


class MinutesRepo:
    """Meeting minutes repository on the shared ``DataKit`` connection."""

    def __init__(self, kit: _KitLike) -> None:
        self._kit = kit
        self._conn: sqlite3.Connection = kit.conn

    # ------------------------------------------------------------------
    # add
    # ------------------------------------------------------------------

    def add(
        self,
        project_code: str,
        held_at: str,
        attendees: str | None,
        decisions: str | None,
        agreed_actions: str | None,
        risks: str | None,
        minutes_text: str,
        cycle_id: int | None = None,
    ) -> int:
        """Insert one minutes row and emit a ``MEETING`` event.

        Returns the new minutes row id.
        """
        ts = _ts()
        new_id = self._kit.tx(
            lambda conn: conn.execute(
                "INSERT INTO meeting_minutes "
                "(project_code, cycle_id, held_at, attendees, decisions, "
                "agreed_actions, risks, minutes_text) "
                "VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
                (
                    project_code,
                    cycle_id,
                    held_at,
                    attendees,
                    decisions,
                    agreed_actions,
                    risks,
                    minutes_text,
                ),
            ).lastrowid
        )
        # Emit the MEETING event (ref_table='minutes', ref_id=new_id).
        self._kit.tx(
            lambda conn: conn.execute(
                "INSERT INTO event "
                "(project_code, kind, ref_table, ref_id, title, body, "
                "occurred_at, created_at) "
                "VALUES (?, ?, 'minutes', ?, 'Meeting minutes', ?, ?, ?)",
                (
                    project_code,
                    EventKind.MEETING.value,
                    int(new_id),
                    minutes_text,
                    ts,
                    ts,
                ),
            )
        )
        return int(new_id)

    # ------------------------------------------------------------------
    # list_for
    # ------------------------------------------------------------------

    def list_for(self, project_code: str) -> list[tuple]:
        """All minutes for a project, ordered ``held_at ASC, id ASC``."""
        return self._conn.execute(
            "SELECT id, project_code, cycle_id, held_at, attendees, "
            "decisions, agreed_actions, risks, minutes_text "
            "FROM meeting_minutes WHERE project_code = ? "
            "ORDER BY held_at ASC, id ASC",
            (project_code,),
        ).fetchall()