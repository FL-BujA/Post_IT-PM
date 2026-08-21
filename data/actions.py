"""data.actions — ActionRepo (contract C2.2, card P-08).

The action state machine over the shared ``DataKit`` connection
(frozen rule C2.1: ONE connection per workspace).  Invariant I4 lives
here: a ``done -> open`` transition increments ``reopen_count``, stamps
``last_reopened_at`` and auto-emits the reopen signal (an
``engagement_signals`` row of kind ``reopen``).

Semantics, frozen by the P-08 card:

- ``create`` inserts an ``action`` row with the frozen defaults
  (``priority 9``, ``status open``, ``reopen_count 0``) and emits the
  ``ACTION_CREATED`` event (``ref_table='actions'``, ``ref_id`` = the
  action's id).
- ``set_status`` enforces the frozen map
  ``core.enums.ALLOWED_ACTION_TRANSITIONS``: every listed transition is
  accepted, every other pair raises ``CoreError`` with code
  ``illegal_transition``.  Each accepted transition emits an
  ``ACTION_STATUS`` event.
- ``started_at`` is stamped on the FIRST arrival at ``in_progress``
  (from ``open`` or ``done``) and never touched on later re-entries.
- ``closed_at`` is stamped exactly on arrivals at ``done``,
  ``deferred`` or ``cancelled`` and cleared on every arrival at
  ``open`` or ``in_progress`` (so it is NULL while the action is open).
- I4: ``done -> open`` increments ``reopen_count``, sets
  ``last_reopened_at`` and inserts one ``engagement_signals`` row of
  kind ``reopen`` for the action (named test
  ``test_i4_reopen_emits_signal``).

Note: the frozen schema (C2.4, card P-05) does not carry the
``started_at`` / ``last_reopened_at`` columns the C2.0 sketch names;
this repo adds them idempotently (``ALTER TABLE ... ADD COLUMN``) so
the card's done-when assertions hold against the real table.
"""

from __future__ import annotations

import sqlite3
from typing import Protocol

from core.enums import ALLOWED_ACTION_TRANSITIONS, ActionStatus, EventKind
from core.errors import CoreError, UnknownProjectData
from core.time import now_utc
from data.rows import ActionRow, EventRow

__all__ = ["ActionRepo"]

#: Frozen error code (C2.2): a transition outside the frozen map.
ILLEGAL_TRANSITION_CODE = "illegal_transition"

#: Arrivals that stamp ``closed_at`` (frozen, P-08).
_CLOSING_STATUSES = frozenset(
    {ActionStatus.DONE, ActionStatus.DEFERRED, ActionStatus.CANCELLED}
)

#: Arrivals that clear ``closed_at`` (open / in_progress).
_OPENING_STATUSES = frozenset(
    {ActionStatus.OPEN, ActionStatus.IN_PROGRESS}
)


class _KitLike(Protocol):
    """The minimal ``DataKit`` surface a repo needs (avoids the import
    cycle ``data.db -> data.actions``)."""

    conn: sqlite3.Connection

    events: object  # EventRepo on the same DataKit

    def tx(self, fn: object) -> object: ...


def _ts() -> str:
    return now_utc().isoformat()


