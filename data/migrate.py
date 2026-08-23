"""data.migrate — schema creation and version guard (contract C2.4).

One frozen schema, version ``'1'``: 10 project tables, the ``meta``
bookkeeping table, ``fts_search`` (FTS5 virtual table) and 5 indexes.
``migrate(path)`` is idempotent — a second call on the same file is a
no-op — and refuses files whose ``meta.schema_version`` it does not
know (future protection, ``CoreError`` code ``unknown_schema``).
"""

from __future__ import annotations

import os
import sqlite3

from core.errors import CoreError

#: The only schema version this build knows (C2.4).
SCHEMA_VERSION = "1"

META_TABLE = "meta"
FTS_TABLE = "fts_search"

#: The 10 project tables, exactly as C2.0 names them.
TABLES: tuple[str, ...] = (
    "project",
    "charter",
    "event",
    "evidence",
    "decision",
    "action",
    "cycle",
    "cycle_item",
    "gate",
    "gate_item",
    "engagement_signals",
    "meeting_minutes",
    "report_history",
)

#: The 5 secondary indexes created beside the tables (C2.4).
INDEXES: tuple[str, ...] = (
    "idx_event_project",
    "idx_action_project",
    "idx_evidence_project",
    "idx_cycle_item_cycle",
    "idx_gate_item_gate",
)

#: C2.4 — the frozen schema, verbatim.  ``fts_search`` is an FTS5
#: virtual table; its columns are the three searchable text surfaces.
SCHEMA_SQL = """
CREATE TABLE project (
    code         TEXT PRIMARY KEY,
    name         TEXT NOT NULL,
    status       TEXT NOT NULL,
    charter      TEXT,
    target       TEXT,
    target_date  TEXT,
    status_rag   TEXT,
    red_flags    TEXT,
    escalation   TEXT,
    sponsor      TEXT,
    created_at   TEXT NOT NULL,
    updated_at   TEXT NOT NULL
);

CREATE TABLE charter (
    id            INTEGER PRIMARY KEY,
    project_code  TEXT NOT NULL REFERENCES project(code),
    revision      INTEGER NOT NULL,
    body          TEXT NOT NULL,
    key_dates     TEXT,
    created_at    TEXT NOT NULL,
    reason        TEXT
);

CREATE TABLE event (
    id            INTEGER PRIMARY KEY,
    project_code  TEXT NOT NULL REFERENCES project(code),
    kind          TEXT NOT NULL,
    ref_table     TEXT,
    ref_id        INTEGER,
    title         TEXT NOT NULL,
    body          TEXT,
    occurred_at   TEXT NOT NULL,
    created_at    TEXT NOT NULL
);

CREATE TABLE evidence (
    id             TEXT PRIMARY KEY,
    project_code   TEXT NOT NULL REFERENCES project(code),
    ref_table      TEXT,
    ref_id         INTEGER,
    original_name  TEXT NOT NULL,
    source_type    TEXT NOT NULL,
    rel_path       TEXT NOT NULL UNIQUE,
    size_bytes     INTEGER NOT NULL,
    sha256         TEXT NOT NULL,
    attached_at    TEXT NOT NULL
);

CREATE TABLE decision (
    id            INTEGER PRIMARY KEY,
    project_code  TEXT NOT NULL REFERENCES project(code),
    event_id      INTEGER NOT NULL REFERENCES event(id),
    revision      INTEGER NOT NULL,
    body          TEXT NOT NULL,
    created_at    TEXT NOT NULL,
    reason        TEXT
);

CREATE TABLE action (
    id            INTEGER PRIMARY KEY,
    project_code  TEXT NOT NULL REFERENCES project(code),
    description   TEXT NOT NULL,
    owner         TEXT NOT NULL,
    priority      INTEGER NOT NULL,
    due           TEXT,
    status        TEXT NOT NULL,
    event_id      INTEGER NOT NULL REFERENCES event(id),
    reopen_count  INTEGER NOT NULL DEFAULT 0,
    created_at    TEXT NOT NULL,
    updated_at    TEXT NOT NULL
);

CREATE TABLE cycle (
    id            INTEGER PRIMARY KEY,
    project_code  TEXT NOT NULL REFERENCES project(code),
    name          TEXT NOT NULL,
    gate_id       INTEGER REFERENCES gate(id),
    closed_at     TEXT,
    validated     INTEGER NOT NULL DEFAULT 0,
    validated_at  TEXT,
    created_at    TEXT NOT NULL
);

CREATE TABLE cycle_item (
    id            INTEGER PRIMARY KEY,
    cycle_id      INTEGER NOT NULL REFERENCES cycle(id),
    project_code  TEXT NOT NULL REFERENCES project(code),
    action_id     INTEGER NOT NULL REFERENCES action(id),
    rank          INTEGER NOT NULL,
    created_at    TEXT NOT NULL
);

CREATE TABLE gate (
    id            INTEGER PRIMARY KEY,
    project_code  TEXT NOT NULL REFERENCES project(code),
    event_id      INTEGER NOT NULL REFERENCES event(id),
    name          TEXT NOT NULL,
    outcome       TEXT NOT NULL,
    planned_date  TEXT,
    actual_date   TEXT,
    created_at    TEXT NOT NULL
);

CREATE TABLE gate_item (
    id            INTEGER PRIMARY KEY,
    gate_id       INTEGER NOT NULL REFERENCES gate(id),
    project_code  TEXT NOT NULL REFERENCES project(code),
    text          TEXT NOT NULL,
    passed        INTEGER NOT NULL DEFAULT 0,
    created_at    TEXT NOT NULL
);

CREATE TABLE engagement_signals (
    id            INTEGER PRIMARY KEY,
    project_code  TEXT NOT NULL REFERENCES project(code),
    owner         TEXT NOT NULL,
    kind          TEXT NOT NULL,
    action_id     INTEGER REFERENCES action(id),
    occurred_at   TEXT NOT NULL,
    note          TEXT,
    resolved      INTEGER NOT NULL DEFAULT 0,
    resolved_at   TEXT
);

CREATE TABLE meeting_minutes (
    id            INTEGER PRIMARY KEY,
    project_code  TEXT NOT NULL REFERENCES project(code),
    cycle_id      INTEGER REFERENCES cycle(id),
    held_at       TEXT NOT NULL,
    attendees     TEXT,
    decisions     TEXT,
    agreed_actions TEXT,
    risks         TEXT,
    minutes_text  TEXT NOT NULL
);

CREATE TABLE report_history (
    id            INTEGER PRIMARY KEY,
    project_code  TEXT NOT NULL REFERENCES project(code),
    generated_at  TEXT NOT NULL,
    pdf_rel_path  TEXT NOT NULL,
    html_rel_path TEXT NOT NULL,
    prepared_for  TEXT,
    snapshot_sha256 TEXT NOT NULL
);

CREATE TABLE meta (
    key   TEXT PRIMARY KEY,
    value TEXT NOT NULL
);

CREATE VIRTUAL TABLE fts_search USING fts5(
    project_code,
    kind,
    body
);

CREATE INDEX idx_event_project   ON event(project_code);
CREATE INDEX idx_action_project  ON action(project_code);
CREATE INDEX idx_evidence_project ON evidence(project_code);
CREATE INDEX idx_cycle_item_cycle ON cycle_item(cycle_id);
CREATE INDEX idx_gate_item_gate  ON gate_item(gate_id);
CREATE INDEX idx_engagement_signals_project_owner ON engagement_signals(project_code, owner);
CREATE INDEX idx_meeting_minutes_project ON meeting_minutes(project_code);
CREATE INDEX idx_report_history_project ON report_history(project_code);
"""


