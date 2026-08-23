"""services.compose — ServiceKit skeleton (card P-10a-i).

Freezes the C3.0 attribute set: every slot is a typed placeholder that
raises CoreError until a later card replaces it with a real service.
No real service logic, no filesystem, no database.
"""

from __future__ import annotations

from core import CoreError
from services.projects import ProjectSVC

#: The frozen C3.0 slot set — later cards replace placeholders,
#: never add or rename slots.
C30_SLOTS = (
    "project_svc",
    "phase_svc",
    "actions_svc",
    "evidence_svc",
    "minutes_svc",
    "report_svc",
    "backup_svc",
    "integrity_svc",
)


class _Placeholder:
    """Typed placeholder for a C3.0 slot.

    Any attribute access raises CoreError naming the slot.
    """

    def __init__(self, slot: str) -> None:
        # Stored in the instance dict so __getattr__ never recurses.
        object.__setattr__(self, "_slot", slot)

    def __getattr__(self, name: str) -> None:
        raise CoreError(f"services slot '{self._slot}' is not implemented yet")

    def __setattr__(self, name: str, value: object) -> None:
        raise CoreError(f"services slot '{self._slot}' is not implemented yet")

    def __repr__(self) -> str:
        return f"<services slot '{self._slot}' placeholder>"


class ServiceKit:
    """Composition root for services (C3.1).

    Accepts a workspace root path and stores it. Does not open a
    database, create directories, or touch the filesystem.
    """

    def __init__(self, root: str) -> None:
        self.root = root
        for slot in C30_SLOTS:
            object.__setattr__(self, slot, _Placeholder(slot))
        # P-10a-ii: replace the project_svc placeholder with the real service.
        object.__setattr__(self, "project_svc", ProjectSVC(root))

    def __repr__(self) -> str:
        return f"ServiceKit(root={self.root!r})"
