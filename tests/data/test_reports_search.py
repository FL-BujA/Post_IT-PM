"""Tests for data.reports_history + data.search — card P-09b.

Done-when (P-09b):
  - report_history.add emits a REPORT event with ref reports/<id>;
  - report_history.list_for returns rows ordered generated_at DESC
    (fixture of 3 rows with distinct timestamps, exact id order asserted);
  - search returns the minutes row containing the unique token
    'quartz-cinder' when queried for it, with table 'minutes' in the
    result (the P-09a storage guarantee, now proven findable);
  - multi-word terms use FTS5 AND semantics: a two-token query returns
    ONLY the row containing both (fixture has one row per token and one
    row with both; assert exactly one hit);
  - project_code filter works (two-project fixture sharing a token,
    assert only the filtered project's row returns);
  - limit is honoured (fixture of 5 hits, limit=2, assert len == 2);
  - snippet is non-empty and contains the queried term (string assert).
"""

from __future__ import annotations

from dataclasses import fields
from typing import Any

import pytest

from core.enums import EventKind
from data.db import DataKit
from data.migrate import migrate
from data.minutes import MinutesRepo
from data.reports_history import ReportHistoryRepo
from data.rows import ReportRow
from data.search import SearchRepo


def _kit(tmp_path: Any) -> DataKit:
    db = str(tmp_path / "app.db")
    migrate(db)
    kit = DataKit(db)
    # Assemble the P-09b repositories over the shared connection.
    kit.minutes = MinutesRepo(kit)
    kit.reports = ReportHistoryRepo(kit)
    kit.search = SearchRepo(kit)
    return kit


# ---------------------------------------------------------------------------
# P-09b — ReportHistoryRepo
# ---------------------------------------------------------------------------


def test_report_add_emits_report_event_with_ref(tmp_path: Any) -> None:
    kit = _kit(tmp_path)
    kit.projects.create("P001", "Alpha")
    new_id = kit.reports.add(
        "P001",
        "reports/P001/2026-08-22_alpha.pdf",
        "reports/P001/2026-08-22_alpha.html",
        "Sponsor A",
        "abc123",
        generated_at="2026-08-22T10:00:00+00:00",
    )
    assert new_id > 0
    # The REPORT event must carry ref_table='reports', ref_id=new_id.
    stored = kit.conn.execute(
        "SELECT ref_table, ref_id, kind FROM event "
        "WHERE kind = ? AND ref_table = 'reports' AND ref_id = ?",
        (EventKind.REPORT.value, new_id),
    ).fetchone()
    assert stored is not None
    assert stored[0] == "reports"
    assert stored[1] == new_id
    assert stored[2] == "report"


def test_report_list_for_orders_generated_at_desc(tmp_path: Any) -> None:
    kit = _kit(tmp_path)
    kit.projects.create("P001", "Alpha")
    # 3 rows with distinct timestamps, inserted out of order.
    id1 = kit.reports.add(
        "P001", "r1.pdf", "r1.html", "Sponsor A", "sha1",
        generated_at="2026-08-22T01:00:00+00:00",
    )
    id2 = kit.reports.add(
        "P001", "r2.pdf", "r2.html", "Sponsor A", "sha2",
        generated_at="2026-08-22T03:00:00+00:00",
    )
    id3 = kit.reports.add(
        "P001", "r3.pdf", "r3.html", "Sponsor A", "sha3",
        generated_at="2026-08-22T02:00:00+00:00",
    )
    rows = kit.reports.list_for("P001")
    assert len(rows) == 3
    # generated_at DESC: id2 (03:00), id3 (02:00), id1 (01:00).
    assert [row.id for row in rows] == [id2, id3, id1]


def test_reportrow_matches_table(tmp_path: Any) -> None:
    """ReportRow's field names equal the report_history columns in order."""
    kit = _kit(tmp_path)
    columns = [
        r[1]
        for r in kit.conn.execute("PRAGMA table_info(report_history)")
    ]
    assert [f.name for f in fields(ReportRow)] == columns


# ---------------------------------------------------------------------------
# P-09b — SearchRepo
# ---------------------------------------------------------------------------