def _ensure_columns(conn: sqlite3.Connection) -> None:
    """Idempotently add the P-08 columns the frozen schema lacks.

    Tolerates a connection whose schema has not been created yet
    (``DataKit`` may be constructed on a fresh file before
    ``data.migrate`` runs — the P-06 pragma test does exactly that).
    """
    try:
        table_exists = conn.execute(
            "SELECT 1 FROM sqlite_master WHERE type = 'table' AND name = 'action'"
        ).fetchone()
        if table_exists is None:
            return  # no action table yet — migrate() will create it
        existing = {
            row[1]
            for row in conn.execute("PRAGMA table_info(action)").fetchall()
        }
    except sqlite3.OperationalError:
        return  # no action table yet — migrate() will create it
    if "started_at" not in existing:
        conn.execute("ALTER TABLE action ADD COLUMN started_at TEXT")
    if "last_reopened_at" not in existing:
        conn.execute("ALTER TABLE action ADD COLUMN last_reopened_at TEXT")
    if "closed_at" not in existing:
        conn.execute("ALTER TABLE action ADD COLUMN closed_at TEXT")
    # I4 needs the engagement_signals table (C2.0 names it; the frozen
    # C2.4 DDL does not create it).  Created idempotently here.
    conn.execute(
        "CREATE TABLE IF NOT EXISTS engagement_signals ("
        "id INTEGER PRIMARY KEY, "
        "project_code TEXT NOT NULL REFERENCES project(code), "
        "owner TEXT NOT NULL, "
        "kind TEXT NOT NULL, "
        "action_id INTEGER REFERENCES action(id), "
        "occurred_at TEXT NOT NULL, "
        "note TEXT, "
        "resolved INTEGER NOT NULL DEFAULT 0, "
        "resolved_at TEXT"
        ")"
    )
    conn.execute(
        "CREATE INDEX IF NOT EXISTS idx_engagement_signals_project_owner "
        "ON engagement_signals(project_code, owner)"
    )


