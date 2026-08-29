"""app.config — config.json: where the workspace is and which port to use.

C4.0: first run writes defaults with the workspace under the user's
Documents. Later runs read it, so the PM's folder choice survives a restart.

C4.4: a "host" key is IGNORED. The server binds loopback and nothing else,
and config cannot change that. A non-loopback bind is refused rather than
silently corrected, because a personal tool quietly listening on a LAN
address is a security failure, not a preference.
"""

from __future__ import annotations

import json
import os
from dataclasses import dataclass

from core import CoreError

CONFIG_NAME = "config.json"
DEFAULT_PORT = 8765
DEFAULT_THEME = "dark"

#: The only addresses the app will bind. C4.4.
LOOPBACK = ("127.0.0.1", "localhost", "::1")


class ConfigError(CoreError):
    """A config.json that cannot be honoured."""

    code = "config"


@dataclass(frozen=True)
class AppConfig:
    """What the app needs to start."""

    workspace: str
    port: int = DEFAULT_PORT
    theme: str = DEFAULT_THEME
    path: str = ""


def default_workspace() -> str:
    """<userprofile>/Documents/PM-Cockpit, per C4.0."""
    home = os.path.expanduser("~")
    return os.path.join(home, "Documents", "PM-Cockpit")


def read(workdir: str | None = None) -> AppConfig:
    """Read config.json from workdir, creating it with defaults if absent.

    Returns the same workspace on a second call without rewriting the file
    — the folder memory the PM relies on.

    Raises ConfigError if the file names a non-loopback host (C4.4).
    """
    root = workdir or default_workspace()
    os.makedirs(root, exist_ok=True)
    path = os.path.join(root, CONFIG_NAME)

    if not os.path.isfile(path):
        data = {
            # forward slashes even on Windows, frozen by C4.0
            "workspace": root.replace("\\", "/"),
            "port": DEFAULT_PORT,
            "theme": DEFAULT_THEME,
        }
        with open(path, "w", encoding="utf-8") as fh:
            json.dump(data, fh, indent=2)
    else:
        with open(path, encoding="utf-8") as fh:
            data = json.load(fh)

    host = data.get("host")
    if host is not None and host not in LOOPBACK:
        raise ConfigError(
            f"config names host {host!r}; this tool binds loopback only "
            f"(C4.4). Remove the key or set it to 127.0.0.1."
        )

    return AppConfig(
        workspace=data.get("workspace", root),
        port=int(data.get("port", DEFAULT_PORT)),
        theme=data.get("theme", DEFAULT_THEME),
        path=path,
    )
