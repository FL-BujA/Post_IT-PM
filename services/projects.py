"""services.projects — project lifecycle (card P-10a-ii).

create_project is the signature acceptance: one call builds the entire
project world (project row, charter event, first open cycle, workspace
directories, root manifest). update_project persists name/target/
prepared_for and emits an UPDATE event naming the changed field.

Every mutation runs inside DataKit.tx(...) (C3.1).
"""

from __future__ import annotations

import json
import os
from typing import Any

from core import (
    CoreError,
    EventKind,
    ProjectStatus,
    ServiceError,
)
from data import DataKit, ProjectRow
from data.migrate import migrate
from data.projects import _ts

#: Workspace subdirectories created by create_project (frozen set).
WORKSPACE_DIRS = ("evidence", "reports", "backups")

#: Root manifest filename (frozen).
MANIFEST_NAME = "manifest.json"


def _next_code(existing: list[ProjectRow]) -> str:
    """Allocate the next free project code: max existing + 1, P%03d."""
    max_n = 0
    for row in existing:
        code = row.code
        if code.startswith("P") and code[1:].isdigit():
            max_n = max(max_n, int(code[1:]))
    return f"P{max_n + 1:03d}"


def _write_manifest(workspace_root: str, codes: list[str]) -> None:
    """Write the root manifest.json with the current project codes."""
    manifest = {"projects": codes}
    path = os.path.join(workspace_root, MANIFEST_NAME)
    with open(path, "w", encoding="utf-8") as fh:
        json.dump(manifest, fh, indent=2)
        fh.write("\n")


class ProjectSVC:
    """Project lifecycle service (C3.1 project section).

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
            f"services slot 'project_svc' has no attribute '{name}'"
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

    def create_project(
        self,
        name: str,
        target_date: str,
        sponsor: str = "TBD",
        objective: str = "",
        charter_text: str = "",
        constraints_text: str = "",
    ) -> ProjectRow:
        """Allocate the next code, create the project row, emit the
        charter event, open the first cycle, create workspace directories,
        and write the root manifest — all in ONE transaction.

        Raises: ServiceError (code 'project_exists') if the name is
        already used by an existing project.
        """
        # Validate name uniqueness BEFORE the transaction.
        data = self._ensure_data()
        existing = data.projects.list()
        for row in existing:
            if row.name == name:
                raise ServiceError(
                    f"project '{name}' already exists",
                    code="project_exists",
                )

        code = _next_code(existing)

        def _build(conn: Any) -> ProjectRow:
            # 1. Project row (status CHARTER).
            project = data.projects.create(
                code,
                name,
                status=ProjectStatus.CHARTER,
                charter=charter_text or None,
                target=objective or None,
                target_date=target_date or None,
                sponsor=sponsor if sponsor and sponsor != "TBD" else None,
            )
            # 2. Charter event (kind CHARTER, ref_table None).
            data.events.emit(
                code,
                EventKind.CHARTER,
                f"Charter drafted: {name}",
                ref_table=None,
                ref_id=None,
                body=charter_text or None,
            )
            # 3. First open cycle named 'Charter cycle'.
            data.cycles.open(code, "Charter cycle")
            return project

        project = data.tx(_build)

        # 4. Workspace directories (outside the DB transaction).
        for d in WORKSPACE_DIRS:
            os.makedirs(os.path.join(self._root, d), exist_ok=True)

        # 5. Root manifest.json with all project codes.
        all_codes = [row.code for row in data.projects.list()]
        _write_manifest(self._root, all_codes)

        return project

    def update_project(
        self,
        code: str,
        name: str | None = None,
        target: str | None = None,
        prepared_for: str | None = None,
    ) -> ProjectRow:
        """Persist name, target, and/or prepared_for for an existing
        project. Each changed field emits an UPDATE event naming the
        field in the summary.

        Raises: CoreError (via data layer) if the project code is unknown.
        """
        # Determine which fields are being changed.
        changed: list[str] = []
        if name is not None:
            changed.append("name")
        if target is not None:
            changed.append("target")
        if prepared_for is not None:
            changed.append("prepared_for")

        if not changed:
            raise ServiceError(
                "no fields to update",
                code="no_fields",
            )

        data = self._ensure_data()

        def _update(conn: Any) -> ProjectRow:
            # Fetch the current row (raises if unknown).
            current = data.projects.get(code)

            # Build the updated row using direct SQL UPDATE.
            new_name = name if name is not None else current.name
            new_target = target if target is not None else current.target
            new_sponsor = (
                prepared_for if prepared_for is not None else current.sponsor
            )

            conn.execute(
                "UPDATE project SET name = ?, target = ?, sponsor = ?, "
                "updated_at = ? WHERE code = ?",
                (new_name, new_target, new_sponsor, _ts(), code),
            )

            # Re-fetch the updated row.
            updated = data.projects.get(code)

            # Emit an UPDATE event for each changed field.
            for field in changed:
                data.events.emit(
                    code,
                    EventKind.NOTE,
                    f"Project updated: {field}",
                    ref_table="projects",
                    ref_id=None,
                    body=None,
                )

            return updated

        return data.tx(_update)