def test_search_finds_minutes_row_with_unique_token(tmp_path: Any) -> None:
    kit = _kit(tmp_path)
    kit.projects.create("P001", "Alpha")
    kit.minutes.add(
        "P001",
        held_at="2026-08-22T09:00:00+00:00",
        attendees="Ana, Ben",
        decisions="none",
        agreed_actions="none",
        risks="none",
        minutes_text="The quartz-cinder deployment went well.",
    )
    hits = kit.search.search("quartz-cinder")
    assert len(hits) == 1
    assert hits[0].table == "minutes"
    assert hits[0].snippet  # non-empty
    assert "quartz-cinder" in hits[0].snippet


def test_search_multi_word_and_semantics(tmp_path: Any) -> None:
    kit = _kit(tmp_path)
    kit.projects.create("P001", "Alpha")
    # One row per token, one row with both.
    kit.minutes.add(
        "P001",
        held_at="2026-08-22T09:00:00+00:00",
        attendees="Ana",
        decisions="none",
        agreed_actions="none",
        risks="none",
        minutes_text="alpha token only",
    )
    kit.minutes.add(
        "P001",
        held_at="2026-08-22T10:00:00+00:00",
        attendees="Ben",
        decisions="none",
        agreed_actions="none",
        risks="none",
        minutes_text="beta token only",
    )
    kit.minutes.add(
        "P001",
        held_at="2026-08-22T11:00:00+00:00",
        attendees="Ana, Ben",
        decisions="none",
        agreed_actions="none",
        risks="none",
        minutes_text="alpha and beta together",
    )
    # Two-token query: ONLY the row containing both tokens.
    hits = kit.search.search("alpha beta")
    assert len(hits) == 1
    assert "alpha" in hits[0].snippet
    assert "beta" in hits[0].snippet


def test_search_project_code_filter(tmp_path: Any) -> None:
    kit = _kit(tmp_path)
    kit.projects.create("P001", "Alpha")
    kit.projects.create("P002", "Beta")
    # Two projects sharing a token.
    kit.minutes.add(
        "P001",
        held_at="2026-08-22T09:00:00+00:00",
        attendees="Ana",
        decisions="none",
        agreed_actions="none",
        risks="none",
        minutes_text="shared token in P001",
    )
    kit.minutes.add(
        "P002",
        held_at="2026-08-22T10:00:00+00:00",
        attendees="Ben",
        decisions="none",
        agreed_actions="none",
        risks="none",
        minutes_text="shared token in P002",
    )
    # Filter to P001: only P001's row returns.
    hits = kit.search.search("shared", project_code="P001")
    assert len(hits) == 1
    assert "P001" in hits[0].snippet
    # Filter to P002: only P002's row returns.
    hits = kit.search.search("shared", project_code="P002")
    assert len(hits) == 1
    assert "P002" in hits[0].snippet
    # No filter: both rows return.
    hits = kit.search.search("shared")
    assert len(hits) == 2


def test_search_limit_honoured(tmp_path: Any) -> None:
    kit = _kit(tmp_path)
    kit.projects.create("P001", "Alpha")
    # 5 hits, all containing the token.
    for i in range(5):
        kit.minutes.add(
            "P001",
            held_at=f"2026-08-22T09:0{i}:00+00:00",
            attendees="Ana",
            decisions="none",
            agreed_actions="none",
            risks="none",
            minutes_text=f"limit token {i}",
        )
    hits = kit.search.search("limit", limit=2)
    assert len(hits) == 2


def test_search_snippet_non_empty_and_contains_term(tmp_path: Any) -> None:
    kit = _kit(tmp_path)
    kit.projects.create("P001", "Alpha")
    kit.minutes.add(
        "P001",
        held_at="2026-08-22T09:00:00+00:00",
        attendees="Ana",
        decisions="none",
        agreed_actions="none",
        risks="none",
        minutes_text="The snippet-token test passed.",
    )
    hits = kit.search.search("snippet-token")
    assert len(hits) == 1
    assert hits[0].snippet  # non-empty
    assert "snippet-token" in hits[0].snippet
