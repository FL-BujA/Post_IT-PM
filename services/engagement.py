"""services.engagement — EngagementService (card A-04).

C3.4: the PM logs engagement signals (defer, extension request, late start,
reopen) and reads them back aggregated per owner.

C3.4 frozen rule: health_by_owner is the ONE definition of signal
aggregation. The report strip (C3.5) and the engagement view both call it —
neither re-counts.
"""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from typing import Any

from core import CoreError, SignalKind
from data import DataKit, SignalRow
from data.migrate import migrate

#: Event kind emitted on a signal. SignalRepo.insert emits it; this service
#: does not emit a second one.
SIGNAL_EVENT_KIND = "SIGNAL"


@dataclass(frozen=True)
class OwnerHealth:
    """C3.4 OwnerHealth — one owner's engagement picture.

    counts carries every SignalKind, including the ones with zero, so the
    report strip and the engagement view render the same four columns
    whether or not an owner has that kind.
    """

    owner: str
    counts: dict[SignalKind, int] = field(default_factory=dict)
    total: int = 0
    open_total: int = 0


class EngagementService:
    """C3.4 EngagementService — signals in, health out."""

    def __init__(self, workspace_root: str) -> None:
        self._root = workspace_root
        self._data: DataKit | None = None

    def __getattr__(self, name: str) -> Any:
        if name.startswith("_"):
            raise AttributeError(name)
        raise CoreError(
            f"services slot 'engagement' has no attribute '{name}'"
        )

    def _ensure_data(self) -> DataKit:
        """Lazily open the database, matching FlowService and
        EvidenceService."""
        if self._data is None:
            db_path = os.path.join(self._root, "app.db")
            migrate(db_path)
            self._data = DataKit(db_path)
        return self._data

    def _get_signal(self, project_code: str, signal_id: int) -> SignalRow:
        """Fetch one signal row by id. SignalRepo has no get(), so read the
        project's signals and select. Raises CoreError if absent."""
        for row in self._ensure_data().signals.list_for(project_code):
            if row.id == signal_id:
                return row
        raise CoreError(
            f"no signal {signal_id} for project {project_code!r}",
            code="signal_unknown",
        )

    # -- C3.4 --------------------------------------------------------------

    def record(
        self,
        project_code: str,
        kind: SignalKind,
        owner: str,
        action_id: int | None = None,
        note: str = "",
    ) -> SignalRow:
        """PM logs a defer / extension / late-start / reopen.

        SignalRepo.insert emits the SIGNAL event and returns the new id;
        this method fetches the row so the contract's SignalRow return type
        is honoured.

        kind=REOPEN from here is the manual path; the automatic one fires
        inside set_action_status. Both are allowed (C3.4).
        """
        kit = self._ensure_data()
        kit.projects.get(project_code)          # raises UnknownProjectData
        signal_id = kit.signals.insert(
            kind,
            project_code,
            owner,
            action_id=action_id,
            note=note,
        )
        return self._get_signal(project_code, signal_id)

    def mark_resolved(
        self,
        project_code: str,
        signal_id: int,
        resolved: bool = True,
    ) -> SignalRow:
        """Resolve or un-resolve a signal.

        SignalRepo.set_resolved returns None; this method fetches the row
        back so the contract's SignalRow return type is honoured.
        """
        self._get_signal(project_code, signal_id)   # raises if unknown
        self._ensure_data().signals.set_resolved(signal_id, resolved)
        return self._get_signal(project_code, signal_id)

    def health_by_owner(self, project_code: str) -> list[OwnerHealth]:
        """Aggregate ALL signals for the project by owner.

        This is the only place signal counts are computed (C3.4 frozen
        rule). Owners are returned in ascending name order so the report
        strip and the engagement view agree without either sorting.
        """
        rows = self._ensure_data().signals.list_for(project_code)

        by_owner: dict[str, list[SignalRow]] = {}
        for row in rows:
            by_owner.setdefault(row.owner, []).append(row)

        health: list[OwnerHealth] = []
        for owner in sorted(by_owner):
            owned = by_owner[owner]
            counts = {kind: 0 for kind in SignalKind}
            for row in owned:
                for kind in SignalKind:
                    if str(row.kind) == kind.value or row.kind == kind:
                        counts[kind] += 1
                        break
            health.append(
                OwnerHealth(
                    owner=owner,
                    counts=counts,
                    total=len(owned),
                    open_total=sum(1 for r in owned if not r.resolved),
                )
            )
        return health

    def list_for(
        self,
        project_code: str,
        kind: SignalKind | str | None = None,
        owner: str | None = None,
        resolved: bool | None = None,
    ) -> list[SignalRow]:
        """The project's signals, filtered. Pass-through to SignalRepo."""
        return self._ensure_data().signals.list_for(
            project_code,
            kind=kind,
            owner=owner,
            resolved=resolved,
        )
