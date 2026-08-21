"""data.projects — ProjectRepo (contract C2.2).

Thin repository over the shared ``DataKit`` connection (frozen rule
C2.1: ONE connection per workspace — a repo NEVER opens its own
handle).  Semantics, frozen by the P-06 card:

- ``create`` inserts a ``project`` row; the ``code`` column is UNIQUE,
  so a second create with the same code raises ``DataError`` with code
  ``unique_violation``.
- ``get`` by code (or id) for an unknown project raises
  ``UnknownProjectData`` — ``isinstance`` of ``DataError`` with code
  ``unknown_project``.
- ``list`` returns codes in ascending order.
- ``set_status`` validates against the ``ProjectStatus`` enum: a bad
  value raises ``ServiceError`` with code ``invalid_status``.
"""

from __future__ import annotations

import sqlite3
from typing import Protocol

from core.enums import ProjectStatus
from core.errors import DataError, ServiceError, UnknownProjectData
from core.time import now_utc
from data.rows import ProjectRow

__all__ = ["ProjectRepo"]


class _KitLike(Protocol):
    """The minimal ``DataKit`` surface a repo needs (avoids the import
    cycle ``data.db -> data.projects``)."""

    conn: sqlite3.Connection

    def tx(self, fn: object) -> object: ...


def _ts() -> str:
    return now_utc().isoformat()


class ProjectRepo:
    """CRUD over the ``project`` table on the shared ``DataKit`` connection."""

    def __init__(self, kit: _KitLike) -> None:
        self._kit = kit
        self._conn: sqlite3.Connection = kit.conn

    # ------------------------------------------------------------------
    # create / get / list
    # ------------------------------------------------------------------

    def create(
        self,
        code: str,
        name: str,
        status: ProjectStatus | str = ProjectStatus.CHARTER,
        *,
        charter: str | None = None,
        target: str | None = None,
        target_date: str | None = None,
        status_rag: str | None = None,
        red_flags: str | None = None,
        escalation: str | None = None,
        sponsor: str | None = None,
    ) -> ProjectRow:
        """Insert a new project row and return it.

        A duplicate ``code`` raises ``DataError`` with code
        ``unique_violation`` (C2.2).
        """
        if not isinstance(status, ProjectStatus):
            status = ProjectStatus(status)
        ts = _ts()
        row = ProjectRow(
            code=code,
            name=name,
            status=status.value,
            charter=charter,
            target=target,
            target_date=target_date,
            status_rag=status_rag,
            red_flags=red_flags,
            escalation=escalation,
            sponsor=sponsor,
            created_at=ts,
            updated_at=ts,
        )
        d = row.to_dict()
        try:
            self._kit.tx(
                lambda conn: conn.execute(
                    "INSERT INTO project "
                    "(code, name, status, charter, target, target_date, "
                    "status_rag, red_flags, escalation, sponsor, "
                    "created_at, updated_at) "
                    "VALUES (:code, :name, :status, :charter, :target, "
                    ":target_date, :status_rag, :red_flags, :escalation, "
                    ":sponsor, :created_at, :updated_at)",
                    d,
                )
            )
        except sqlite3.IntegrityError as exc:
            raise DataError(
                f"project code {code!r} already exists", code="unique_violation"
            ) from exc
        return row

    def get(self, code: str) -> ProjectRow:
        """Fetch a project by its unique code.

        Unknown code raises ``UnknownProjectData`` (isinstance
        ``DataError``, code ``unknown_project``).
        """
        row = self._conn.execute(
            "SELECT code, name, status, charter, target, target_date, "
            "status_rag, red_flags, escalation, sponsor, created_at, "
            "updated_at FROM project WHERE code = ?",
            (code,),
        ).fetchone()
        if row is None:
            raise UnknownProjectData(f"no project with code {code!r}")
        return ProjectRow(*row)

    def list(self) -> list[ProjectRow]:
        """All projects in ascending ``code`` order."""
        rows = self._conn.execute(
            "SELECT code, name, status, charter, target, target_date, "
            "status_rag, red_flags, escalation, sponsor, created_at, "
            "updated_at FROM project ORDER BY code ASC"
        ).fetchall()
        return [ProjectRow(*row) for row in rows]

    # ------------------------------------------------------------------
    # status
    # ------------------------------------------------------------------

    def set_status(self, code: str, status: ProjectStatus | str) -> ProjectRow:
        """Change a project's status, validating against the enum.

        A value outside ``ProjectStatus`` raises ``ServiceError`` with
        code ``invalid_status`` (P-06).  An unknown project code raises
        ``UnknownProjectData``.
        """
        if isinstance(status, ProjectStatus):
            value = status.value
        else:
            try:
                value = ProjectStatus(status).value
            except ValueError as exc:
                raise ServiceError(
                    f"invalid status {status!r}", code="invalid_status"
                ) from exc
        ts = _ts()
        updated = self._conn.execute(
            "UPDATE project SET status = ?, updated_at = ? WHERE code = ?",
            (value, ts, code),
        )
        if updated.rowcount == 0:
            raise UnknownProjectData(f"no project with code {code!r}")
        return self.get(code)
