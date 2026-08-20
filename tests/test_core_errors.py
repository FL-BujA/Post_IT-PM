"""Contract tests for core.errors (C1.4).

Acceptance: the hierarchy and the stable machine codes are frozen; the api
layer (C4.2) maps err.code to the error envelope without parsing messages.
"""

from __future__ import annotations

import pytest

from core.errors import (
    CoreError,
    CycleCloseError,
    DataError,
    EvidenceConflict,
    GateMissing,
    IntegrityError,
    InvalidSlug,
    MissingFileError,
    OwnerError,
    PathEscape,
    PdfError,
    ServiceError,
    UnknownProjectData,
    UnknownProjectService,
)


def test_hierarchy_data_branch() -> None:
    assert issubclass(DataError, CoreError)
    assert issubclass(UnknownProjectData, DataError)


def test_hierarchy_service_branch() -> None:
    for cls in (
        InvalidSlug,
        PathEscape,
        OwnerError,
        UnknownProjectService,
        EvidenceConflict,
        GateMissing,
        CycleCloseError,
        IntegrityError,
        MissingFileError,
        PdfError,
    ):
        assert issubclass(cls, ServiceError), f"{cls.__name__} not a ServiceError"
    assert issubclass(ServiceError, CoreError)


def test_data_and_service_branches_are_disjoint() -> None:
    assert not issubclass(DataError, ServiceError)
    assert not issubclass(ServiceError, DataError)
    assert not issubclass(UnknownProjectService, DataError)
    assert not issubclass(UnknownProjectData, ServiceError)


def test_base_codes() -> None:
    assert CoreError.code == "core"
    assert DataError.code == "data_error"
    assert ServiceError.code == "service_error"


@pytest.mark.parametrize(
    ("cls", "expected_code"),
    [
        (UnknownProjectData, "unknown_project"),
        (UnknownProjectService, "unknown_project"),
        (InvalidSlug, "invalid_slug"),
        (PathEscape, "path_escape"),
        (OwnerError, "invalid_owner"),
        (EvidenceConflict, "evidence_conflict"),
        (GateMissing, "gate_missing"),
        (CycleCloseError, "cycle_close"),
        (IntegrityError, "integrity"),
        (MissingFileError, "missing_file"),
        (PdfError, "pdf_error"),
    ],
)
def test_frozen_machine_codes(cls: type[CoreError], expected_code: str) -> None:
    assert cls.code == expected_code


def test_concrete_codes_override_base_defaults() -> None:
    assert InvalidSlug("x").code == "invalid_slug"
    assert UnknownProjectData("x").code == "unknown_project"


def test_message_is_preserved() -> None:
    err = CycleCloseError("gate 42 has no outcome")
    assert str(err) == "gate 42 has no outcome"
    assert err.code == "cycle_close"


def test_constructor_allows_explicit_code_override() -> None:
    err = CoreError("custom", code="custom_code")
    assert err.code == "custom_code"
    assert str(err) == "custom"


def test_errors_are_catchable_as_core_error() -> None:
    with pytest.raises(CoreError):
        raise EvidenceConflict("evidence/P001/x already exists")
    with pytest.raises(CoreError):
        raise UnknownProjectData("P999 not found")


def test_errors_are_exceptions() -> None:
    assert issubclass(CoreError, Exception)
