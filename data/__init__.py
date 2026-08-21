"""data — SQLite schema, connection lifecycle, row shapes (C2.0, C2.4, C2.5)."""

from data.db import BUSY_TIMEOUT_MS, JOURNAL_MODE, DataKit
from data.migrate import FTS_TABLE, INDEXES, META_TABLE, TABLES, migrate
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

__all__ = [
    "BUSY_TIMEOUT_MS",
    "FTS_TABLE",
    "INDEXES",
    "JOURNAL_MODE",
    "META_TABLE",
    "TABLES",
    "ActionRow",
    "CharterRow",
    "CycleItemRow",
    "CycleRow",
    "DataKit",
    "DecisionRow",
    "EventRow",
    "EvidenceRow",
    "GateItemRow",
    "GateRow",
    "ProjectRow",
    "migrate",
]
