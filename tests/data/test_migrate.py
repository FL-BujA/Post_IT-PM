"""Tests for data.migrate / data.db / data.rows — card P-05 (C2.4, C2.5, C2.0).

Done-when (P-05):
  - migrate(tmp) creates all 10 tables + fts_search + 5 indexes + the
    unique evidence(rel_path) index; enumerated via sqlite_master;
  - meta.schema_version == '1'; re-running migrate() is a no-op;
  - migrate raises CoreError(code='unknown_schema') on a doctored
    version-'2' file;
  - DataKit: journal_mode 'wal', busy_timeout 5000, tx commits,
    tx rolls back;
  - row dataclasses: every field name matches the C2.0 column list
    (transcribed as test data, not comments).
"""

from __future__ import annotations

import sqlite3
from typing import Any

import pytest

import data as data_pkg
from core.errors import CoreError
from data.db import DataKit
from data.migrate import FTS_TABLE, INDEXES, TABLES, migrate
from data.rows import (
    ActionRow,
    CharterRow,
    CycleItemRow,
    CycleRow,
    DecisionRow,
    EventRow,
    EvidenceRow,
    GateItemRow,
    GateRow,
    ProjectRow,
)


def _master_names(db: str, kind: str) -> set[str]:
    conn = sqlite3.connect(db)
    try:
        rows = conn.execute(
            "SELECT name FROM sqlite_master WHERE type = ?", (kind,)
        ).fetchall()
    finally:
        conn.close()
    return {row[0] for row in rows}


# ---------------------------------------------------------------------------
# C2.4 — migrate
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("expected", [*TABLES, FTS_TABLE])
def test_migrate_creates_expected_tables(tmp_path: Any, expected: str) -> None:
    db = str(tmp_path / "app.db")
    migrate(db)
    assert expected in _master_names(db, "table")


@pytest.mark.parametrize("expected", INDEXES)
def test_migrate_creates_expected_indexes(tmp_path: Any, expected: str) -> None:
    db = str(tmp_path / "app.db")
    migrate(db)
    assert expected in _master_names(db, "index")


def test_evidence_rel_path_is_unique(tmp_path: Any) -> None:
    db = str(tmp_path / "app.db")
    migrate(db)
    cols = _master_names(db, "index")
    # SQLite auto-names the unique index on the unique column.
    assert "sqlite_autoindex_evidence_1" in cols


def test_meta_schema_version_is_one(tmp_path: Any) -> None:
    db = str(tmp_path / "app.db")
    migrate(db)
    conn = sqlite3.connect(db)
    try:
        row = conn.execute(
            "SELECT value FROM meta WHERE key = 'schema_version'"
        ).fetchone()
    finally:
        conn.close()
    assert row is not None and row[0] == "1"


def test_migrate_is_idempotent(tmp_path: Any) -> None:
    db = str(tmp_path / "app.db")
    migrate(db)
    before = _master_names(db, "table") | _master_names(db, "index")

    migrate(db)  # second call: no error, state unchanged

    after = _master_names(db, "table") | _master_names(db, "index")
    assert before == after

    conn = sqlite3.connect(db)
    try:
        row = conn.execute(
            "SELECT value FROM meta WHERE key = 'schema_version'"
        ).fetchone()
    finally:
        conn.close()
    assert row[0] == "1"


def test_migrate_raises_on_unknown_version(tmp_path: Any) -> None:
    db = str(tmp_path / "doctored.db")
    # Build a file that claims to be schema version '2'.
    conn = sqlite3.connect(db)
    try:
        conn.execute("CREATE TABLE meta (key TEXT PRIMARY KEY, value TEXT)")
        conn.execute("INSERT INTO meta (key, value) VALUES ('schema_version', '2')")
        conn.commit()
    finally:
        conn.close()

    with pytest.raises(CoreError) as excinfo:
        migrate(db)
    assert excinfo.value.code == "unknown_schema"


# ---------------------------------------------------------------------------
# C2.5 — DataKit
# ---------------------------------------------------------------------------


def test_datakit_pinned_pragmas(tmp_path: Any) -> None:
    db = str(tmp_path / "kit.db")
    kit = DataKit(db)
    try:
        mode = kit.conn.execute("PRAGMA journal_mode").fetchone()[0]
        timeout = kit.conn.execute("PRAGMA busy_timeout").fetchone()[0]
    finally:
        kit.close()
    assert mode == "wal"
    assert timeout == 5000


