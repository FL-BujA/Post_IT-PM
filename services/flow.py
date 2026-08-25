"""services.flow — FlowService (card A-02).

First six C3.3 methods: project, cycle, gate and action orchestration.
Five delegate to the built services (ProjectSVC, PhaseSVC, ActionsSVC);
record_gate is new and delegates to the data layer's GateRepo.
"""

from __future__ import annotations

import os
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
    GateRow,
    ProjectRow,
)
from data.migrate import migrate
from services.actions import ActionsSVC
from services.phase import PhaseSVC
from services.projects import ProjectSVC


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
