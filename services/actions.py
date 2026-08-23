"""services.actions — actions, priorities and engagement (card P-11, I4).

add_action normalises the owner through the core Owner value object and
delegates to the data layer (which emits the ACTION_CREATED event).
add_priority auto-assigns P1..Pn in insertion order; set_priority stores
the given value verbatim — positions are NOT rebalanced (manual is
manual, by contract). change_status delegates the state machine and the
I4 reopen signal to the data layer (the transition map is imported from
core, never re-implemented). add_signal accepts every SignalKind and
emits the SIGNAL event; note_late_start emits a LATE_START signal for an
action not in_progress by its due date.

Every mutation runs inside DataKit.tx(...) (C3.1).
"""

from __future__ import annotations

from typing import Any

from core import (
    ActionStatus,
    CoreError,
    EventKind,
    Owner,
    ServiceError,
    SignalKind,
)
from core.time import now_utc
from data import ActionRow, DataKit
from data.rows import SignalRow
from data.signals import SignalRepo

#: Priority assigned to the Nth auto-prioritised action (P1, P2, ...).
_AUTO_PRIORITY_BASE = 1


def _next_auto_priority(existing: list[ActionRow]) -> int:
    """P1..Pn in insertion order: 1 + count of actions already carrying
    an auto-assigned priority (1..n). Manual priorities never collide
    with the auto sequence because they are stored verbatim."""
    auto = [r.priority for r in existing if 1 <= r.priority <= len(existing)]
    return _AUTO_PRIORITY_BASE + len(auto)


