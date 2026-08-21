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

from data._slots import (
    ActionRepoSlot,
    CharterRepoSlot,
    DecisionRepoSlot,
    EvidenceRepoSlot,
    IntegritySlot,
    SearchSlot,
)
from data.cycles import CycleRepo
from data.events import EventRepo
from data.gates import GateRepo
from data.projects import ProjectRepo

#: Frozen connection settings (C2.5).
JOURNAL_MODE = "wal"
BUSY_TIMEOUT_MS = 5000


class DataKit:
    """A live SQLite connection with the C2.5 settings pinned.

    ``DataKit(path)`` connects to the file at ``path`` (created if it
    does not exist — run ``data.migrate`` on it before writing) and
    immediately applies the WAL journal mode and the 5 s busy timeout.

    C2.1 assembly (frozen from P-06): ``data.projects`` and
    ``data.events`` are real repositories over this ONE connection; the
    remaining C2.1 slots (cycles, charter, evidence, decisions, actions,
    gates, search, integrity) are typed placeholders that raise
    ``CoreError`` until later cards fill them — the shape never
    reshuffles.
    """

    def __init__(self, path: str | os.PathLike[str]) -> None:
        self.path = os.fspath(path)
        self.conn = sqlite3.connect(self.path)
        self.conn.execute(f"PRAGMA journal_mode = {JOURNAL_MODE}")
        self.conn.execute(f"PRAGMA busy_timeout = {BUSY_TIMEOUT_MS}")

        # C2.1 assembly (P-06): real repos over the single connection.
        self.projects = ProjectRepo(self)
        self.events = EventRepo(self)

        # C2.1 assembly (P-07): gates + cycles slots filled in — invariant
        # I3 lives here (a cycle cannot close without a gate outcome).
        self.gates = GateRepo(self)
        self.cycles = CycleRepo(self)

        # C2.1 assembly (P-06): remaining slots — typed placeholders.
        self.charter: CharterRepoSlot = CharterRepoSlot()
        self.evidence: EvidenceRepoSlot = EvidenceRepoSlot()
        self.decisions: DecisionRepoSlot = DecisionRepoSlot()
        self.actions: ActionRepoSlot = ActionRepoSlot()
        self.search: SearchSlot = SearchSlot()
        self.integrity: IntegritySlot = IntegritySlot()

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
