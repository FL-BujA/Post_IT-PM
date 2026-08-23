"""services.phase — phase lifecycle (card P-10b).

open_cycle opens the next cycle for a project and emits the phase event.
close_cycle performs the I3 gate check in the service BEFORE the data
call is reached: the gate must belong to the project and carry a
recorded outcome (non-PLANNED). Only then is data.close_cycle called.

Every mutation runs inside DataKit.tx(...) (C3.1).
"""

from __future__ import annotations

from typing import Any

from core import (
    CoreError,
    EventKind,
    GateMissing,
    GateOutcome,
    ServiceError,
)
from data import DataKit, CycleRow


class PhaseSVC:
    """Phase lifecycle service (C3.1 phase section).

    Receives its DataKit via the ServiceKit — no global state, no
    module-level DB handles.
    """

    def __init__(self, workspace_root: str) -> None:
        self._root = workspace_root
        self._data: DataKit | None = None

    def __getattr__(self, name: str) -> Any:
        """Raise CoreError for unknown attributes (matches the
        _Placeholder behavior from P-10a-i)."""
        if name.startswith("_"):
            raise AttributeError(name)
        raise CoreError(
            f"services slot 'phase_svc' has no attribute '{name}'"
        )

    def _ensure_data(self) -> DataKit:
        """Lazily create the DataKit on first use (avoids opening the
        database in __init__, which would break ServiceKit tests that
        use non-existent paths)."""
        if self._data is None:
            from data.migrate import migrate

            db_path = f"{self._root}/app.db"
            migrate(db_path)
            self._data = DataKit(db_path)
        return self._data

    def open_cycle(self, project_code: str, name: str) -> CycleRow:
        """Open a new cycle for the project and emit the phase event.

        Only one open cycle per project: a second open while one is
        already open raises ServiceError with code 'cycle_open' (frozen
        rule: close the old one first — the loop does not overlap for
        v1).

        Raises: UnknownProjectData (via data layer) if the project code
        is unknown; ServiceError (code 'cycle_open') if a cycle is
        already open.
        """
        data = self._ensure_data()

        def _open(conn: Any) -> CycleRow:
            # Frozen rule: only one open cycle per project.
            current = data.cycles.current_for(project_code)
            if current is not None:
                raise ServiceError(
                    f"project '{project_code}' already has an open cycle "
                    f"({current.name!r}) — close it first",
                    code="cycle_open",
                )
            cycle = data.cycles.open(project_code, name)
            data.events.emit(
                project_code,
                EventKind.PHASE,
                f"Cycle opened: {name}",
                ref_table="cycle",
                ref_id=cycle.id,
            )
            return cycle

        return data.tx(_open)

    def close_cycle(self, project_code: str, gate_id: int) -> CycleRow:
        """Close the current open cycle against a recorded gate.

        I3 (service side, BEFORE the data call): the gate must belong
        to the project and its outcome must be recorded (non-PLANNED).
        The data layer then closes the cycle and emits the GATE event.

        Raises: UnknownProjectData (via data layer) if the project code
        is unknown; CycleCloseError (code 'cycle_close') if no cycle is
        open; GateMissing (code 'gate_missing') if the gate is unknown,
        belongs to another project, or has no recorded outcome.
        """
        data = self._ensure_data()

        # I3 guard — runs BEFORE data.close_cycle is reached.
        cycle = data.cycles.current_for(project_code)
        if cycle is None:
            raise ServiceError(
                f"project '{project_code}' has no open cycle to close",
                code="cycle_close",
            )
        gate = data.gates.get(gate_id)
        if gate.project_code != project_code:
            raise GateMissing(
                f"gate {gate_id} belongs to project "
                f"'{gate.project_code}', not '{project_code}'"
            )
        if gate.outcome == GateOutcome.PLANNED.value:
            raise GateMissing(
                f"gate {gate_id} has no recorded outcome — "
                "record it before closing the cycle"
            )

        def _close(conn: Any) -> CycleRow:
            return data.cycles.close_cycle(cycle.id, gate_id)

        return data.tx(_close)
