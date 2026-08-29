"""services.handover — HandoverService (card A-08).

C3.8: the "Documentation and handover" artifact. One zip per project,
readable without the tool: the rows as JSON, the story as markdown, the
files themselves, and a manifest with a sha256 for every entry.

Scope flow: Project delivery -> Documentation and handover -> Finished.
"""

from __future__ import annotations

import json
import os
import zipfile
from datetime import datetime, timezone
from typing import Any

from core import CoreError
from core.hash import sha256_file
from data import DataKit
from data.migrate import SCHEMA_VERSION, migrate

#: Trees copied into the zip, relative to the workspace root.
HANDOVER_TREES = ("evidence", "reports")

#: Entry names inside the zip.
DB_SLICE_NAME = "db_slice.json"
STORY_NAME = "story.md"
MANIFEST_NAME = "manifest.json"

#: Signal kinds that count as unresolved escalation in the story.
_UNRESOLVED_HEADING = "Unresolved signals"


class HandoverService:
    """C3.8 HandoverService — one project, one zip, no tool required."""

    def __init__(self, workspace_root: str) -> None:
        self._root = workspace_root
        self._data: DataKit | None = None

    def __getattr__(self, name: str) -> Any:
        if name.startswith("_"):
            raise AttributeError(name)
        raise CoreError(
            f"services slot 'handover' has no attribute '{name}'"
        )

    def _ensure_data(self) -> DataKit:
        if self._data is None:
            db_path = os.path.join(self._root, "app.db")
            migrate(db_path)
            self._data = DataKit(db_path)
        return self._data

    # -- pieces ------------------------------------------------------------

    def _db_slice(self, project_code: str) -> dict[str, list[dict[str, Any]]]:
        """Every row belonging to this project, as dicts.

        created_at-first key order per C3.8 is provided by each row's
        to_dict(), which follows the table's column order.
        """
        kit = self._ensure_data()
        project = kit.projects.get(project_code)   # raises if unknown

        cycles = []
        current = kit.cycles.current_for(project_code)
        if current is not None:
            cycles.append(current.to_dict())

        return {
            "projects": [project.to_dict()],
            "events": [r.to_dict() for r in kit.events.list_for(project_code)],
            "cycles": cycles,
            "gates": [r.to_dict() for r in kit.gates.list_for(project_code)],
            "actions": [r.to_dict() for r in kit.actions.list_for(project_code)],
            "evidence": [
                r.to_dict() for r in kit.evidence.list_for(project_code)
            ],
            "minutes": [r.to_dict() for r in kit.minutes.list_for(project_code)],
            "signals": [r.to_dict() for r in kit.signals.list_for(project_code)],
            "report_history": [
                r.to_dict() for r in kit.reports.list_for(project_code)
            ],
        }

    def _story(self, project_code: str) -> str:
        """The project's timeline as markdown, plus the three sections
        C3.8 names: open actions, unresolved signals, gate history."""
        kit = self._ensure_data()
        project = kit.projects.get(project_code)

        lines: list[str] = [
            f"# {project.name} ({project.code})",
            "",
            f"Status: {project.status}",
            f"Exported: {datetime.now(tz=timezone.utc).isoformat()}",
            "",
            "## Timeline",
            "",
        ]

        events = sorted(
            kit.events.list_for(project_code), key=lambda e: e.occurred_at
        )
        for ev in events:
            day = ev.occurred_at[:10]
            summary = f" — {ev.body}" if ev.body else ""
            lines.append(f"- [{day}] ({ev.kind}) {ev.title}{summary}")
        if not events:
            lines.append("- (no events)")

        lines += ["", "## Open actions", ""]
        open_actions = [
            a
            for a in kit.actions.list_for(project_code)
            if str(a.status) in ("open", "in_progress")
        ]
        for a in sorted(open_actions, key=lambda a: a.priority):
            reopened = (
                f" (reopened {a.reopen_count}x)" if a.reopen_count else ""
            )
            lines.append(
                f"- P{a.priority} {a.description} — {a.owner}{reopened}"
            )
        if not open_actions:
            lines.append("- (none)")

        lines += ["", f"## {_UNRESOLVED_HEADING}", ""]
        unresolved = [
            s for s in kit.signals.list_for(project_code) if not s.resolved
        ]
        for s in unresolved:
            note = f" — {s.note}" if s.note else ""
            lines.append(f"- [{s.occurred_at[:10]}] {s.kind} · {s.owner}{note}")
        if not unresolved:
            lines.append("- (none)")

        lines += ["", "## Gate history", ""]
        gates = kit.gates.list_for(project_code)
        for g in gates:
            planned = g.planned_date or "—"
            actual = g.actual_date or "—"
            lines.append(
                f"- {g.name}: {g.outcome} (planned {planned}, actual {actual})"
            )
        if not gates:
            lines.append("- (none)")

        # C3.8: the evidence sha256 appendix, so a reader can verify the
        # files without the tool.
        lines += ["", "## Evidence appendix", "", "| rel_path | sha256 |",
                  "| --- | --- |"]
        rows = kit.evidence.list_for(project_code)
        for row in rows:
            lines.append(f"| {row.rel_path} | {row.sha256} |")
        if not rows:
            lines.append("| (none) | |")

        return "\n".join(lines) + "\n"

    # -- C3.8 --------------------------------------------------------------

    def export(self, project_code: str, dest_dir: str) -> str:
        """Build <dest_dir>/<code>_handover.zip and return its path.

        Raises UnknownProjectData (via the data layer) for an unknown code.
        """
        db_slice = self._db_slice(project_code)      # raises if unknown
        story = self._story(project_code)

        os.makedirs(dest_dir, exist_ok=True)
        zip_path = os.path.join(dest_dir, f"{project_code}_handover.zip")

        entries: list[dict[str, Any]] = []

        with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED) as zf:
            slice_text = json.dumps(db_slice, indent=2, sort_keys=False)
            zf.writestr(DB_SLICE_NAME, slice_text)
            entries.append(
                {"rel_path": DB_SLICE_NAME, "size": len(slice_text.encode())}
            )

            zf.writestr(STORY_NAME, story)
            entries.append(
                {"rel_path": STORY_NAME, "size": len(story.encode())}
            )

            for tree in HANDOVER_TREES:
                base = os.path.join(self._root, tree, project_code)
                if not os.path.isdir(base):
                    continue
                for dirpath, _dirs, files in os.walk(base):
                    for name in sorted(files):
                        abs_path = os.path.join(dirpath, name)
                        rel = os.path.relpath(
                            abs_path, self._root
                        ).replace("\\", "/")
                        zf.write(abs_path, rel)
                        entries.append(
                            {
                                "rel_path": rel,
                                "size": os.path.getsize(abs_path),
                                "sha256": sha256_file(abs_path),
                            }
                        )

            manifest = {
                "exported_at": datetime.now(tz=timezone.utc).isoformat(),
                "project_code": project_code,
                "schema_version": SCHEMA_VERSION,
                "file_count": len(entries),
                "files": sorted(entries, key=lambda e: e["rel_path"]),
            }
            zf.writestr(
                MANIFEST_NAME, json.dumps(manifest, indent=2, sort_keys=True)
            )

        return zip_path
