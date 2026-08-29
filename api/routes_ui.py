"""api.routes_ui — the C4.3 UI intent (the api's one bridge to the OS).

    GET /api/ui/open?rel_path=<evidence or report path>

This is how the PM double-clicks an evidence file or opens a report they
just generated. It is the ONLY place in the application that shell-executes
anything, and the only reason it exists is that a browser cannot open a
local file the user did not pick themselves.

Two rules, both frozen by C4.3:

  - the path is validated before anything happens. Anything outside the
    workspace raises PathEscape -> 400. A rel_path is not a filename; it is
    a claim, and it is checked.
  - only Windows executes. Everywhere else the path is resolved and
    returned, so tests and development machines exercise the validation
    without launching a viewer.
"""

from __future__ import annotations

import os
import sys
from typing import Any

from fastapi import APIRouter, Query, Request

from core import MissingFileError, PathEscape

router = APIRouter(prefix="/api")

#: Directories a rel_path may point into. Nothing else is openable, even
#: inside the workspace — the database and the backups are not documents.
OPENABLE_ROOTS = ("evidence", "reports")


def _resolve(workspace_root: str, rel_path: str) -> str:
    """Return the absolute path, or raise.

    The check is done on the resolved path, not on the string: a rel_path
    of 'evidence/../../etc/passwd' looks fine by prefix and is caught here.
    """
    normalised = (rel_path or "").replace("\\", "/").strip()
    if not normalised:
        raise PathEscape("no path given")

    head = normalised.split("/", 1)[0]
    if head not in OPENABLE_ROOTS:
        raise PathEscape(
            f"{rel_path!r} is not under {' or '.join(OPENABLE_ROOTS)}"
        )

    root = os.path.realpath(workspace_root)
    target = os.path.realpath(os.path.join(root, *normalised.split("/")))

    if not (target == root or target.startswith(root + os.sep)):
        raise PathEscape(f"path escape: {rel_path!r}")
    if not os.path.isfile(target):
        raise MissingFileError(f"no file at {rel_path!r}")
    return target


@router.get("/ui/open")
async def open_path(
    request: Request, rel_path: str = Query(..., min_length=1)
) -> dict[str, Any]:
    """C4.3 — validate, then open on Windows and resolve elsewhere."""
    kit = request.app.state.kit
    target = _resolve(kit.root, rel_path)

    opened = False
    if sys.platform.startswith("win"):
        os.startfile(target)          # noqa: S606 - the one intended call
        opened = True

    return {"opened": opened, "path": target}
