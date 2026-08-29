"""app.main — the one way to start the tool.

    python -m app.main

run() reads config.json, builds the real kit through the composition root,
starts uvicorn on loopback, and opens the window. If pywebview is not
available it prints the URL and the server keeps running.

C4.4: the bind address is 127.0.0.1, hardcoded in api.server. Nothing here
can change it.
"""

from __future__ import annotations

import threading
import time
from typing import Any

from api import create_app
from api.server import HOST, run as run_server
from app.config import read as read_config
from app.root import WiredConfig, build_kit
from app.window import window as open_window

#: How long to let uvicorn bind before opening the window.
STARTUP_GRACE_SECONDS = 1.0


def build(workdir: str | None = None) -> tuple[Any, str, int]:
    """Assemble everything without starting anything.

    Returns (app, workspace, port). Separated from run() so the assembly
    can be exercised without a server: the composition happens here, the
    listening happens in run().
    """
    config = read_config(workdir)
    kit = build_kit(config.workspace, WiredConfig())
    app = create_app(kit)
    return app, config.workspace, config.port


def run(
    workdir: str | None = None,
    port: int | None = None,
    open_ui: bool = True,
) -> None:
    """Start the tool. Blocks until the window closes or the server stops.

    The server runs on a daemon thread so the window owns the main thread —
    pywebview requires that on Windows and macOS. With no window, the main
    thread waits on the server instead.
    """
    app, workspace, config_port = build(workdir)
    port = port or config_port
    url = f"http://{HOST}:{port}/"

    server_thread = threading.Thread(
        target=run_server, args=(app, port), daemon=True
    )
    server_thread.start()
    time.sleep(STARTUP_GRACE_SECONDS)

    print(f"PM Cockpit — workspace {workspace}")
    print(f"Serving on {url}")

    if not open_ui:
        server_thread.join()
        return

    opened = open_window(url)
    if not opened:
        # no window: the server is the app, so hold the main thread
        server_thread.join()


if __name__ == "__main__":
    run()
