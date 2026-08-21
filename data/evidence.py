"""data.evidence — EvidenceRepo (contract C2.2, card P-08).

The glue row for evidence files over the shared ``DataKit`` connection
(frozen rule C2.1: ONE connection per workspace).  The FILE itself is
the services layer's job; this repo only persists the glue:

- ``record`` inserts one ``evidence`` row, storing ``rel_path``
  VERBATIM (no normalization — the services layer validated it with
  ``core.paths.normalize_relpath``; data stores exactly the input
  string).  A duplicate ``rel_path`` raises ``EvidenceConflict`` and
  the FIRST row survives untouched.
- ``list_for`` returns a project's rows in ascending id order.
- ``get_by_path`` round-trips a row by its exact ``rel_path``; an
  unknown path raises ``CoreError`` with code ``evidence_unknown``.
"""

from __future__ import annotations

import sqlite3
from typing import Protocol

from core.errors import CoreError, EvidenceConflict
from data.rows import EvidenceRow

__all__ = ["EvidenceRepo"]


class _KitLike(Protocol):
    """The minimal ``DataKit`` surface a repo needs (avoids the import
    cycle ``data.db -> data.evidence``)."""

    conn: sqlite3.Connection

    def tx(self, fn: object) -> object: ...


class EvidenceRepo:
    """CRUD over the ``evidence`` table (glue rows only)."""

    def __init__(self, kit: _KitLike) -> None:
        self._kit = kit
        self._conn: sqlite3.Connection = kit.conn

    # ------------------------------------------------------------------
    # record / list / get
    # ------------------------------------------------------------------

    def record(self, row: EvidenceRow) -> EvidenceRow:
        """Persist one glue row and return it (P-08).

        ``rel_path`` is stored exactly as given — no normalization side
        effects.  A duplicate ``rel_path`` raises ``EvidenceConflict``
        (code ``evidence_conflict``) and the first row survives
        untouched.
        """
        d = row.to_dict()
        try:
            self._kit.tx(
                lambda conn: conn.execute(
                    "INSERT INTO evidence "
                    "(id, project_code, ref_table, ref_id, original_name, "
                    "source_type, rel_path, size_bytes, sha256, attached_at) "
                    "VALUES (:id, :project_code, :ref_table, :ref_id, "
                    ":original_name, :source_type, :rel_path, :size_bytes, "
                    ":sha256, :attached_at)",
                    d,
                )
            )
        except sqlite3.IntegrityError as exc:
            raise EvidenceConflict(
                f"evidence rel_path {row.rel_path!r} already exists"
            ) from exc
        return self.get_by_path(row.rel_path)

    def list_for(self, project_code: str) -> list[EvidenceRow]:
        """A project's glue rows in ascending id order (P-08).

        ``id`` is a random ``short_id()`` string (C1.5), so "ascending
        id" is a stable total order, not insertion order.
        """
        rows = self._conn.execute(
            "SELECT id, project_code, ref_table, ref_id, original_name, "
            "source_type, rel_path, size_bytes, sha256, attached_at "
            "FROM evidence WHERE project_code = ? ORDER BY id ASC",
            (project_code,),
        ).fetchall()
        return [EvidenceRow(*row) for row in rows]

    def get_by_path(self, rel_path: str) -> EvidenceRow:
        """Fetch a glue row by its EXACT ``rel_path`` (P-08).

        Unknown path raises ``CoreError`` with code
        ``evidence_unknown``.
        """
        row = self._conn.execute(
            "SELECT id, project_code, ref_table, ref_id, original_name, "
            "source_type, rel_path, size_bytes, sha256, attached_at "
            "FROM evidence WHERE rel_path = ?",
            (rel_path,),
        ).fetchone()
        if row is None:
            raise CoreError(
                f"no evidence row for rel_path {rel_path!r}",
                code="evidence_unknown",
            )
        return EvidenceRow(*row)
