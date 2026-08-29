"""api.server — the uvicorn entry point (C4.4).

C4.4 is an architecture constraint, not a preference: the server binds
127.0.0.1 and nothing else. The host is hardcoded here and config.json's
"host" key, if present, is ignored. A test asserts both.

No CORS middleware. Nothing cross-origin is served or consumed, and adding
one would be a way in from another origin (C4.4 frozen).
"""

from __future__ import annotations

import json
import os
from typing import Any

#: C4.4: hardcoded. Config cannot override this.
HOST = "127.0.0.1"

#: C4.0 default when config.json says nothing.
DEFAULT_PORT = 8765

#: Config keys that are read. "host" is deliberately absent — see C4.4.
CONFIG_NAME = "config.json"


def read_config(workspace_root: str) -> dict[str, Any]:
    """Read config.json from the workspace root, writing defaults on first
    run (C4.0).

    A "host" key in the file is IGNORED. It is not an error to have one —
    older files may — but it never reaches uvicorn.
    """
    path = os.path.join(workspace_root, CONFIG_NAME)
    if not os.path.isfile(path):
        defaults = {
            "workspace": workspace_root.replace("\\", "/"),
            "port": DEFAULT_PORT,
            "theme": "dark",
        }
        os.makedirs(workspace_root, exist_ok=True)
        with open(path, "w", encoding="utf-8") as fh:
            json.dump(defaults, fh, indent=2)
        return defaults

    with open(path, encoding="utf-8") as fh:
        config = json.load(fh)
    config.pop("host", None)              # C4.4: never honoured
    config.setdefault("port", DEFAULT_PORT)
    config.setdefault("theme", "dark")
    return config


def run_config(port: int | None = None) -> dict[str, Any]:
    """The uvicorn keyword arguments. Separated from run() so a test can
    assert the bind address without starting a server."""
    return {
        "host": HOST,
        "port": port or DEFAULT_PORT,
        "log_level": "info",
    }


def run(app: Any, port: int | None = None) -> None:
    """Start uvicorn on loopback. Imported lazily so the module can be
    inspected without uvicorn installed."""
    import uvicorn

    uvicorn.run(app, **run_config(port))
