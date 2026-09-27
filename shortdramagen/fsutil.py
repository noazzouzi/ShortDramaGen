"""File replacements that survive Windows.

Windows refuses to replace or move a file that another program has open
(``PermissionError``, WinError 5 or 32): ``sdg ui`` reading a manifest while a
download rewrites it, the antivirus scanning a file just written, a video
player… These locks last from a few milliseconds to a few hundred, so the
operation is retried for about 3 seconds before giving up.
"""

from __future__ import annotations

import os
import time
from pathlib import Path

DELAYS = (0.01, 0.02, 0.05, 0.1, 0.2, 0.3, 0.4, 0.5, 0.6, 0.8)  # ≈ 3 s in all


def replace(src: Path, dst: Path, delays: tuple[float, ...] = DELAYS) -> None:
    """``os.replace``, retried while the source or the destination is locked."""
    for delay in (*delays, None):
        try:
            os.replace(src, dst)
            return
        except PermissionError:
            if delay is None:
                raise
            time.sleep(delay)


def write_text(path: Path, text: str) -> None:
    """Write atomically: a temporary file next to ``path``, then a replacement."""
    tmp = path.with_name(path.name + ".tmp")
    tmp.write_text(text, encoding="utf-8")
    replace(tmp, path)


def read_text(path: Path, delays: tuple[float, ...] = (0.01, 0.03, 0.1)) -> str:
    """``Path.read_text``, retried briefly: opening can fail during a replacement."""
    for delay in (*delays, None):
        try:
            return path.read_text(encoding="utf-8")
        except PermissionError:
            if delay is None:
                raise
            time.sleep(delay)
    raise AssertionError("unreachable")
