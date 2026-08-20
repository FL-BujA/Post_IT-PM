"""core.errors — error types shared by every layer (contract C1.4).

Hierarchy:
    CoreError
    ├── DataError            (data layer raises these)
    │    └── UnknownProjectData
    └── ServiceError         (services layer raises these)
         ├── InvalidSlug
         ├── PathEscape
         ├── OwnerError
         ├── UnknownProjectService
         ├── EvidenceConflict
         ├── GateMissing
         ├── CycleCloseError
         ├── IntegrityError
         ├── MissingFileError
         └── PdfError

Every concrete error carries a stable machine ``code`` string so the api
layer can map to the frozen error envelope (C4.2) without parsing messages.
"""

from __future__ import annotations


class CoreError(Exception):
    """Base error. ``code`` is a stable machine string (e.g. "invalid_slug")."""

    code: str = "core"

    def __init__(self, message: str, *, code: str | None = None) -> None:
        super().__init__(message)
        if code is not None:
            self.code = code


class DataError(CoreError):
    """Data layer raises these."""

    code = "data_error"


class ServiceError(CoreError):
    """Services layer raises these."""

    code = "service_error"


class UnknownProjectData(DataError):
    def __init__(self, message: str) -> None:
        super().__init__(message, code="unknown_project")


class InvalidSlug(ServiceError):
    def __init__(self, message: str) -> None:
        super().__init__(message, code="invalid_slug")


class PathEscape(ServiceError):
    def __init__(self, message: str) -> None:
        super().__init__(message, code="path_escape")


class OwnerError(ServiceError):
    def __init__(self, message: str) -> None:
        super().__init__(message, code="invalid_owner")


class UnknownProjectService(ServiceError):
    def __init__(self, message: str) -> None:
        super().__init__(message, code="unknown_project")


class EvidenceConflict(ServiceError):
    def __init__(self, message: str) -> None:
        super().__init__(message, code="evidence_conflict")


class GateMissing(ServiceError):
    def __init__(self, message: str) -> None:
        super().__init__(message, code="gate_missing")


class CycleCloseError(ServiceError):
    def __init__(self, message: str) -> None:
        super().__init__(message, code="cycle_close")


class IntegrityError(ServiceError):
    def __init__(self, message: str) -> None:
        super().__init__(message, code="integrity")


class MissingFileError(ServiceError):
    def __init__(self, message: str) -> None:
        super().__init__(message, code="missing_file")


class PdfError(ServiceError):
    def __init__(self, message: str) -> None:
        super().__init__(message, code="pdf_error")


__all__ = [
    "CoreError",
    "DataError",
    "ServiceError",
    "UnknownProjectData",
    "InvalidSlug",
    "PathEscape",
    "OwnerError",
    "UnknownProjectService",
    "EvidenceConflict",
    "GateMissing",
    "CycleCloseError",
    "IntegrityError",
    "MissingFileError",
    "PdfError",
]
