"""data — SQLite schema, connection lifecycle, row shapes (C2.0, C2.4, C2.5)
and the C2.1 assembly: real (projects, events) repositories plus the typed
placeholder slots frozen from card P-06."""

from data._slots import (
    ActionRepoSlot,
    CharterRepoSlot,
    DecisionRepoSlot,
    EvidenceRepoSlot,
    IntegritySlot,
    SearchSlot,
)
from data.cycles import CycleRepo
from data.db import BUSY_TIMEOUT_MS, JOURNAL_MODE, DataKit
from data.gates import GateRepo
from data.events import EventRepo
from data.migrate import FTS_TABLE, INDEXES, META_TABLE, TABLES, migrate
from data.projects import ProjectRepo
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
    "ActionRepoSlot",
    "ActionRow",
    "CharterRepoSlot",
    "CharterRow",
    "CycleItemRow",
    "CycleRepo",
    "CycleRow",
    "DataKit",
    "DecisionRepoSlot",
    "DecisionRow",
    "EventRepo",
    "EventRow",
    "EvidenceRepoSlot",
    "EvidenceRow",
    "GateItemRow",
    "GateRepo",
    "GateRow",
    "IntegritySlot",
    "ProjectRepo",
    "ProjectRow",
    "SearchSlot",
    "migrate",
]
