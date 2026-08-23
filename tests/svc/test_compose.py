"""Tests for services.compose — card P-10a-i (ServiceKit skeleton).

Done-when (P-10a-i):
  - ServiceKit(root) stores the root; no filesystem, no database.
  - every C3.0 slot is a placeholder raising CoreError naming the slot
    on ANY attribute access (parametrized over the eight slot names).
  - test_c30_attribute_set — the complete attribute set, by name.
"""

from __future__ import annotations

import pytest

from core import CoreError
from services import ServiceKit
from services.compose import C30_SLOTS

SLOT_NAMES = (
    "project_svc",
    "phase_svc",
    "actions_svc",
    "evidence_svc",
    "minutes_svc",
    "report_svc",
    "backup_svc",
    "integrity_svc",
)


def test_root_stored(tmp_path: object) -> None:
    root = "/tmp/some/workspace"
    kit = ServiceKit(root)
    assert kit.root == root


@pytest.mark.parametrize("slot", SLOT_NAMES)
def test_placeholder_raises_coreerror_naming_slot(slot: str) -> None:
    kit = ServiceKit("/tmp/some/workspace")
    placeholder = getattr(kit, slot)
    with pytest.raises(CoreError) as excinfo:
        _ = placeholder.any_attribute
    assert slot in str(excinfo.value)


def test_c30_attribute_set() -> None:
    kit = ServiceKit("/tmp/some/workspace")
    assert set(C30_SLOTS) == set(SLOT_NAMES)
    for slot in SLOT_NAMES:
        assert hasattr(kit, slot)
    # The frozen shape: exactly the eight slots plus root.
    assert set(vars(kit)) == set(SLOT_NAMES) | {"root"}
