"""services.flow — FlowService (cards A-02, A-03a, A-03b).

The eight C3.3 methods: project, cycle, gate, action, minutes and the
project snapshot. Five delegate to the built services (ProjectSVC,
PhaseSVC, ActionsSVC); record_gate, add_minutes and list_for_project
go through the DataKit repositories directly.
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from typing import Any

from core import (
    ActionStatus,
    CoreError,
    GateOutcome,
    ServiceError,
)
from data import (
    ActionRow,
    CycleRow,
    DataKit,
    EventRow,
    GateRow,
    MinutesRow,
    ProjectRow,
    SignalRow,
)
from data.migrate import migrate
from services.actions import ActionsSVC
from services.phase import PhaseSVC
from services.projects import ProjectSVC


#: Gate outcomes that mean "not yet decided". A gate is OPEN while its
#: outcome is one of these. Compared as strings so the check works whether
#: the row stores a GateOutcome member or its value.
_OPEN_GATE_OUTCOMES = frozenset(
    {"", "planned", str(GateOutcome.PLANNED), GateOutcome.PLANNED.value}
)

#: C3.3 snapshot limits (frozen by the contract).
_MAX_EVENTS = 20
_MAX_MINUTES = 5
_MAX_SIGNALS = 10


@dataclass(frozen=True)
class ProjectSnapshot:
    """C3.3 list_for_project — the ONE query the UI needs.

    Every element is a C2 row; this type introduces no new row shape.
    Ordering is settled here so no later layer re-sorts:
      actions     priority ascending, current cycle only
      open_gates  gates whose outcome is still PLANNED
      events      newest first, at most 20
      minutes     at most 5, newest last as the repo returns them
      signals     at most 10
    """

    project: ProjectRow
    current_cycle: CycleRow | None
    actions: list[ActionRow]
    open_gates: list[GateRow]
    events: list[EventRow]
    minutes: list[MinutesRow]
    signals: list[SignalRow]


class FlowService:
    """C3.3 FlowService — cycle / gate / action orchestration (A-02).

    Delegates to the built services; owns only the C3.3 frozen rules
    that the built services do not enforce (cycle_open).
    """

    def __init__(self, workspace_root: str) -> None:
        self._root = workspace_root
        self._data: DataKit | None = None
        self._project_svc = ProjectSVC(workspace_root)
        self._phase_svc = PhaseSVC(workspace_root)
        self._actions_svc = ActionsSVC(workspace_root)

    def __getattr__(self, name: str) -> Any:
        """Raise CoreError for unknown attributes (matches the
        _Placeholder behavior from P-10a-i)."""
        if name.startswith("_"):
            raise AttributeError(name)
        raise CoreError(
            f"services slot 'flow' has no attribute '{name}'"
        )

    def _ensure_data(self) -> DataKit:
        """Lazily create the DataKit on first use (avoids opening the
        database in __init__, which would break ServiceKit tests that
        use non-existent paths)."""
        if self._data is None:
            db_path = os.path.join(self._root, "app.db")
            migrate(db_path)
            self._data = DataKit(db_path)
        return self._data

    # -- project -----------------------------------------------------------

    def create_project(
        self,
        name: str,
        sponsor: str,
        target_date: str,
        objective: str,
        charter_text: str = "",
        constraints_text: str = "",
    ) -> ProjectRow:
        """C3.3 create_project — maps parameters BY NAME onto
        ProjectSVC.create_project, whose order differs."""
        return self._project_svc.create_project(
            name=name,
            target_date=target_date,
            sponsor=sponsor,
            objective=objective,
            charter_text=charter_text,
            constraints_text=constraints_text,
        )

    # -- cycle -------------------------------------------------------------

    def open_cycle(self, project_code: str, name: str) -> CycleRow:
        """C3.3 open_cycle — only one open cycle per project; a second
        while one is open raises ServiceError code 'cycle_open'."""
        current = self._ensure_data().cycles.current_for(project_code)
        if current is not None:
            raise ServiceError(
                f"project {project_code} already has an open cycle "
                f"(close it first)",
                code="cycle_open",
            )
        return self._phase_svc.open_cycle(project_code, name)

    def close_cycle(self, project_code: str, gate_id: int) -> CycleRow:
        """C3.3 close_cycle — delegates to PhaseSVC (I3 guard lives
        there and in the data layer)."""
        return self._phase_svc.close_cycle(project_code, gate_id)

    # -- gate --------------------------------------------------------------

    def record_gate(
        self,
        project_code: str,
        gate_id: int,
        outcome: GateOutcome,
        actual_date: str | None = None,
    ) -> GateRow:
        """C3.3 record_gate — stores the outcome on the gate and returns
        the GateRow. Delegates to the data layer's GateRepo."""
        gate = self._ensure_data().gates.get(gate_id)
        if gate.project_code != project_code:
            raise CoreError(
                f"gate {gate_id} belongs to {gate.project_code}, "
                f"not {project_code}"
            )
        return self._ensure_data().gates.record_outcome(gate_id, outcome)

    # -- action ------------------------------------------------------------

    def add_action(
        self,
        project_code: str,
        title: str,
        owner: str,
        description: str = "",
        priority: int = 9,
        due_start: str | None = None,
        due_end: str | None = None,
        cycle_id: int | None = None,
    ) -> ActionRow:
        """C3.3 add_action — identical signature, pass through."""
        return self._actions_svc.add_action(
            project_code,
            title,
            owner,
            description=description,
            priority=priority,
            due_start=due_start,
            due_end=due_end,
            cycle_id=cycle_id,
        )

    def set_action_status(
        self,
        project_code: str,
        action_id: int,
        new: ActionStatus,
    ) -> ActionRow:
        """C3.3 set_action_status — rename of ActionsSVC.change_status."""
        return self._actions_svc.change_status(project_code, action_id, new)

    # -- minutes -----------------------------------------------------------

    def add_minutes(
        self,
        project_code: str,
        held_at: str,
        attendees: str | None,
        decisions: str | None,
        agreed_actions: str | None,
        risks: str | None,
        minutes_text: str,
        cycle_id: int | None = None,
    ) -> MinutesRow:
        """C3.3 add_minutes — emits the MEETING event via the data layer.

        MinutesRepo.add returns the new row id; this method fetches the
        row so the contract's MinutesRow return type is honoured.

        agreed_actions is free text. No action rows are created from it
        (C3.3 frozen: the PM adds actions explicitly).
        """
        kit = self._ensure_data()
        minutes_id = kit.minutes.add(
            project_code,
            held_at,
            attendees,
            decisions,
            agreed_actions,
            risks,
            minutes_text,
            cycle_id=cycle_id,
        )
        for row in kit.minutes.list_for(project_code):
            if row.id == minutes_id:
                return row
        raise CoreError(
            f"minutes row {minutes_id} not readable after insert"
        )

    # -- snapshot ----------------------------------------------------------

    def list_for_project(self, project_code: str) -> ProjectSnapshot:
        """C3.3 list_for_project — one call, the whole project state.

        Raises UnknownProjectData (from ProjectRepo.get) for an unknown
        code. Every list_for below returns an empty list for a project
        with no rows; none of them raise.
        """
        kit = self._ensure_data()

        project = kit.projects.get(project_code)
        current = kit.cycles.current_for(project_code)

        if current is None:
            actions: list[ActionRow] = []
        else:
            actions = sorted(
                kit.actions.list_for(project_code, cycle_id=current.id),
                key=lambda a: a.priority,
            )

        open_gates = [
            g
            for g in kit.gates.list_for(project_code)
            if g.outcome is None or str(g.outcome) in _OPEN_GATE_OUTCOMES
        ]

        # EventRepo.list_for orders occurred_at ASC (C2.2). Take the newest
        # slice, then reverse so the snapshot is newest-first.
        events = list(reversed(kit.events.list_for(project_code)[-_MAX_EVENTS:]))

        minutes = kit.minutes.list_for(project_code)[-_MAX_MINUTES:]
        signals = kit.signals.list_for(project_code)[-_MAX_SIGNALS:]

        return ProjectSnapshot(
            project=project,
            current_cycle=current,
            actions=actions,
            open_gates=open_gates,
            events=events,
            minutes=minutes,
            signals=signals,
        )
