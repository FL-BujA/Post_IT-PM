"""A-00 — DataKit exposes the eleven C2.1 repository slots.

The eleven attribute names and their classes are transcribed verbatim
from the C2.1 code block of contracts/02-CONTRACTS-data.md.  This is
the assertion whose absence let the divergence stand.
"""

from __future__ import annotations

from typing import Any

from data.actions import ActionRepo
from data.cycles import CycleRepo
from data.db import DataKit
from data.evidence import EvidenceRepo
from data.events import EventRepo
from data.gates import GateRepo
from data.integrity import IntegrityService
from data.minutes import MinutesRepo
from data.migrate import migrate
from data.projects import ProjectRepo
from data.reports_history import ReportHistoryRepo
from data.search import SearchRepo
from data.signals import SignalRepo

#: C2.1 — the eleven slots, transcribed from the contract.
C21_SLOTS: tuple[tuple[str, type], ...] = (
    ("projects", ProjectRepo),
    ("events", EventRepo),
    ("cycles", CycleRepo),
    ("gates", GateRepo),
    ("actions", ActionRepo),
    ("evidence", EvidenceRepo),
    ("minutes", MinutesRepo),
    ("signals", SignalRepo),
    ("reports", ReportHistoryRepo),
    ("search", SearchRepo),
    ("integrity", IntegrityService),
)


def _kit(tmp_path: Any) -> DataKit:
    db = str(tmp_path / "app.db")
    migrate(db)
    return DataKit(db)


def test_c21_attribute_set(tmp_path: Any) -> None:
    kit = _kit(tmp_path)
    for name, cls in C21_SLOTS:
        assert hasattr(kit, name), f"DataKit is missing C2.1 slot {name!r}"
        assert isinstance(getattr(kit, name), cls), (
            f"DataKit.{name} is {type(getattr(kit, name)).__name__}, "
            f"not {cls.__name__}"
        )


def test_slots_are_lazy_and_cached(tmp_path: Any) -> None:
    kit = _kit(tmp_path)
    # Lazy: a DataKit that is never asked for a repo constructs none.
    assert kit._repos == {}
    # Cached: accessing a slot twice returns the SAME instance.
    assert kit.projects is kit.projects
    assert kit.events is kit.events
    assert kit.cycles is kit.cycles
    assert kit.gates is kit.gates
    assert kit.actions is kit.actions
    assert kit.evidence is kit.evidence
    assert kit.minutes is kit.minutes
    assert kit.signals is kit.signals
    assert kit.reports is kit.reports
    assert kit.search is kit.search
    assert kit.integrity is kit.integrity
    # Only the slots actually asked for were constructed.
    assert set(kit._repos) == {
        "projects",
        "events",
        "cycles",
        "gates",
        "actions",
        "evidence",
        "minutes",
        "signals",
        "reports",
        "search",
        "integrity",
    }


def test_tx_close_and_init_behave_as_before(tmp_path: Any) -> None:
    kit = _kit(tmp_path)
    # __init__ pinned the C2.5 settings on the single connection.
    row = kit.tx(lambda conn: conn.execute("PRAGMA journal_mode").fetchone())
    assert row[0] == "wal"
    # tx commits on return.
    kit.projects.create("P001", "Alpha")
    # tx rolls back (and re-raises) on exception.
    try:
        kit.tx(lambda conn: (_ for _ in ()).throw(RuntimeError("boom")))
    except RuntimeError as exc:
        assert str(exc) == "boom"
    else:
        raise AssertionError("tx should re-raise")
    kit.close()
    try:
        kit.conn.execute("SELECT 1")
    except Exception as exc:
        assert "closed" in str(exc)
    else:
        raise AssertionError("connection should be closed")


def test_repo_built_old_way_and_new_way_read_same_row(tmp_path: Any) -> None:
    db = str(tmp_path / "app.db")
    migrate(db)
    kit = DataKit(db)
    row = kit.projects.create("P001", "Alpha", sponsor="S")
    # Old way: the caller constructs the repository directly with a
    # kit-like object (the kit itself satisfies the protocol).
    old_way = ProjectRepo(kit)
    # New way: the C2.1 slot on the kit.
    new_way = kit.projects
    assert old_way.get(row.code) == new_way.get(row.code)
    assert old_way.get(row.code).to_dict() == new_way.get(row.code).to_dict()