class ActionRepo:
    """CRUD + state machine over the ``action`` table; I4 enforced here."""

    def __init__(self, kit: _KitLike) -> None:
        self._kit = kit
        self._conn: sqlite3.Connection = kit.conn
        _ensure_columns(self._conn)

    # ------------------------------------------------------------------
    # create / get / list
    # ------------------------------------------------------------------

    def create(
        self,
        project_code: str,
        title: str,
        owner: str,
        *,
        description: str = "",
        priority: int = 9,
        due_start: str | None = None,
        due_end: str | None = None,
    ) -> ActionRow:
        """Insert a new action and emit the ``ACTION_CREATED`` event.

        Frozen defaults (P-08): ``priority 9``, ``status open``,
        ``reopen_count 0``.  An unknown project code raises
        ``UnknownProjectData``.
        """
        self._require_project(project_code)
        ts = _ts()
        event: EventRow = self._kit.events.emit(  # type: ignore[attr-defined]
            project_code,
            EventKind.ACTION_CREATED,
            f"Action created: {title}",
            ref_table="actions",
            ref_id=0,
            body=description or None,
        )
        row = ActionRow(
            id=0,  # auto-assigned; filled in below
            project_code=project_code,
            description=title,
            owner=owner,
            priority=priority,
            due=due_end,
            status=ActionStatus.OPEN.value,
            event_id=event.id,
            reopen_count=0,
            created_at=ts,
            updated_at=ts,
        )
        d = row.to_dict()
        new_id = self._kit.tx(
            lambda conn: (
                conn.execute(
                    "INSERT INTO action "
                    "(project_code, description, owner, priority, due, "
                    "status, event_id, reopen_count, created_at, updated_at) "
                    "VALUES (:project_code, :description, :owner, :priority, "
                    ":due, :status, :event_id, :reopen_count, :created_at, "
                    ":updated_at)",
                    d,
                ).lastrowid
            )
        )
        row.id = int(new_id)
        # Backfill the action id into the timeline event (ref actions/id).
        self._conn.execute(
            "UPDATE event SET ref_id = ? WHERE id = ?", (row.id, event.id)
        )
        self._conn.commit()
        return row

    def get(self, action_id: int) -> ActionRow:
        """Fetch an action by id; unknown id raises ``CoreError`` with
        code ``action_unknown``."""
        row = self._conn.execute(
            "SELECT id, project_code, description, owner, priority, due, "
            "status, event_id, reopen_count, created_at, updated_at "
            "FROM action WHERE id = ?",
            (action_id,),
        ).fetchone()
        if row is None:
            raise CoreError(
                f"no action with id {action_id!r}", code="action_unknown"
            )
        return ActionRow(*row)

    def list_for(
        self, project_code: str, cycle_id: int | None = None
    ) -> list[ActionRow]:
        """Actions of a project in ascending id order (P-08).

        ``cycle_id`` is accepted for the C2.2 signature; the frozen
        schema has no cycle link on actions, so the filter is a no-op.
        """
        rows = self._conn.execute(
            "SELECT id, project_code, description, owner, priority, due, "
            "status, event_id, reopen_count, created_at, updated_at "
            "FROM action WHERE project_code = ? ORDER BY id ASC",
            (project_code,),
        ).fetchall()
        return [ActionRow(*row) for row in rows]

    # ------------------------------------------------------------------
    # state machine (I4 lives here)
    # ------------------------------------------------------------------

    def set_status(self, action_id: int, new: ActionStatus | str) -> ActionRow:
        """Move an action along the frozen state machine (C2.2).

        Every transition in ``ALLOWED_ACTION_TRANSITIONS`` is accepted;
        every other pair raises ``CoreError`` with code
        ``illegal_transition``.  On success an ``ACTION_STATUS`` event
        is emitted and the row returned.

        Frozen side effects (P-08):
        - ``started_at`` stamped on the FIRST arrival at
          ``in_progress`` (from ``open`` or ``done``); later
          re-entries leave it untouched.
        - ``closed_at`` stamped exactly on arrivals at ``done``,
          ``deferred`` or ``cancelled``; cleared on arrivals at
          ``open`` / ``in_progress`` (NULL while the action is open).
        - I4: ``done -> open`` increments ``reopen_count``, stamps
          ``last_reopened_at`` and inserts one ``engagement_signals``
          row of kind ``reopen`` for the action.
        """
        if isinstance(new, ActionStatus):
            target = new
        else:
            try:
                target = ActionStatus(new)
            except ValueError as exc:
                raise CoreError(
                    f"invalid action status {new!r}", code="invalid_status"
                ) from exc

        action = self.get(action_id)
        current = ActionStatus(action.status)
        if target not in ALLOWED_ACTION_TRANSITIONS[current]:
            raise CoreError(
                f"illegal transition {current.value} -> {target.value} "
                f"for action {action_id!r}",
                code=ILLEGAL_TRANSITION_CODE,
            )

        ts = _ts()
        reopen = current is ActionStatus.DONE and target is ActionStatus.OPEN
        started_at = self._conn.execute(
            "SELECT started_at FROM action WHERE id = ?", (action_id,)
        ).fetchone()[0]
        first_in_progress = (
            target is ActionStatus.IN_PROGRESS and started_at is None
        )

        self._kit.tx(
            lambda conn: conn.execute(
                "UPDATE action SET status = ?, updated_at = ?, "
                "reopen_count = ?, last_reopened_at = ?, started_at = ?, "
                "closed_at = ? WHERE id = ?",
                (
                    target.value,
                    ts,
                    action.reopen_count + (1 if reopen else 0),
                    ts if reopen else None,
                    ts if first_in_progress else started_at,
                    ts if target in _CLOSING_STATUSES else None,
                    action_id,
                ),
            )
        )

        # I4: the reopen signal row (engagement_signals, kind 'reopen').
        if reopen:
            self._conn.execute(
                "INSERT INTO engagement_signals "
                "(project_code, owner, kind, action_id, occurred_at, note) "
                "VALUES (?, ?, 'reopen', ?, ?, 'auto-emitted by I4')",
                (action.project_code, action.owner, action_id, ts),
            )
            self._conn.commit()

        self._kit.events.emit(  # type: ignore[attr-defined]
            action.project_code,
            EventKind.ACTION_STATUS,
            f"Action status: {action.description} -> {target.value}",
            ref_table="actions",
            ref_id=action_id,
            body=f"from {current.value} to {target.value}",
        )
        self._conn.commit()
        return self.get(action_id)

    # ------------------------------------------------------------------
    # helpers
    # ------------------------------------------------------------------

    def _require_project(self, project_code: str) -> None:
        if self._conn.execute(
            "SELECT 1 FROM project WHERE code = ?", (project_code,)
        ).fetchone() is None:
            raise UnknownProjectData(f"no project with code {project_code!r}")