def test_datakit_tx_commits(tmp_path: Any) -> None:
    db = str(tmp_path / "kit.db")
    migrate(db)
    kit = DataKit(db)
    try:

        def write(conn: sqlite3.Connection) -> int:
            cur = conn.execute(
                "INSERT INTO project "
                "(code, name, status, created_at, updated_at) "
                "VALUES (?, ?, ?, ?, ?)",
                ("P999", "Commit test", "charter", "t", "t"),
            )
            return cur.lastrowid or -1

        rowid = kit.tx(write)
        # Committed: visible from a fresh connection.
        conn = sqlite3.connect(db)
        try:
            n = conn.execute(
                "SELECT COUNT(*) FROM project WHERE code = 'P999'"
            ).fetchone()[0]
        finally:
            conn.close()
        assert rowid >= 0
        assert n == 1
    finally:
        kit.close()


def test_datakit_tx_rolls_back(tmp_path: Any) -> None:
    db = str(tmp_path / "kit.db")
    migrate(db)
    kit = DataKit(db)
    try:

        def boom(conn: sqlite3.Connection) -> None:
            conn.execute(
                "INSERT INTO project "
                "(code, name, status, created_at, updated_at) "
                "VALUES (?, ?, ?, ?, ?)",
                ("P998", "Rollback test", "charter", "t", "t"),
            )
            raise RuntimeError("forced failure")

        with pytest.raises(RuntimeError):
            kit.tx(boom)

        # Rolled back: no row visible.
        n = kit.conn.execute(
            "SELECT COUNT(*) FROM project WHERE code = 'P998'"
        ).fetchone()[0]
        assert n == 0
    finally:
        kit.close()


# ---------------------------------------------------------------------------
# C2.0 — row dataclasses (fields == contract column names, transcribed)
# ---------------------------------------------------------------------------

#: C2.0 — the frozen column lists, transcribed as test data.
C20_COLUMNS: dict[type, tuple[str, ...]] = {
    ProjectRow: (
        "code",
        "name",
        "status",
        "charter",
        "target",
        "target_date",
        "status_rag",
        "red_flags",
        "escalation",
        "sponsor",
        "created_at",
        "updated_at",
    ),
    CharterRow: (
        "id",
        "project_code",
        "revision",
        "body",
        "key_dates",
        "created_at",
        "reason",
    ),
    EventRow: (
        "id",
        "project_code",
        "kind",
        "ref_table",
        "ref_id",
        "title",
        "body",
        "occurred_at",
        "created_at",
    ),
    EvidenceRow: (
        "id",
        "project_code",
        "ref_table",
        "ref_id",
        "original_name",
        "source_type",
        "rel_path",
        "size_bytes",
        "sha256",
        "attached_at",
    ),
    DecisionRow: (
        "id",
        "project_code",
        "event_id",
        "revision",
        "body",
        "created_at",
        "reason",
    ),
    ActionRow: (
        "id",
        "project_code",
        "description",
        "owner",
        "priority",
        "due",
        "status",
        "event_id",
        "reopen_count",
        "created_at",
        "updated_at",
    ),
    CycleRow: (
        "id",
        "project_code",
        "name",
        "gate_id",
        "closed_at",
        "validated",
        "validated_at",
        "created_at",
    ),
    CycleItemRow: (
        "id",
        "cycle_id",
        "project_code",
        "action_id",
        "rank",
        "created_at",
    ),
    GateRow: (
        "id",
        "project_code",
        "event_id",
        "name",
        "outcome",
        "planned_date",
        "actual_date",
        "created_at",
    ),
    GateItemRow: (
        "id",
        "gate_id",
        "project_code",
        "text",
        "passed",
        "created_at",
    ),
}


def _field_names(cls: type) -> list[str]:
    from dataclasses import fields

    return [f.name for f in fields(cls)]


@pytest.mark.parametrize("row_cls, columns", list(C20_COLUMNS.items()))
def test_row_fields_match_c20_columns(row_cls: type, columns: tuple[str, ...]) -> None:
    assert _field_names(row_cls) == list(columns)


def test_row_to_dict_keys_are_c20_columns() -> None:
    row = ProjectRow(
        code="P001",
        name="n",
        status="charter",
        charter=None,
        target=None,
        target_date=None,
        status_rag=None,
        red_flags=None,
        escalation=None,
        sponsor=None,
        created_at="t",
        updated_at="t",
    )
    d = row.to_dict()
    assert list(d.keys()) == list(C20_COLUMNS[ProjectRow])


def test_package_reexports_surface() -> None:
    assert data_pkg.migrate is migrate
    assert data_pkg.DataKit is DataKit
    assert data_pkg.TABLES == TABLES
    assert data_pkg.FTS_TABLE == FTS_TABLE
