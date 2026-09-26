"""Read the duration of an MP4 file (mvhd box) without ffmpeg."""

from __future__ import annotations

import struct
from pathlib import Path
from typing import BinaryIO


def _boxes(f: BinaryIO, start: int, end: int):
    """Yield (type, payload_start, box_end) for the boxes in [start, end)."""
    offset = start
    while offset + 8 <= end:
        f.seek(offset)
        header = f.read(8)
        if len(header) < 8:
            return
        size, box_type = struct.unpack(">I4s", header)
        header_size = 8
        if size == 1:
            size = struct.unpack(">Q", f.read(8))[0]
            header_size = 16
        elif size == 0:
            size = end - offset
        if size < header_size:
            return
        yield box_type, offset + header_size, offset + size
        offset += size


def duration_seconds(path: str | Path) -> float | None:
    """Movie duration in seconds, or None if the file is not a readable MP4."""
    path = Path(path)
    end = path.stat().st_size
    with path.open("rb") as f:
        for box_type, payload, box_end in _boxes(f, 0, end):
            if box_type != b"moov":
                continue
            for sub_type, sub_payload, _ in _boxes(f, payload, box_end):
                if sub_type != b"mvhd":
                    continue
                f.seek(sub_payload)
                version = f.read(1)[0]
                if version == 1:
                    f.seek(sub_payload + 20)
                    timescale, duration = struct.unpack(">IQ", f.read(12))
                else:
                    f.seek(sub_payload + 12)
                    timescale, duration = struct.unpack(">II", f.read(8))
                return duration / timescale if timescale else None
    return None
