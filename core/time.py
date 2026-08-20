"""core.time — the single source of truth for "now" (contract C1.5).

One rule for every layer: all timestamps come from ``now_utc()``. It
returns an aware ``datetime`` pinned to UTC, so stored values never
drift with a host-local timezone and comparisons are always valid.
No layer calls ``datetime.now()`` or ``datetime.utcnow()`` directly.
"""

from __future__ import annotations

from datetime import datetime, timezone

__all__ = ["A4_PAGE_PT", "now_utc"]


def now_utc() -> datetime:
    """The one clock for the whole system (C1.5).

    Returns an aware ``datetime`` in UTC. Monotonicity is guaranteed by
    the underlying clock (two calls 50 ms apart: second >= first), but
    no monotonicity is enforced here — this is a pure read of the wall
    clock, no policy.
    """
    return datetime.now(timezone.utc)
