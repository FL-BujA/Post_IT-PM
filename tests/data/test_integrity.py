"""Tests for data.integrity — card P-09c (I2 + DataKit closure).

Done-when (P-09c):
  - test_i2_missing_file_flagged — a db row whose file has been deleted:
    verify returns ok=False, the row appears in missing[], and NOTHING
    is deleted from the db (row count unchanged before/after).
  - test_i2_hash_mismatch — file bytes changed after record:
    mismatched[] is non-empty and names the rel_path.
  - test_i2_orphan — a file on disk with no db row: orphans[] contains
    its rel_path.
  - test_i2_clean — a consistent workspace: ok=True and all three lists
    are empty.
  - DataKit exposes every C2.1 slot as a real implementation: one test
    asserts the full attribute set and the type of each — DATA
    CONTRACT CLOSED.
  - Forbidden: verify never deletes, repairs or quarantines — the db
    row count AND the on-disk file count are both unchanged across a
    verify call.
"""

from __future__ import annotations

from typing import Any

from core.enums import ProjectStatus, SourceType
from core.hash import short_id, sha256_bytes
from data.db import DataKit
from data.integrity import IntegrityReport, IntegrityService
from data.migrate import migrate
from data.rows import EvidenceRow

REL_PATH = "evidence/P001/2026-08-01_report.pdf"
ORPHAN_PATH = "evidence/P001/2026-08-02_orphan.pdf"


def _kit(tmp_path: Any) -> DataKit:
    # The db lives OUTSIDE the workspace root: the workspace is the
    # evidence-file surface I2 scans, and the db file itself is not
    # evidence (it must not show up as an orphan).
    db = str(tmp_path.parent / f"app-{tmp_path.name}.db")
    migrate(db)
    return DataKit(db)


def _project(kit: DataKit, code: str = "P001") -> None:
    kit.projects.create(code, f"proj {code}", ProjectStatus.ACTIVE)


def _glue_row(
    rel_path: str = REL_PATH,
    sha256: str | None = None,
    **overrides: Any,
) -> EvidenceRow:
    base = dict(
        id=short_id(),
        project_code="P001",
        ref_table="actions",
        ref_id=7,
        original_name="Report.pdf",
        source_type=SourceType.DOC.value,
        rel_path=rel_path,
        size_bytes=11,
        sha256=sha256 if sha256 is not None else sha256_bytes(b"evidence-bytes"),
        attached_at="2026-08-01T09:00:00+00:00",
    )
    base.update(overrides)
    return EvidenceRow(**base)


def _write(root: Any, rel_path: str, payload: bytes) -> None:
    path = root / rel_path
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(payload)


def _evidence_count(kit: DataKit) -> int:
    return kit.conn.execute("SELECT COUNT(*) FROM evidence").fetchone()[0]


def _file_count(root: Any) -> int:
    return sum(len(files) for _dir, _dirs, files in root.walk())


# ---------------------------------------------------------------------------
# P-09c — I2
# ---------------------------------------------------------------------------


def test_i2_missing_file_flagged(tmp_path: Any) -> None:
    """A db row whose file has been deleted: ok=False, the row is in
    missing[], and NOTHING is deleted from the db."""
    kit = _kit(tmp_path)
    _project(kit)
    row = _glue_row()
    kit.evidence.record(row)
    _write(tmp_path, REL_PATH, b"evidence-bytes")

    (tmp_path / REL_PATH).unlink()  # the file is deleted

    before_rows = _evidence_count(kit)
    before_files = _file_count(tmp_path)

    report = kit.integrity.verify(str(tmp_path))

    assert report.ok is False
    assert report.missing == [row]
    assert report.mismatched == []
    assert report.orphans == []

    # NOTHING is deleted from the db; the disk is untouched too.
    assert _evidence_count(kit) == before_rows
    assert _file_count(tmp_path) == before_files


