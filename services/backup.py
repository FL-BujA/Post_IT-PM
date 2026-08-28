"""services.backup — BackupService (card A-07).

C3.7: stdlib only — shutil, hashlib, json, sqlite3's backup API.

The data-loss guarantee the whole tool rests on. Two frozen rules from the
contract are load-bearing and are asserted by name in the tests:

  I6 — restore verifies BEFORE it replaces. Integrity is checked against
       the backup, and a failure aborts before a single file is written
       over.
  restore is merge-over. Files present in the backup overwrite their
       counterparts; workspace content the backup does not contain is left
       alone. Restore never deletes.

Deviation from C3.7, logged in BUILD_STATE.md: the contract says the live
DataKit handle is closed "via DataKit.close() injected for this op —
composition root wires it". No such injection exists. This service opens and
closes its own DataKit instead. The behaviour is the same in a
single-process tool; the wiring differs.
"""

from __future__ import annotations

import json
import os
import shutil
import sqlite3
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any

from core import CoreError, MissingFileError
from core.hash import sha256_file
from data import DataKit
from data.migrate import SCHEMA_VERSION, migrate

#: Trees copied into a backup alongside the database.
BACKUP_TREES = ("evidence", "reports")

#: The database file inside the workspace and inside a backup.
DB_NAME = "app.db"

#: Written into every backup; restore refuses a directory without it.
MANIFEST_NAME = "MANIFEST.json"

#: Where backups live, relative to the workspace root.
BACKUPS_DIR = "backups"


@dataclass(frozen=True)
class BackupDescriptor:
    """C3.7 create_backup return value."""

    count_files: int
    dest: str
    ok: bool = True


@dataclass(frozen=True)
class RestoreReport:
    """C3.7 restore return value."""

    ok: bool
    verified_ok: bool
    missing_count: int
    mismatch_count: int
    orphan_count: int


