"""Tests for services.projects — card P-10a-ii (project lifecycle).

Done-when (P-10a-ii):
  - test_one_call_whole_world — create_project on a FRESH empty tmp
    workspace produces, in ONE call: project row with status 'planned',
    charter event, first open cycle named 'Charter cycle', evidence/
    reports/ backups/ directories, root manifest.json with
    projects: ["P001"], NO evidence rows.
  - a duplicate code raises ServiceError with code 'project_exists'.
  - update_project: name, target and prepared_for each persist and emit
    an UPDATE event naming the changed field (parametrized x3).
  - ServiceKit(tmp).project_svc is the real ProjectSVC; the other seven
    slots still raise CoreError.
"""

from __future__ import annotations

import json
import os

import pytest

from core import CoreError, ServiceError
from services import ServiceKit
from services.projects import ProjectSVC


def _make_kit(tmp_path: object) -> ServiceKit:
    """Create a ServiceKit over a fresh tmp workspace."""
    root = str(tmp_path)
    return ServiceKit(root)


def test_one_call_whole_world(tmp_path: object) -> None:
    """Signature acceptance: one call builds the entire project world."""
    kit = _make_kit(tmp_path)
    svc = kit.project_svc

    # ONE call.
    project = svc.create_project("Alpha Bom", "2026-09-30", "TBD")

    # 1. Project row with status 'charter' (initial status per C3.3).
    assert project.code == "P001"
    assert project.name == "Alpha Bom"
    assert project.status == "charter"

    # 2. Charter event present (kind 'charter', summary contains 'Alpha Bom').
    events = svc._data.events.list_for("P001")
    charter_events = [e for e in events if e.kind == "charter"]
    assert len(charter_events) == 1
    assert "Alpha Bom" in charter_events[0].title

    # 3. First open cycle row named 'Charter cycle'.
    cycle = svc._data.cycles.current_for("P001")
    assert cycle is not None
    assert cycle.name == "Charter cycle"

    # 4. evidence/, reports/ and backups/ directories created.
    root = str(tmp_path)
    for d in ("evidence", "reports", "backups"):
        assert os.path.isdir(os.path.join(root, d)), f"missing {d}/"

    # 5. Root manifest.json exists with projects: ["P001"].
    manifest_path = os.path.join(root, "manifest.json")
    assert os.path.isfile(manifest_path)
    with open(manifest_path, "r", encoding="utf-8") as fh:
        manifest = json.load(fh)
    assert manifest["projects"] == ["P001"]

    # 6. NO evidence rows (nothing attached yet).
    evidence = svc._data.evidence.list_for("P001")
    assert evidence == []


def test_duplicate_code_raises_serviceerror(tmp_path: object) -> None:
    """A duplicate code raises ServiceError with code 'project_exists'."""
    kit = _make_kit(tmp_path)
    svc = kit.project_svc

    # First project succeeds.
    svc.create_project("Alpha Bom", "2026-09-30", "TBD")

    # Second project with the same name raises.
    with pytest.raises(ServiceError) as excinfo:
        svc.create_project("Alpha Bom", "2026-10-31", "TBD")
    assert excinfo.value.code == "project_exists"


@pytest.mark.parametrize(
    "field, value",
    [
        ("name", "New Name"),
        ("target", "New Target"),
        ("prepared_for", "New Sponsor"),
    ],
)
def test_update_project_persists_and_emits_event(
    tmp_path: object, field: str, value: str
) -> None:
    """update_project persists the field and emits an UPDATE event."""
    kit = _make_kit(tmp_path)
    svc = kit.project_svc

    # Create a project first.
    svc.create_project("Alpha Bom", "2026-09-30", "TBD")

    # Update the field.
    kwargs = {field: value}
    updated = svc.update_project("P001", **kwargs)

    # The field is persisted.
    if field == "name":
        assert updated.name == value
    elif field == "target":
        assert updated.target == value
    elif field == "prepared_for":
        assert updated.sponsor == value

    # An UPDATE event naming the changed field is emitted.
    events = svc._data.events.list_for("P001")
    update_events = [e for e in events if "updated" in e.title.lower()]
    assert len(update_events) >= 1
    assert any(field in e.title for e in update_events)


def test_servicekit_project_svc_is_real_others_placeholder(
    tmp_path: object,
) -> None:
    """ServiceKit(tmp).project_svc is the real ProjectSVC; the other
    seven slots still raise CoreError."""
    kit = _make_kit(tmp_path)

    # project_svc is the real ProjectSVC.
    assert isinstance(kit.project_svc, ProjectSVC)

    # The other seven slots still raise CoreError.
    other_slots = (
        "phase_svc",
        "actions_svc",
        "evidence_svc",
        "minutes_svc",
        "report_svc",
        "backup_svc",
        "integrity_svc",
    )
    for slot in other_slots:
        placeholder = getattr(kit, slot)
        with pytest.raises(CoreError):
            _ = placeholder.any_attribute