def _connect(path: str | os.PathLike[str]) -> sqlite3.Connection:
    return sqlite3.connect(str(path))


def _create_all(conn: sqlite3.Connection) -> None:
    """Create every table, index and the FTS table (C2.4)."""
    conn.executescript(SCHEMA_SQL)
    conn.execute(
        "INSERT INTO meta (key, value) VALUES ('schema_version', ?)",
        (SCHEMA_VERSION,),
    )
    conn.commit()


def _schema_version(conn: sqlite3.Connection) -> str | None:
    try:
        row = conn.execute(
            "SELECT value FROM meta WHERE key = 'schema_version'"
        ).fetchone()
    except sqlite3.OperationalError:
        return None  # no meta table: file is new (or foreign — treated as new)
    return row[0] if row is not None else None


def migrate(path: str | os.PathLike[str]) -> int:
    """Bring the file at ``path`` to schema version ``'1'`` (C2.4).

    - New (or empty) file: create all 10 tables + ``fts_search`` + the
      5 indexes + ``meta`` with ``schema_version = '1'``.
    - Re-run on a version-``'1'`` file: no-op (idempotent).
    - File with an unknown ``meta.schema_version``: ``CoreError`` with
      code ``unknown_schema`` — never touch a file this build does not
      understand (future protection).

    Returns ``1`` on success.
    """
    conn = _connect(path)
    try:
        version = _schema_version(conn)
        if version is None:
            _create_all(conn)
        elif version == SCHEMA_VERSION:
            pass  # idempotent: nothing to do
        else:
            raise CoreError(
                f"unknown schema version {version!r}", code="unknown_schema"
            )
        return 1
    finally:
        conn.close()


__all__ = [
    "FTS_TABLE",
    "INDEXES",
    "META_TABLE",
    "SCHEMA_SQL",
    "SCHEMA_VERSION",
    "TABLES",
    "migrate",
]