def test_i2_hash_mismatch(tmp_path: Any) -> None:
    """File bytes changed after record: mismatched[] is non-empty and
    names the rel_path."""
    kit = _kit(tmp_path)
    _project(kit)
    row = _glue_row()
    kit.evidence.record(row)
    _write(tmp_path, REL_PATH, b"evidence-bytes")

    _write(tmp_path, REL_PATH, b"tampered-bytes")  # bytes changed

    report = kit.integrity.verify(str(tmp_path))

    assert report.ok is False
    assert report.missing == []
    assert report.orphans == []
    assert len(report.mismatched) == 1
    mismatch_row, observed = report.mismatched[0]
    assert mismatch_row.rel_path == REL_PATH
    assert observed == sha256_bytes(b"tampered-bytes")


def test_i2_orphan(tmp_path: Any) -> None:
    """A file on disk with no db row: orphans[] contains its rel_path."""
    kit = _kit(tmp_path)
    _project(kit)
    row = _glue_row()
    kit.evidence.record(row)
    _write(tmp_path, REL_PATH, b"evidence-bytes")
    _write(tmp_path, ORPHAN_PATH, b"orphan-bytes")

    report = kit.integrity.verify(str(tmp_path))

    assert report.ok is False
    assert report.missing == []
    assert report.mismatched == []
    assert report.orphans == [ORPHAN_PATH]


def test_i2_clean(tmp_path: Any) -> None:
    """A consistent workspace: ok=True and all three lists are empty."""
    kit = _kit(tmp_path)
    _project(kit)
    row = _glue_row()
    kit.evidence.record(row)
    _write(tmp_path, REL_PATH, b"evidence-bytes")

    report = kit.integrity.verify(str(tmp_path))

    assert report.ok is True
    assert report.missing == []
    assert report.mismatched == []
    assert report.orphans == []


def test_i2_verify_never_mutates(tmp_path: Any) -> None:
    """Forbidden: deleting, repairing or quarantining during verify —
    the db row count AND the file count are both unchanged across a
    verify call (even a dirty one)."""
    kit = _kit(tmp_path)
    _project(kit)
    row = _glue_row()
    kit.evidence.record(row)
    _write(tmp_path, REL_PATH, b"tampered-bytes")  # mismatch
    _write(tmp_path, ORPHAN_PATH, b"orphan-bytes")  # orphan

    before_rows = _evidence_count(kit)
    before_files = _file_count(tmp_path)

    report = kit.integrity.verify(str(tmp_path))
    assert report.ok is False

    assert _evidence_count(kit) == before_rows
    assert _file_count(tmp_path) == before_files
    # The row is still fetchable and the files still on disk.
    assert kit.evidence.get_by_path(REL_PATH).id == row.id
    assert (tmp_path / REL_PATH).is_file()
    assert (tmp_path / ORPHAN_PATH).is_file()


# ---------------------------------------------------------------------------
# P-09c — DataKit closure (C2.1)
# ---------------------------------------------------------------------------


def test_datakit_exposes_full_c21_attribute_set(tmp_path: Any) -> None:
    """DataKit exposes every C2.1 slot as a real implementation — one
    test asserts the full attribute set and the type of each.
    DATA CONTRACT CLOSED."""
    import data as data_pkg
    from data.actions import ActionRepo
    from data.cycles import CycleRepo
    from data.evidence import EvidenceRepo
    from data.events import EventRepo
    from data.gates import GateRepo
    from data.projects import ProjectRepo

    kit = _kit(tmp_path)

    expected = {
        "projects": ProjectRepo,
        "events": EventRepo,
        "cycles": CycleRepo,
        "gates": GateRepo,
        "actions": ActionRepo,
        "evidence": EvidenceRepo,
        "integrity": IntegrityService,
    }
    for name, cls in expected.items():
        assert type(getattr(kit, name)) is cls, name

    # The C2.1 shape is exported by the package.
    assert data_pkg.IntegrityService is IntegrityService
    assert data_pkg.IntegrityReport is IntegrityReport
    assert "IntegrityService" in data_pkg.__all__
    assert "IntegrityReport" in data_pkg.__all__
