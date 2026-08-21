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

#: Frozen connection settings (C2.5).
JOURNAL_MODE = "wal"
BUSY_TIMEOUT_MS = 5000


class DataKit:
    """A live SQLite connection with the C2.5 settings pinned.

    ``DataKit(path)`` connects to the file at ``path`` (created if it
    does not exist — run ``data.migrate`` on it before writing) and
    immediately applies the WAL journal mode and the 5 s busy timeout.
    """

    def __init__(self, path: str | os.PathLike[str]) -> None:
        self.path = os.fspath(path)
        self.conn = sqlite3.connect(self.path)
        self.conn.execute(f"PRAGMA journal_mode = {JOURNAL_MODE}")
        self.conn.execute(f"PRAGMA busy_timeout = {BUSY_TIMEOUT_MS}")

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
