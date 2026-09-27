"""Show a file or a folder of the library in the system's file manager, or play it.

Only called with paths rebuilt and checked by the library index: ``os.startfile``
opens whatever it is given, executables included.
"""

from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path


def reveal(path: Path, select: bool = False) -> None:
    """Open the folder, or the folder with ``path`` selected."""
    if sys.platform == "win32":
        if select:
            subprocess.Popen(["explorer", f"/select,{path}"])
        else:
            os.startfile(path)  # noqa: S606 (a folder of the library)
    elif sys.platform == "darwin":
        subprocess.Popen(["open", "-R", str(path)] if select else ["open", str(path)])
    else:
        subprocess.Popen(["xdg-open", str(path.parent if select else path)])


def play(path: Path) -> None:
    """Open a video (.mp4 of the library) in the default player."""
    if path.suffix.lower() != ".mp4":
        raise ValueError("seules les vidéos .mp4 s'ouvrent dans le lecteur")
    if sys.platform == "win32":
        os.startfile(path)  # noqa: S606
    elif sys.platform == "darwin":
        subprocess.Popen(["open", str(path)])
    else:
        subprocess.Popen(["xdg-open", str(path)])
