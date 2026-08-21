"""data.events — EventRepo (contract C2.2).

Append-only event log over the shared ``DataKit`` connection (frozen
rule C2.1: ONE connection per workspace).  Semantics, frozen by the
P-06 card:

- ``emit`` inserts one ``event`` row.  A kind may carry a
  ``ref_table``/``ref_id`` pair (e.g. ``ref_table='actions'``,
  ``ref_id=3``); kinds ``note`` and ``charter`` are also allowed with
  ``ref_table=None`` (invariant I1 shape — both forms are legal).
- ``list_for`` returns events of a project ordered ``occurred_at ASC,
  id ASC``; an optional ``kind`` filter and ``limit`` are honored.
"""

from __future__ import annotations

import sqlite3
from typing import Protocol

from core.enums import EventKind
from core.time import now_utc
from data.rows import EventRow

__all__ = ["EventRepo"]


class _KitLike(Protocol):
    """The minimal ``DataKit`` surface a repo needs (avoids the import
    cycle ``data.db -> data.events``)."""

    conn: sqlite3.Connection

    def tx(self, fn: object) -> object: ...


def _ts() -> str:
    return now_utc().isoformat()


class EventRepo:
    """Append-only event log on the shared ``DataKit`` connection."""

    def __init__(self, kit: _KitLike) -> None:
        self._kit = kit
        self._conn: sqlite3.Connection = kit.conn

    # ------------------------------------------------------------------
    # emit
    # ------------------------------------------------------------------

    def emit(
        self,
        project_code: str,
        kind: EventKind | str,
        title: str,
        *,
        ref_table: str | None = None,
        ref_id: int | None = None,
        body: str | None = None,
        occurred_at: str | None = None,
    ) -> EventRow:
        """Append one event row and return it.

        ``ref_table``/``ref_id`` are stored as given: either a paired
        reference (``ref_table='actions'``, ``ref_id=3``) or both
        ``None`` (the ``note``/``charter`` I1 form).
        """
        if not isinstance(kind, EventKind):
            kind = EventKind(kind)
        ts = _ts()
        occurred = occurred_at if occurred_at is not None else ts
        row = EventRow(
            id=0,  # auto-assigned; filled in below
            project_code=project_code,
            kind=kind.value,
            ref_table=ref_table,
            ref_id=ref_id,
            title=title,
            body=body,
            occurred_at=occurred,
            created_at=ts,
        )
        d = row.to_dict()
        new_id = self._kit.tx(
            lambda conn: (
                conn.execute(
                    "INSERT INTO event "
                    "(project_code, kind, ref_table, ref_id, title, body, "
                    "occurred_at, created_at) "
                    "VALUES (:project_code, :kind, :ref_table, :ref_id, :title, "
                    ":body, :occurred_at, :created_at)",
                    d,
                ).lastrowid
            )
        )
        row.id = int(new_id)
        return row

    # ------------------------------------------------------------------
    # list_for
    # ------------------------------------------------------------------

    def list_for(
        self,
        project_code: str,
        *,
        kind: EventKind | str | None = None,
        limit: int | None = None,
    ) -> list[EventRow]:
        """Events of a project ordered ``occurred_at ASC, id ASC``.

        An optional ``kind`` filter and ``limit`` are honored (P-06).
        """
        sql = (
            "SELECT id, project_code, kind, ref_table, ref_id, title, body, "
            "occurred_at, created_at FROM event WHERE project_code = ?"
        )
        params: list[object] = [project_code]
        if kind is not None:
            if not isinstance(kind, EventKind):
                kind = EventKind(kind)
            sql += " AND kind = ?"
            params.append(kind.value)
        sql += " ORDER BY occurred_at ASC, id ASC"
        if limit is not None:
            sql += " LIMIT ?"
            params.append(int(limit))
        rows = self._conn.execute(sql, params).fetchall()
        return [EventRow(*row) for row in rows]
