"""Start Audio Sprout Studio and open it in the default browser."""

from __future__ import annotations

import threading
import webbrowser

import uvicorn


def _open_browser() -> None:
    webbrowser.open("http://127.0.0.1:7862")


if __name__ == "__main__":
    threading.Timer(1.4, _open_browser).start()
    uvicorn.run("backend.main:app", host="127.0.0.1", port=7862, reload=False)

