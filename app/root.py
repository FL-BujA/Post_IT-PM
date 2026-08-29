"""app.root — the composition root.

The one place that decides which implementations the app runs on. Every
other module receives what it needs and constructs nothing global.

DEVIATION (logged in BUILD_STATE.md): C2.5 and C3.9 specify stub
implementations, and MOSAIC R3 puts a stubbed skeleton before real logic.
This project built real implementations first, and no stubs exist. WiredConfig
therefore keeps the contract's shape but has one honest branch: every flag
resolves real. The seam card (P-27) is retired rather than left to pass
vacuously — a seam that can only swap one way proves nothing.

If stubs are written later, this is the only file that needs to change.
"""

from __future__ import annotations

from dataclasses import dataclass

from services import ServiceKit
from services.renderer_stub import StubRenderer


@dataclass(frozen=True)
class WiredConfig:
    """Which implementations to build. Kept for shape; see the module
    docstring for why every flag is currently forced real."""

    data: bool = True
    services: bool = True
    renderer: bool = False        # the real renderer does not exist yet


def build_kit(
    workspace_root: str, wired: WiredConfig | None = None
) -> ServiceKit:
    """Build the ServiceKit the app runs on.

    The renderer is the one genuine seam still open: C3.6's real
    implementation needs a PDF library, so the stub is wired until P-17
    lands. That swap happens here and nowhere else — a stub must never be
    chosen anywhere below this line (anti-pattern #9).
    """
    wired = wired or WiredConfig()

    if wired.renderer:
        raise NotImplementedError(
            "the real C3.6 renderer is not built yet; leave renderer=False"
        )

    kit = ServiceKit(workspace_root)
    return kit


def renderer_for(wired: WiredConfig | None = None) -> object:
    """The renderer the kit should use. Separated so a caller can see which
    implementation it got without reaching into the kit."""
    wired = wired or WiredConfig()
    if wired.renderer:
        raise NotImplementedError(
            "the real C3.6 renderer is not built yet; leave renderer=False"
        )
    return StubRenderer()
