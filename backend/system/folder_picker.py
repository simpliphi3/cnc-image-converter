"""Native folder-picker dialog.

Tkinter ships with the standalone Python that `uv` installs, so this works on the
target Windows box without extra dependencies. We open and tear down a hidden Tk
root for every call so we don't keep a mainloop alive in the server process.
"""

from __future__ import annotations

import asyncio
from pathlib import Path


def _pick_folder_sync(initial_dir: str | None) -> str | None:
    import tkinter as tk
    from tkinter import filedialog

    root = tk.Tk()
    try:
        root.withdraw()
        root.attributes("-topmost", True)
        root.update()
        start = initial_dir if initial_dir and Path(initial_dir).expanduser().exists() else None
        chosen = filedialog.askdirectory(
            initialdir=start,
            title="Choose your Aspire imports folder",
            mustexist=False,
            parent=root,
        )
    finally:
        root.destroy()
    return chosen or None


async def pick_folder(initial_dir: str | None = None) -> str | None:
    return await asyncio.to_thread(_pick_folder_sync, initial_dir)
