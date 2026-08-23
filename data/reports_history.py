"""data.reports_history — ReportHistoryRepo (contract C2.2, card P-09b).

Report provenance rows over the shared ``DataKit`` connection.
Semantics, frozen by the P-09b card:

- ``add`` inserts one ``report_history`` row and emits a ``REPORT``
  event (``ref_table='reports'``, ``ref_id`` = the report row id).
- ``list_for`` returns a project's report rows ordered
  ``generated_at DESC, id DESC``.
"""

from __future__ import annotations

import sqlite3
from typing import Protocol

from core.enums import EventKind
from core.time import now_utc

__all__ = ["ReportHistoryRepo"]


class _KitLike(Protocol):
    """The minimal ``DataKit`` surface a repo needs (avoids the import
    cycle ``data.db -> data.reports_history``)."""

    conn: sqlite3.Connection

    def tx(self, fn: object) -> object: ...


def _ts() -> str:
    return now_utc().isoformat()


class ReportHistoryRepo:
    """Report provenance repository on the shared ``DataKit`` connection."""

    def __init__(self, kit: _KitLike) -> None:
        self._kit = kit
        self._conn: sqlite3.Connection = kit.conn

    # ------------------------------------------------------------------
    # add
    # ------------------------------------------------------------------

    def add(
        self,
        project_code: str,
        pdf_rel_path: str,
        html_rel_path: str,
        prepared_for: str | None,
        snapshot_sha256: str,
        generated_at: str | None = None,
    ) -> int:
        """Insert one report row and emit a ``REPORT`` event.

        Returns the new report row id.
        """
        ts = _ts()
        generated = generated_at if generated_at is not None else ts
        new_id = self._kit.tx(
            lambda conn: conn.execute(
                "INSERT INTO report_history "
                "(project_code, generated_at, pdf_rel_path, html_rel_path, "
                "prepared_for, snapshot_sha256) "
                "VALUES (?, ?, ?, ?, ?, ?)",
                (
                    project_code,
                    generated,
                    pdf_rel_path,
                    html_rel_path,
                    prepared_for,
                    snapshot_sha256,
                ),
            ).lastrowid
        )
        # Emit the REPORT event (ref_table='reports', ref_id=new_id).
        self._kit.tx(
            lambda conn: conn.execute(
                "INSERT INTO event "
                "(project_code, kind, ref_table, ref_id, title, body, "
                "occurred_at, created_at) "
                "VALUES (?, ?, 'reports', ?, 'Report generated', ?, ?, ?)",
                (
                    project_code,
                    EventKind.REPORT.value,
                    int(new_id),
                    f"reports/{new_id}",
                    generated,
                    ts,
                ),
            )
        )
        return int(new_id)

    # ------------------------------------------------------------------
    # list_for
    # ------------------------------------------------------------------

    def list_for(self, project_code: str) -> list[tuple]:
        """A project's report rows ordered ``generated_at DESC, id DESC``."""
        return self._conn.execute(
            "SELECT id, project_code, generated_at, pdf_rel_path, "
            "html_rel_path, prepared_for, snapshot_sha256 "
            "FROM report_history WHERE project_code = ? "
            "ORDER BY generated_at DESC, id DESC",
            (project_code,),
        ).fetchall()