class BackupService:
    """C3.7 BackupService — copy out, verify, copy back."""

    def __init__(self, workspace_root: str) -> None:
        self._root = workspace_root
        self._data: DataKit | None = None

    def __getattr__(self, name: str) -> Any:
        if name.startswith("_"):
            raise AttributeError(name)
        raise CoreError(
            f"services slot 'backup' has no attribute '{name}'"
        )

    def _db_path(self) -> str:
        return os.path.join(self._root, DB_NAME)

    def _ensure_data(self) -> DataKit:
        if self._data is None:
            migrate(self._db_path())
            self._data = DataKit(self._db_path())
        return self._data

    def _close_data(self) -> None:
        """Release the live handle so the database file can be replaced."""
        if self._data is not None:
            self._data.close()
            self._data = None

    # -- manifest ----------------------------------------------------------

    def _manifest_entries(self, base: str) -> list[dict[str, Any]]:
        """Every file under base, with its size and sha256, rel_path first
        so the manifest is stable across machines."""
        entries: list[dict[str, Any]] = []
        for dirpath, _dirnames, filenames in os.walk(base):
            for name in sorted(filenames):
                if name == MANIFEST_NAME:
                    continue
                abs_path = os.path.join(dirpath, name)
                rel_path = os.path.relpath(abs_path, base).replace("\\", "/")
                entries.append(
                    {
                        "rel_path": rel_path,
                        "size": os.path.getsize(abs_path),
                        "sha256": sha256_file(abs_path),
                    }
                )
        return sorted(entries, key=lambda e: e["rel_path"])

    # -- C3.7 --------------------------------------------------------------

    def create_backup(
        self,
        label: str | None = None,
        dest_dir: str | None = None,
    ) -> BackupDescriptor:
        """Copy the database and the evidence and reports trees into a
        dated backup directory, then write a MANIFEST over everything
        copied.

        Default destination: <workspace>/backups/<YYYY-MM-DD>_<label|full>/
        """
        stamp = datetime.now(tz=timezone.utc).strftime("%Y-%m-%d")
        if dest_dir is None:
            dest_dir = os.path.join(
                self._root, BACKUPS_DIR, f"{stamp}_{label or 'full'}"
            )
        os.makedirs(dest_dir, exist_ok=True)

        # 1. the database, through SQLite's backup API so a live handle is
        #    safe. Fall back to a file copy if no handle is open.
        db_dest = os.path.join(dest_dir, DB_NAME)
        if os.path.exists(self._db_path()):
            kit = self._ensure_data()
            target = sqlite3.connect(db_dest)
            try:
                kit.conn.backup(target)
            except AttributeError:
                target.close()
                shutil.copy2(self._db_path(), db_dest)
            else:
                target.close()

        # 2. the trees
        for tree in BACKUP_TREES:
            src = os.path.join(self._root, tree)
            if not os.path.isdir(src):
                continue
            shutil.copytree(
                src, os.path.join(dest_dir, tree), dirs_exist_ok=True
            )

        # 3. the manifest, over every file copied
        entries = self._manifest_entries(dest_dir)
        manifest = {
            "created_at": datetime.now(tz=timezone.utc).isoformat(),
            "schema_version": SCHEMA_VERSION,
            "files": entries,
        }
        with open(
            os.path.join(dest_dir, MANIFEST_NAME), "w", encoding="utf-8"
        ) as fh:
            json.dump(manifest, fh, indent=2, sort_keys=True)

        # 4. record when we last backed up
        try:
            kit = self._ensure_data()
            kit.tx(
                lambda conn: conn.execute(
                    "INSERT INTO meta(key, value) VALUES('last_backup_at', ?) "
                    "ON CONFLICT(key) DO UPDATE SET value = excluded.value",
                    (manifest["created_at"],),
                )
            )
        except Exception:                      # noqa: BLE001 - meta is advisory
            pass

        return BackupDescriptor(
            count_files=len(entries), dest=dest_dir, ok=True
        )

    def restore(self, backup_dir: str) -> RestoreReport:
        """Restore a backup into the CURRENT workspace root.

        I6: the backup is verified against its own manifest BEFORE
        anything in the workspace is touched. A mismatch aborts with
        nothing written.

        Merge-over: files in the backup overwrite their counterparts;
        workspace files the backup does not contain are left in place.
        Nothing is ever deleted.
        """
        manifest_path = os.path.join(backup_dir, MANIFEST_NAME)
        if not os.path.isfile(manifest_path):
            raise MissingFileError(
                f"backup at {backup_dir!r} has no {MANIFEST_NAME}"
            )

        with open(manifest_path, encoding="utf-8") as fh:
            manifest = json.load(fh)

        # --- I6: verify the backup before replacing anything -------------
        missing = 0
        mismatched = 0
        for entry in manifest.get("files", []):
            abs_path = os.path.join(backup_dir, *entry["rel_path"].split("/"))
            if not os.path.isfile(abs_path):
                missing += 1
            elif sha256_file(abs_path) != entry["sha256"]:
                mismatched += 1

        if missing or mismatched:
            return RestoreReport(
                ok=False,
                verified_ok=False,
                missing_count=missing,
                mismatch_count=mismatched,
                orphan_count=0,
            )

        # --- replace ------------------------------------------------------
        self._close_data()

        db_src = os.path.join(backup_dir, DB_NAME)
        if os.path.isfile(db_src):
            shutil.copy2(db_src, self._db_path())

        for tree in BACKUP_TREES:
            src = os.path.join(backup_dir, tree)
            if os.path.isdir(src):
                shutil.copytree(
                    src, os.path.join(self._root, tree), dirs_exist_ok=True
                )

        # --- verify the result -------------------------------------------
        report = self._ensure_data().integrity.verify(self._root)
        return RestoreReport(
            ok=report.ok,
            verified_ok=report.ok,
            missing_count=len(report.missing),
            mismatch_count=len(report.mismatched),
            orphan_count=len(report.orphans),
        )
