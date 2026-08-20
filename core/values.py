"""core.values — small validated value objects (contract C1.3).

Pure data + validation, no I/O. Each type validates at construction time
and raises the frozen C1.4 error. All are comparable value objects:
equality is value-based, so ``Owner("  ana  ") == Owner("ana")``.
"""

from __future__ import annotations

from dataclasses import dataclass

from core.enums import EventKind
from core.errors import OwnerError

__all__ = [
    "ALLOWED_REF_TABLES",
    "EventRef",
    "Owner",
    "PreparedFor",
]

#: Frozen set of tables that can be referenced by an ``EventRef`` (C1.3).
ALLOWED_REF_TABLES: frozenset[str] = frozenset(
    {"charter", "decision", "action", "meeting", "gate"}
)


@dataclass(frozen=True)
class Owner:
    """A free-text owner name (C1.3).

    Whitespace-only or empty values are ``OwnerError``; surrounding
    whitespace is stripped, so instances compare by cleaned value.
    """

    name: str

    def __init__(self, name: str) -> None:
        if not isinstance(name, str) or not name.strip():
            raise OwnerError("owner name must be non-empty")
        object.__setattr__(self, "name", name.strip())


@dataclass(frozen=True)
class PreparedFor:
    """The sponsor line on a report — an open field (C1.3).

    Empty is rejected; "TBD" is explicitly allowed (sponsor is filled
    per project at generation time per SCOPE Q2).
    """

    value: str

    def __init__(self, value: str) -> None:
        if not isinstance(value, str) or not value.strip():
            raise OwnerError("prepared-for must be non-empty")
        object.__setattr__(self, "value", value.strip())


@dataclass(frozen=True)
class EventRef:
    """Reference from an event row to one of the 5 frozen tables (C1.3).

    The constructor enforces the pairing rule: ``ref_table`` is ``None``
    if and only if ``ref_id`` is ``None``. ``ref_table`` must be a member
    of ``ALLOWED_REF_TABLES``; ``kind`` must be a valid ``EventKind``.
    """

    kind: EventKind
    ref_table: str | None
    ref_id: int | None

    def __init__(
        self,
        kind: EventKind,
        ref_table: str | None = None,
        ref_id: int | None = None,
    ) -> None:
        if not isinstance(kind, EventKind):
            raise TypeError("kind must be an EventKind")

        if (ref_table is None) != (ref_id is None):
            raise OwnerError(
                "ref_table None implies ref_id None, and vice versa"
            )

        if ref_table is not None and ref_table not in ALLOWED_REF_TABLES:
            raise OwnerError(f"unknown ref_table: {ref_table!r}")

        object.__setattr__(self, "kind", kind)
        object.__setattr__(self, "ref_table", ref_table)
        object.__setattr__(self, "ref_id", ref_id)
