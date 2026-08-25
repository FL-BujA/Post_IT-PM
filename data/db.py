"""data.db — connection lifecycle and transaction helper (contract C2.5).

``DataKit`` owns ONE connection to one SQLite file.  At construction it
pins the two connection settings frozen by C2.5 — ``journal_mode = wal``
and ``busy_timeout = 5000`` — and ``tx`` runs a callback in a single
transaction: commit on success, rollback on any exception.

Deliberately NOT here (card P-05 rule): any repository logic.  No
``SELECT``/``INSERT`` policy, no services import, no third-party
dependencies — lifecycle + ``tx`` only.
"""

from __future__ import annotations

import os
import sqlite3
from collections.abc import Callable
from typing import Any, Self

from data.actions import ActionRepo
from data.cycles import CycleRepo
from data.evidence import EvidenceRepo
from data.events import EventRepo
from data.gates import GateRepo
from data.integrity import IntegrityService
from data.minutes import MinutesRepo
from data.projects import ProjectRepo
from data.reports_history import ReportHistoryRepo
from data.search import SearchRepo
from data.signals import SignalRepo

#: Frozen connection settings (C2.5).
JOURNAL_MODE = "wal"
BUSY_TIMEOUT_MS = 5000


class DataKit:
    """A live SQLite connection with the C2.5 settings pinned.

    ``DataKit(path)`` connects to the file at ``path`` (created if it
    does not exist — run ``data.migrate`` on it before writing) and
    immediately applies the WAL journal mode and the 5 s busy timeout.

    C2.1 assembly (A-00): all eleven C2.1 slots are real repositories
    over this ONE connection, constructed lazily on first access and
    cached — a ``DataKit`` that is never asked for a repo constructs
    none.  The shape never reshuffles.
    """

    def __init__(self, path: str | os.PathLike[str]) -> None:
        self.path = os.fspath(path)
        self.conn = sqlite3.connect(self.path)
        self.conn.execute(f"PRAGMA journal_mode = {JOURNAL_MODE}")
        self.conn.execute(f"PRAGMA busy_timeout = {BUSY_TIMEOUT_MS}")
        # C2.1 assembly (A-00): lazy, cached repository slots.  The
        # mapping is the single source of the eleven C2.1 attributes.
        self._repo_factories: dict[str, Callable[[], Any]] = {
            "projects": lambda: ProjectRepo(self),
            "events": lambda: EventRepo(self),
            "cycles": lambda: CycleRepo(self),
            "gates": lambda: GateRepo(self),
            "actions": lambda: ActionRepo(self),
            "evidence": lambda: EvidenceRepo(self),
            "minutes": lambda: MinutesRepo(self),
            "signals": lambda: SignalRepo(self),
            "reports": lambda: ReportHistoryRepo(self),
            "search": lambda: SearchRepo(self),
            "integrity": lambda: IntegrityService(self),
        }
        self._repos: dict[str, Any] = {}

    def __getattr__(self, name: str) -> Any:
        # C2.1 assembly (A-00): lazy, cached repository slots.  Only
        # reached for names the normal lookup missed, so ``tx``,
        # ``close``, ``conn`` and friends behave exactly as before.
        factories = self.__dict__.get("_repo_factories")
        if factories is not None and name in factories:
            repos = self.__dict__.setdefault("_repos", {})
            if name not in repos:
                repos[name] = factories[name]()
            return repos[name]
        raise AttributeError(f"{type(self).__name__!r} object has no attribute {name!r}")

    def tx(self, fn: Callable[[sqlite3.Connection], Any]) -> Any:
        """Run ``fn(conn)`` inside one transaction (C2.5).

        Commits if ``fn`` returns; rolls back (and re-raises) if ``fn``
        raises.  The connection itself is never closed here — it belongs
        to the owner of the ``DataKit``.
        """
        try:
            result = fn(self.conn)
            self.conn.commit()
            return result
        except Exception:
            self.conn.rollback()
            raise

    def close(self) -> None:
        """Close the underlying connection (idempotent)."""
        self.conn.close()

    def __enter__(self) -> Self:
        return self

    def __exit__(self, *exc: object) -> None:
        self.close()


__all__ = ["BUSY_TIMEOUT_MS", "JOURNAL_MODE", "DataKit"]
