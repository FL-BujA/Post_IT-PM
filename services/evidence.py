"""services.evidence — EvidenceService (card A-05).

C3.2: attach a file from anywhere on disk into the project's evidence
folder, hand back the row, and let the caller find the file again.

The frozen guarantees from C3.2 that this module owns:
  - the destination name is core.slugify(<source stem>, <source mtime date>,
    <source extension>)
  - a collision appends _2, _3 ... BEFORE the file is stored
  - the stored rel_path is what the row carries: the row is always the
    truth of where the file is
"""

from __future__ import annotations

import os
import shutil
from datetime import datetime, timezone
from typing import Any

from core import (
    CoreError,
    MissingFileError,
    PathEscape,
    SourceType,
)
from core.hash import sha256_file, short_id
from core.paths import slugify
from data import DataKit, EvidenceRow
from data.migrate import migrate

#: The directory, relative to the workspace root, that holds attachments.
EVIDENCE_DIR = "evidence"

#: Event kind emitted on a successful attach. EvidenceRepo.record does NOT
#: emit — this service does.
EVIDENCE_EVENT_KIND = "EVIDENCE"


class EvidenceService:
    """C3.2 EvidenceService — the glue: file in, row and event out."""

    def __init__(self, workspace_root: str) -> None:
        self._root = workspace_root
        self._data: DataKit | None = None

    def __getattr__(self, name: str) -> Any:
        if name.startswith("_"):
            raise AttributeError(name)
        raise CoreError(
            f"services slot 'evidence' has no attribute '{name}'"
        )

    def _ensure_data(self) -> DataKit:
        """Lazily open the database, matching FlowService."""
        if self._data is None:
            db_path = os.path.join(self._root, "app.db")
            migrate(db_path)
            self._data = DataKit(db_path)
        return self._data

    # -- helpers -----------------------------------------------------------

    def _require_project(self, project_code: str) -> None:
        """Raise UnknownProjectData if the project does not exist.

        ProjectRepo.get raises it; calling it is the check.
        """
        self._ensure_data().projects.get(project_code)

    def _destination(self, project_code: str, source_path: str) -> tuple[str, str]:
        """Return (rel_path, abs_path) for a source file, with collision
        suffixing applied BEFORE anything is written.

        The date comes from the SOURCE file's mtime, per C3.2.
        """
        stat = os.stat(source_path)
        date = datetime.fromtimestamp(stat.st_mtime, tz=timezone.utc).strftime(
            "%Y-%m-%d"
        )
        base = os.path.basename(source_path)
        stem, ext = os.path.splitext(base)
        ext = ext.lstrip(".")

        name = slugify(stem, date, ext)          # raises InvalidSlug
        project_dir = os.path.join(self._root, EVIDENCE_DIR, project_code)
        os.makedirs(project_dir, exist_ok=True)

        candidate = name
        counter = 1
        while os.path.exists(os.path.join(project_dir, candidate)):
            counter += 1
            root, dot, suffix = name.rpartition(".")
            if dot:
                candidate = f"{root}_{counter}.{suffix}"
            else:
                candidate = f"{name}_{counter}"

        rel_path = f"{EVIDENCE_DIR}/{project_code}/{candidate}"
        return rel_path, os.path.join(project_dir, candidate)

    # -- C3.2 --------------------------------------------------------------

    def attach(
        self,
        project_code: str,
        source_path: str,
        source_type: SourceType,
        note: str = "",
    ) -> EvidenceRow:
        """Copy source_path into evidence/<code>/<date>_<slug>.<ext>,
        compute sha256, persist the glue row, emit the EVIDENCE event.

        Raises before anything is copied or written:
          UnknownProjectData  the project does not exist
          MissingFileError    source_path is unreadable
          InvalidSlug         the source name cannot be slugified
        Raises after the copy is prepared but before the row is kept:
          EvidenceConflict    rel_path is already recorded

        No size cap is enforced (C3.2: a large file must never raise).
        """
        self._require_project(project_code)

        if not os.path.isfile(source_path):
            raise MissingFileError(f"source file not readable: {source_path!r}")

        rel_path, abs_path = self._destination(project_code, source_path)

        kit = self._ensure_data()
        row = EvidenceRow(
            id=short_id(),
            project_code=project_code,
            ref_table=None,
            ref_id=None,
            original_name=os.path.basename(source_path),
            source_type=str(
                source_type.value if hasattr(source_type, "value") else source_type
            ),
            rel_path=rel_path,
            size_bytes=os.path.getsize(source_path),
            sha256="",
            attached_at=datetime.now(tz=timezone.utc).isoformat(),
        )

        shutil.copy2(source_path, abs_path)
        try:
            row = EvidenceRow(**{**row.to_dict(), "sha256": sha256_file(abs_path)})
            stored = kit.evidence.record(row)
        except Exception:
            # never leave a file behind for a row that was not kept
            if os.path.exists(abs_path):
                os.remove(abs_path)
            raise

        kit.events.emit(
            project_code,
            EVIDENCE_EVENT_KIND,
            f"Evidence attached: {row.original_name}",
            ref_table="evidence",
            ref_id=None,
            body=note or None,
        )
        return stored

    def open_path(self, project_code: str, rel_path: str) -> str:
        """Return the ABSOLUTE path of an evidence file after validating
        the project, the rel_path, and the file's existence.

        Raises PathEscape if rel_path leaves the project's evidence folder,
        MissingFileError if the file is not on disk.
        """
        self._require_project(project_code)

        expected_prefix = f"{EVIDENCE_DIR}/{project_code}/"
        normalised = rel_path.replace("\\", "/")
        if normalised.startswith("/") or ".." in normalised.split("/"):
            raise PathEscape(f"path escape: {rel_path!r}")
        if not normalised.startswith(expected_prefix):
            raise PathEscape(
                f"{rel_path!r} is not inside {expected_prefix!r}"
            )

        abs_path = os.path.join(self._root, *normalised.split("/"))
        if not os.path.isfile(abs_path):
            raise MissingFileError(f"no file at {rel_path!r}")
        return abs_path

    def list_for(self, project_code: str) -> list[EvidenceRow]:
        """The project's evidence rows, newest first."""
        rows = self._ensure_data().evidence.list_for(project_code)
        return sorted(rows, key=lambda r: r.attached_at, reverse=True)
