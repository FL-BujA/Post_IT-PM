"""data.integrity — IntegrityService, invariant I2 (contract C2.2, card P-09c).

``verify`` is a PURE READ over the two surfaces I2 compares — the
``evidence`` glue rows in the db and the files on disk under
``workspace_root``:

- ``missing``    — a db row whose file is gone (row, no file).
- ``mismatched`` — a file whose bytes no longer hash to the recorded
  ``sha256`` (row, observed digest).
- ``orphans``    — a file on disk with no db row (its ``rel_path``).

I2 reports; it NEVER deletes, repairs or quarantines — a ``verify``
call leaves both the db row count and the on-disk file count exactly
as they were.
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from typing import Protocol

from core.hash import sha256_file
from data.rows import EvidenceRow

__all__ = ["IntegrityReport", "IntegrityService"]


class _KitLike(Protocol):
    """The minimal ``DataKit`` surface the service needs (avoids the
    import cycle ``data.db -> data.integrity``)."""

    conn: object

    def tx(self, fn: object) -> object: ...


@dataclass
class IntegrityReport:
    """The I2 verdict (C2.2): three lists, plus ``ok`` when all empty."""

    ok: bool
    missing: list[EvidenceRow]
    mismatched: list[tuple[EvidenceRow, str]]
    orphans: list[str]


class IntegrityService:
    """I2 — db rows vs. on-disk files.  Reports, never mutates."""

    def __init__(self, kit: _KitLike) -> None:
        self._kit = kit
        self._conn = kit.conn

    def verify(self, workspace_root: str | os.PathLike[str]) -> IntegrityReport:
        """Compare the ``evidence`` rows against the files under
        ``workspace_root`` and return the report (C2.2).

        Pure read: no ``INSERT``/``UPDATE``/``DELETE`` anywhere, and
        nothing on disk is touched either.
        """
        root = os.fspath(workspace_root)

        rows = self._conn.execute(
            "SELECT id, project_code, ref_table, ref_id, original_name, "
            "source_type, rel_path, size_bytes, sha256, attached_at "
            "FROM evidence ORDER BY id ASC"
        ).fetchall()
        evidence_rows = [EvidenceRow(*row) for row in rows]

        missing: list[EvidenceRow] = []
        mismatched: list[tuple[EvidenceRow, str]] = []
        for row in evidence_rows:
            path = os.path.join(root, *row.rel_path.split("/"))
            if not os.path.isfile(path):
                missing.append(row)
                continue
            observed = sha256_file(path)
            if observed != row.sha256:
                mismatched.append((row, observed))

        orphans: list[str] = []
        if os.path.isdir(root):
            for dirpath, _dirnames, filenames in os.walk(root):
                for name in filenames:
                    full = os.path.join(dirpath, name)
                    rel = os.path.relpath(full, root).replace(os.sep, "/")
                    if not any(r.rel_path == rel for r in evidence_rows):
                        orphans.append(rel)
        orphans.sort()

        return IntegrityReport(
            ok=not (missing or mismatched or orphans),
            missing=missing,
            mismatched=mismatched,
            orphans=orphans,
        )
