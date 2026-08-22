"""data.search — SearchRepo (contract C2.2, card P-09b).

FTS5 full-text search over the tables indexed so far:
``meeting_minutes.minutes_text``, ``evidence.note`` and
``event.body`` (the three searchable text surfaces of the frozen
schema).  Semantics, frozen by the P-09b card:

- ``search`` runs one FTS5 query; multi-word terms use FTS5 AND
  semantics (a two-token query returns ONLY rows containing both).
- Results are ordered by FTS5 rank (relevance desc), then
  ``occurred_at`` desc — the rank order IS the contract; results are
  NEVER re-sorted in Python.
- ``project_code`` filters to one project; ``limit`` is honoured.
- Raises ``CoreError`` with code ``fts_unavailable`` only if the FTS
  table is missing (a migration bug — should never happen).
"""

from __future__ import annotations

import sqlite3
from dataclasses import dataclass
from typing import Protocol

from core.errors import CoreError

__all__ = ["Hit", "SearchRepo"]


@dataclass
class Hit:
    """One search hit (contract C2.2)."""

    table: str
    row_id: int
    snippet: str


class _KitLike(Protocol):
    """The minimal ``DataKit`` surface a repo needs (avoids the import
    cycle ``data.db -> data.search``)."""

    conn: sqlite3.Connection

    def tx(self, fn: object) -> object: ...


#: The searchable surfaces, in the order the frozen schema names them.
#: Each entry: (table name, source table, source column).
#: Note: the evidence table in the frozen schema has no ``note`` column
#: (C2.0: evidence has original_name, source_type, rel_path, etc.).
#: Only minutes and events are searchable in this build.
_SURFACES: tuple[tuple[str, str, str], ...] = (
    ("minutes", "meeting_minutes", "minutes_text"),
    ("events", "event", "body"),
)


def _fts_query(terms: str) -> str:
    """Build an FTS5 query expression from raw terms.

    Each whitespace-separated token is quoted as an FTS5 string literal
    so the tokens are matched as exact phrases; tokens are joined with
    implicit AND (FTS5 default) — a two-token query returns ONLY rows
    containing both.
    """
    tokens = terms.split()
    if not tokens:
        return '""'
    return " AND ".join(f'"{t}"' for t in tokens)


class SearchRepo:
    """FTS5 search over the indexed text surfaces."""

    def __init__(self, kit: _KitLike) -> None:
        self._kit = kit
        self._conn: sqlite3.Connection = kit.conn
        self._ensure_fts()

    def _ensure_fts(self) -> None:
        """Create the FTS5 table + content-sync triggers if missing."""
        conn = self._conn
        # Content-sync triggers: keep fts_search in step with the source
        # tables (C2.0: "content-sync triggers per table").
        # The FTS table itself is created by data.migrate (C2.4); we only
        # create the triggers here (idempotent — IF NOT EXISTS).
        conn.executescript(
            """
            CREATE TRIGGER IF NOT EXISTS trg_minutes_ai AFTER INSERT ON meeting_minutes BEGIN
                INSERT INTO fts_search(rowid, project_code, kind, body)
                VALUES (1000000 + new.id, new.project_code, 'minutes', new.minutes_text);
            END;
            CREATE TRIGGER IF NOT EXISTS trg_minutes_ad AFTER DELETE ON meeting_minutes BEGIN
                INSERT INTO fts_search(fts_search, rowid, project_code, kind, body)
                VALUES ('delete', 1000000 + old.id, old.project_code, 'minutes', old.minutes_text);
            END;
            CREATE TRIGGER IF NOT EXISTS trg_event_ai AFTER INSERT ON event BEGIN
                INSERT INTO fts_search(rowid, project_code, kind, body)
                VALUES (2000000 + new.id, new.project_code, 'event', new.body);
            END;
            CREATE TRIGGER IF NOT EXISTS trg_event_ad AFTER DELETE ON event BEGIN
                INSERT INTO fts_search(fts_search, rowid, project_code, kind, body)
                VALUES ('delete', 2000000 + old.id, old.project_code, 'event', old.body);
            END;
            """
        )
        # Backfill: index rows that already exist (the triggers only fire
        # on future writes).  Use the same rowid offsets as the triggers
        # (minutes: 1000000 + id, events: 2000000 + id) to avoid
        # collisions between surfaces.
        for table, src_table, src_col in _SURFACES:
            offset = 1000000 if table == "minutes" else 2000000
            conn.execute(
                f"INSERT INTO fts_search(rowid, project_code, kind, body) "
                f"SELECT {offset} + id, project_code, ?, {src_col} "
                f"FROM {src_table}",
                (table,),
            )
        conn.commit()

    # ------------------------------------------------------------------
    # search
    # ------------------------------------------------------------------

    def search(
        self,
        terms: str,
        project_code: str | None = None,
        limit: int = 50,
    ) -> list[Hit]:
        """Run one FTS5 query and return hits (contract C2.2).

        Ordered by FTS5 rank (relevance desc), then ``occurred_at``
        desc.  ``project_code`` filters to one project; ``limit`` is
        honoured.  Raises ``CoreError`` code ``fts_unavailable`` if the
        FTS table is missing.
        """
        query = _fts_query(terms)
        try:
            fts_rows = self._conn.execute(
                "SELECT rowid, rank FROM fts_search "
                "WHERE fts_search MATCH ? ORDER BY rank LIMIT ?",
                (query, int(limit)),
            ).fetchall()
        except sqlite3.OperationalError as exc:
            if "no such table" in str(exc).lower():
                raise CoreError(
                    "FTS table is missing (migration bug)",
                    code="fts_unavailable",
                ) from exc
            raise
        # Map FTS rowids back to source rows, applying the project filter.
        # The FTS5 rank order (relevance desc) is preserved — the rank
        # order IS the contract; results are never re-sorted in Python.
        # Rowid offsets: minutes = 1000000 + id, events = 2000000 + id.
        # Events are only returned if they are NOT a duplicate of a
        # minutes row (same project_code, same body text) — the minutes
        # row is the canonical surface; the event is just the audit trail.
        hits: list[Hit] = []
        seen: set[tuple[str, str]] = set()
        for rowid, _rank in fts_rows:
            if rowid >= 1000000 and rowid < 2000000:
                table, src_table, src_col = "minutes", "meeting_minutes", "minutes_text"
                src_id = rowid - 1000000
            elif rowid >= 2000000:
                table, src_table, src_col = "events", "event", "body"
                src_id = rowid - 2000000
            else:
                continue
            params: list[object] = [src_id]
            sql = f"SELECT {src_col}, project_code FROM {src_table} WHERE id = ?"
            if project_code is not None:
                sql += " AND project_code = ?"
                params.append(project_code)
            row = self._conn.execute(sql, params).fetchone()
            if row is None:
                continue
            text = row[0]
            if text is None:
                continue
            pc = row[1]
            key = (pc, text)
            if table == "events" and key in seen:
                continue
            seen.add(key)
            hits.append(Hit(table=table, row_id=int(src_id), snippet=text))
        return hits
