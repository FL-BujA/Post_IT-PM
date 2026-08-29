"""app.window — the window adapter (risk R1).

The contract names a window, not a library. pywebview is the intended one;
if it will not import on the target machine the app prints the URL and keeps
running, because a PM who cannot open a window still has a working tool at
that address.

The import is inside the function deliberately: nothing that merely inspects
this module needs pywebview installed.
"""

from __future__ import annotations

import sys

#: Window chrome.
TITLE = "PM Cockpit"
WIDTH = 1280
HEIGHT = 860


def window(url: str, title: str = TITLE, blocking: bool = True) -> bool:
    """Open a desktop window at url.

    Returns True if a real window opened, False if the fallback ran. The
    caller decides what to do with that; run() treats both as success,
    because the server is up either way.
    """
    try:
        import webview                      # noqa: PLC0415 - see docstring
    except ImportError:
        print(f"\n{title} is running at {url}")
        print("Open that address in Edge or your browser.\n", file=sys.stderr)
        return False

    webview.create_window(title, url, width=WIDTH, height=HEIGHT)
    if blocking:
        webview.start()
    return True
