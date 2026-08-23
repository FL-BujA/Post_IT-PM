"""Tests for data.minutes + data.signals — card P-09a.

Done-when (P-09a):
  - minutes.add emits a MEETING event and stores minutes_text verbatim
    (test writes a string containing '**bold**' and reads back the exact
    bytes — no normalisation, no markdown handling).
  - minutes.add stores the unique token 'quartz-cinder' when given it;
    this card asserts STORAGE only. The search assertion for that token
    belongs to P-09b — do not add a search test here.
  - signals.insert emits a SIGNAL event whose summary starts with
    'Signal #' (test asserts the prefix, the frozen format).
  - signals.list_for filters: kind, owner, and resolved each tested
    independently (three assertions, one fixture).
  - signals.set_resolved toggles resolved and sets resolved_at
    (test asserts resolved_at is None before and non-None after).
"""

from __future__ import annotations

from dataclasses import fields
from typing import Any

import pytest

from core.enums import EventKind, SignalKind
from data.db import DataKit
from data.migrate import migrate
from data.minutes import MinutesRepo
from data.rows import SignalRow
from data.signals import SignalRepo


def _kit(tmp_path: Any) -> DataKit:
    db = str(tmp_path / "app.db")
    migrate(db)
    return DataKit(db)


def _create_project(kit: DataKit, code: str = "P001") -> None:
    """Create a minimal project row for FK references."""
    ts = "2026-01-01T00:00:00"
    kit.conn.execute(
        "INSERT INTO project (code, name, status, created_at, updated_at) "
        "VALUES (?, ?, 'active', ?, ?)",
        (code, f"Test {code}", ts, ts),
    )
    kit.conn.commit()


# ---------------------------------------------------------------------------
# minutes
# ---------------------------------------------------------------------------


def test_minutes_add_emits_meeting_event(tmp_path: Any) -> None:
    """minutes.add emits a MEETING event (ref_table='minutes')."""
    kit = _kit(tmp_path)
    _create_project(kit)
    repo = MinutesRepo(kit)

    repo.add(
        project_code="P001",
        held_at="2026-01-15T10:00:00",
        attendees="Ana, Ben",
        decisions="Ship it",
        agreed_actions="Write docs",
        risks="None",
        minutes_text="Meeting notes",
    )

    rows = kit.conn.execute(
        "SELECT kind, ref_table, ref_id FROM event WHERE kind = 'meeting'"
    ).fetchall()
    assert len(rows) == 1
    assert rows[0][0] == EventKind.MEETING.value
    assert rows[0][1] == "minutes"
    assert rows[0][2] is not None


def test_minutes_add_stores_text_verbatim(tmp_path: Any) -> None:
    """minutes_text is stored verbatim — no normalisation, no markdown."""
    kit = _kit(tmp_path)
    _create_project(kit)
    repo = MinutesRepo(kit)

    original = "This is **bold** and *italic* text with\nnewlines and  spaces."
    repo.add(
        project_code="P001",
        held_at="2026-01-15T10:00:00",
        attendees=None,
        decisions=None,
        agreed_actions=None,
        risks=None,
        minutes_text=original,
    )

    row = kit.conn.execute(
        "SELECT minutes_text FROM meeting_minutes WHERE project_code = 'P001'"
    ).fetchone()
    assert row[0] == original


def test_minutes_add_stores_unique_token(tmp_path: Any) -> None:
    """The token 'quartz-cinder' is stored (storage only, no search)."""
    kit = _kit(tmp_path)
    _create_project(kit)
    repo = MinutesRepo(kit)

    repo.add(
        project_code="P001",
        held_at="2026-01-15T10:00:00",
        attendees=None,
        decisions=None,
        agreed_actions=None,
        risks=None,
        minutes_text="quartz-cinder",
    )

    row = kit.conn.execute(
        "SELECT minutes_text FROM meeting_minutes WHERE project_code = 'P001'"
    ).fetchone()
    assert row[0] == "quartz-cinder"


# ---------------------------------------------------------------------------
# signals
# ---------------------------------------------------------------------------


def test_signals_insert_emits_signal_event_with_prefix(tmp_path: Any) -> None:
    """SIGNAL event summary starts with 'Signal #' (frozen format)."""
    kit = _kit(tmp_path)
    _create_project(kit)
    repo = SignalRepo(kit)

    repo.insert(
        kind=SignalKind.EXTENSION_REQUEST,
        project_code="P001",
        owner="Ana",
        note="Need more time",
    )

    rows = kit.conn.execute(
        "SELECT title, body FROM event WHERE kind = 'signal'"
    ).fetchall()
    assert len(rows) == 1
    assert rows[0][0].startswith("Signal #")
    assert rows[0][1].startswith("Signal #")


def test_signals_list_for_filters(tmp_path: Any) -> None:
    """list_for filters by kind, owner, and resolved independently."""
    kit = _kit(tmp_path)
    _create_project(kit)
    repo = SignalRepo(kit)

    # Insert three signals with different attributes.
    repo.insert(kind=SignalKind.DEFER, project_code="P001", owner="Ana")
    repo.insert(kind=SignalKind.LATE_START, project_code="P001", owner="Ben")
    repo.insert(kind=SignalKind.DEFER, project_code="P001", owner="Ben")

    # Filter by kind.
    results = repo.list_for(project_code="P001", kind=SignalKind.DEFER)
    assert len(results) == 2
    assert all(row.kind == SignalKind.DEFER.value for row in results)

    # Filter by owner.
    results = repo.list_for(project_code="P001", owner="Ana")
    assert len(results) == 1
    assert results[0].owner == "Ana"

    # Filter by resolved (all are unresolved initially).
    results = repo.list_for(project_code="P001", resolved=False)
    assert len(results) == 3

    # No filter: all three.
    results = repo.list_for(project_code="P001")
    assert len(results) == 3


def test_signals_set_resolved_toggles_and_stamps(tmp_path: Any) -> None:
    """set_resolved toggles resolved and sets resolved_at."""
    kit = _kit(tmp_path)
    _create_project(kit)
    repo = SignalRepo(kit)

    sig_id = repo.insert(
        kind=SignalKind.REOPEN,
        project_code="P001",
        owner="Ana",
    )

    # Before: resolved=0, resolved_at is NULL.
    row = kit.conn.execute(
        "SELECT resolved, resolved_at FROM engagement_signals WHERE id = ?",
        (sig_id,),
    ).fetchone()
    assert row[0] == 0
    assert row[1] is None

    # After set_resolved(True): resolved=1, resolved_at is set.
    repo.set_resolved(sig_id, True)
    row = kit.conn.execute(
        "SELECT resolved, resolved_at FROM engagement_signals WHERE id = ?",
        (sig_id,),
    ).fetchone()
    assert row[0] == 1
    assert row[1] is not None

    # After set_resolved(False): resolved=0, resolved_at still set.
    repo.set_resolved(sig_id, False)
    row = kit.conn.execute(
        "SELECT resolved, resolved_at FROM engagement_signals WHERE id = ?",
        (sig_id,),
    ).fetchone()
    assert row[0] == 0
    assert row[1] is not None


def test_signalrow_matches_table(tmp_path: Any) -> None:
    """SignalRow's field names equal the engagement_signals columns in order."""
    kit = _kit(tmp_path)
    columns = [
        r[1]
        for r in kit.conn.execute("PRAGMA table_info(engagement_signals)")
    ]
    assert [f.name for f in fields(SignalRow)] == columns