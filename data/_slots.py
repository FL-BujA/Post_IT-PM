"""data._slots — C2.1 assembly slots, frozen from card P-06.

P-06 made ``DataKit`` assemble the (projects, events) repositories.
Everything else the C2.1 shape names (cycles, charter, evidence,
decisions, actions, gates, search, integrity) stays a typed slot: a
placeholder class whose instances raise ``CoreError`` (code
``not_implemented_in_this_phase``) on attribute access — later cards
replace the slot classes with real ones, never reshuffle the shape.
"""

from __future__ import annotations

from typing import Any

from core.errors import CoreError

#: Frozen slot code for the not-yet-built repositories (P-06 shape).
NOT_IMPLEMENTED_CODE = "not_implemented_in_this_phase"


class _Slot:
    """Placeholder repository slot (C2.1 shape, P-06).

    Accessing any attribute on an instance raises ``CoreError`` with
    code ``not_implemented_in_this_phase`` — deliberately a
    ``CoreError``, NOT an ``AttributeError``.
    """

    def __getattribute__(self, name: str) -> Any:
        raise CoreError(
            f"{type(self).__name__} is not implemented in this phase",
            code=NOT_IMPLEMENTED_CODE,
        )


__all__ = [
    "NOT_IMPLEMENTED_CODE",
    "ActionRepoSlot",
    "CharterRepoSlot",
    "CycleRepoSlot",
    "DecisionRepoSlot",
    "EvidenceRepoSlot",
    "GateRepoSlot",
    "IntegritySlot",
    "SearchSlot",
]

#: One typed slot per remaining C2.1 repository (later cards fill them).
CharterRepoSlot = _Slot
EvidenceRepoSlot = _Slot
DecisionRepoSlot = _Slot
ActionRepoSlot = _Slot
CycleRepoSlot = _Slot
GateRepoSlot = _Slot
SearchSlot = _Slot
IntegritySlot = _Slot