class ActionsSVC:
    """Actions, priorities and engagement signals (C3.1 actions section).

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
            f"services slot 'actions_svc' has no attribute '{name}'"
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

    def _signals(self) -> SignalRepo:
        """Get the SignalRepo (not exposed on DataKit, so we create it
        on demand)."""
        data = self._ensure_data()
        return SignalRepo(data)

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
        """Create an action for the project.

        The owner is normalised through the core Owner value object
        ("  ana " is stored as "ana"). Priority defaults to 9. The
        ACTION_CREATED event is emitted by the data layer.

        cycle_id defaults to the current open cycle (C3.3).

        Raises: UnknownProjectData (via data layer) if the project code
        is unknown.
        """
        data = self._ensure_data()
        owner_name = Owner(owner).name

        def _create(conn: Any) -> ActionRow:
            # cycle_id defaults to the current open cycle (C3.3).
            cid = cycle_id
            if cid is None:
                current = data.cycles.current_for(project_code)
                cid = current.id if current is not None else None
            row = data.actions.create(
                project_code,
                title,
                owner_name,
                description=description,
                priority=priority,
                due_start=due_start,
                due_end=due_end,
            )
            # Attach the action to the cycle (best effort — the data
            # layer owns the cycle_item bookkeeping).
            if cid is not None:
                data.conn.execute(
                    "INSERT INTO cycle_item (cycle_id, project_code, "
                    "action_id, rank, created_at) "
                    "SELECT ?, ?, ?, COALESCE(MAX(rank), 0) + 1, ? "
                    "FROM cycle_item WHERE cycle_id = ?",
                    (cid, project_code, row.id, _ts(), cid),
                )
            return row

        return data.tx(_create)

    def add_priority(self, project_code: str, action_id: int) -> ActionRow:
        """Auto-assign the next priority (P1, P2, P3, ...) to an existing
        action, in insertion order.

        The value is stored verbatim; positions are NOT rebalanced —
        manual is manual, by contract.

        Raises: CoreError (via data layer) if the action id is unknown.
        """
        data = self._ensure_data()

        def _assign(conn: Any) -> ActionRow:
            action = data.actions.get(action_id)
            if action.project_code != project_code:
                raise ServiceError(
                    f"action {action_id} belongs to project "
                    f"'{action.project_code}', not '{project_code}'",
                    code="action_project_mismatch",
                )
            existing = data.actions.list_for(project_code)
            priority = _next_auto_priority(existing)
            data.conn.execute(
                "UPDATE action SET priority = ?, updated_at = ? WHERE id = ?",
                (priority, _ts(), action_id),
            )
            return data.actions.get(action_id)

        return data.tx(_assign)

    def set_priority(self, project_code: str, action_id: int,
                     priority: int) -> ActionRow:
        """Store the given priority verbatim on an existing action.

        Positions are NOT rebalanced — manual is manual, by contract.

        Raises: CoreError (via data layer) if the action id is unknown.
        """
        data = self._ensure_data()

        def _set(conn: Any) -> ActionRow:
            action = data.actions.get(action_id)
            if action.project_code != project_code:
                raise ServiceError(
                    f"action {action_id} belongs to project "
                    f"'{action.project_code}', not '{project_code}'",
                    code="action_project_mismatch",
                )
            data.conn.execute(
                "UPDATE action SET priority = ?, updated_at = ? WHERE id = ?",
                (priority, _ts(), action_id),
            )
            return data.actions.get(action_id)

        return data.tx(_set)

    def change_status(self, project_code: str, action_id: int,
                      new: ActionStatus) -> ActionRow:
        """Change the status of an action through the frozen state
        machine (ALLOWED_ACTION_TRANSITIONS, imported from core — never
        re-implemented here).

        I4 lives in the data layer: a done->open arrival increments
        reopen_count and emits the REOPEN signal + SIGNAL event.

        Raises: CoreError (code 'illegal_transition') for any pair not
        in the frozen map; CoreError (via data layer) if the action id
        is unknown.
        """
        data = self._ensure_data()

        def _change(conn: Any) -> ActionRow:
            action = data.actions.get(action_id)
            if action.project_code != project_code:
                raise ServiceError(
                    f"action {action_id} belongs to project "
                    f"'{action.project_code}', not '{project_code}'",
                    code="action_project_mismatch",
                )
            return data.actions.set_status(action_id, new)

        return data.tx(_change)

    def add_signal(self, project_code: str, kind: SignalKind, owner: str,
                   action_id: int | None = None,
                   note: str = "") -> SignalRow:
        """Record an engagement signal of any SignalKind (DEFER,
        EXTENSION_REQUEST, LATE_START, REOPEN) and emit the SIGNAL event.

        The event summary uses the frozen '#<id>' format when an action
        is named.

        Raises: UnknownProjectData (via data layer) if the project code
        is unknown.
        """
        data = self._ensure_data()
        owner_name = Owner(owner).name
        signals = self._signals()

        def _record(conn: Any) -> SignalRow:
            signal_id = signals.insert(
                kind, project_code, owner_name, action_id=action_id,
                note=note,
            )
            if action_id is not None:
                summary = f"Signal {kind.value}: Action #{action_id}"
            else:
                summary = f"Signal {kind.value}"
            data.events.emit(
                project_code,
                EventKind.SIGNAL,
                summary,
                ref_table="signals",
                ref_id=signal_id,
                body=note or None,
            )
            return signals.list_for(project_code)[-1]

        return data.tx(_record)

    def note_late_start(self, project_code: str,
                        action_id: int) -> SignalRow:
        """Emit a LATE_START signal for an action not in_progress by its
        due date, plus its SIGNAL event.

        The owner is taken from the action row (the PM is the one
        logging the late start on behalf of the owner).

        Raises: CoreError (via data layer) if the action id is unknown.
        """
        data = self._ensure_data()

        def _note(conn: Any) -> SignalRow:
            action = data.actions.get(action_id)
            if action.project_code != project_code:
                raise ServiceError(
                    f"action {action_id} belongs to project "
                    f"'{action.project_code}', not '{project_code}'",
                    code="action_project_mismatch",
                )
            return self.add_signal(
                project_code,
                SignalKind.LATE_START,
                action.owner,
                action_id=action_id,
                note=f"Action #{action_id} not in_progress by its due date",
            )

        return data.tx(_note)


def _ts() -> str:
    """UTC timestamp for the cycle_item.created_at column."""
    return now_utc().isoformat()
