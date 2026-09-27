"""Files with HTTP Range, for <video> and <img>.

The standard library's file handler knows nothing about Range, which a video
player needs to seek. Open-ended ranges ("bytes=0-", what browsers send) are
capped at 8 MiB: the player simply asks for the next piece, and each response
keeps the file open only briefly, so Windows can still delete or replace it
(an open file cannot be removed there).
"""

from __future__ import annotations

import os
import re
from dataclasses import dataclass
from pathlib import Path
from urllib.parse import quote

MAX_OPEN_RANGE = 8 * 1024 * 1024
CHUNK = 256 * 1024

_RANGE_RE = re.compile(r"^\s*bytes\s*=\s*(\d*)\s*-\s*(\d*)\s*$", re.IGNORECASE)


class RangeNotSatisfiable(Exception):
    pass


@dataclass
class FileReply:
    """What to send: status, headers, and the byte span of ``path`` (None for HEAD/304)."""

    status: int
    headers: dict
    path: Path | None = None
    start: int = 0
    length: int = 0


def parse_range(header: str | None, size: int) -> tuple[int, int] | None:
    """Inclusive (start, end) for a single byte range, or None to send the whole file.

    Only the first range of a multi-range request is honoured. A syntactically
    invalid header is ignored (RFC 9110); a range starting past the end raises
    RangeNotSatisfiable.
    """
    if not header:
        return None
    m = _RANGE_RE.match(header.split(",", 1)[0])
    if not m:
        return None
    first, last = m.groups()
    if not first and not last:
        return None
    if not first:  # suffix: the last N bytes
        count = int(last)
        if count == 0 or size == 0:
            raise RangeNotSatisfiable()
        return max(0, size - count), size - 1
    start = int(first)
    if start >= size:
        raise RangeNotSatisfiable()
    if last:
        end = int(last)
        if end < start:
            return None
        return start, min(end, size - 1)
    return start, min(size - 1, start + MAX_OPEN_RANGE - 1)


def etag_for(stat: os.stat_result) -> str:
    return f'"{stat.st_size:x}-{stat.st_mtime_ns:x}"'


def content_disposition(filename: str) -> str:
    """attachment with an ASCII fallback and the exact UTF-8 name (RFC 6266 / 5987)."""
    ascii_name = filename.encode("ascii", "replace").decode("ascii").replace('"', "'").replace("?", "_")
    return f"attachment; filename=\"{ascii_name}\"; filename*=UTF-8''{quote(filename, safe='')}"


def prepare(
    path: Path,
    content_type: str,
    headers_in,
    head: bool = False,
    cache: str = "private, no-cache",
    download_name: str | None = None,
) -> FileReply:
    """Status and headers for serving ``path`` given the request headers."""
    stat = path.stat()
    size = stat.st_size
    etag = etag_for(stat)
    headers = {
        "Content-Type": content_type,
        "Accept-Ranges": "bytes",
        "ETag": etag,
        "Cache-Control": cache,
    }
    if download_name:
        headers["Content-Disposition"] = content_disposition(download_name)

    range_header = headers_in.get("Range")
    if_range = headers_in.get("If-Range")
    if range_header and if_range and if_range.strip() != etag:
        range_header = None  # the file changed since the client's first piece: send it whole
    if not range_header and etag in [t.strip() for t in (headers_in.get("If-None-Match") or "").split(",")]:
        return FileReply(304, headers)

    try:
        span = parse_range(range_header, size)
    except RangeNotSatisfiable:
        headers.update({"Content-Range": f"bytes */{size}", "Content-Length": "0"})
        headers.pop("Content-Type")
        return FileReply(416, headers)
    if span is None:
        start, length, status = 0, size, 200
    else:
        start, end = span
        length, status = end - start + 1, 206
        headers["Content-Range"] = f"bytes {start}-{end}/{size}"
    headers["Content-Length"] = str(length)
    return FileReply(status, headers, None if head else path, start, length)


def copy_span(path: Path, start: int, length: int, out) -> None:
    """Write ``length`` bytes of ``path`` from ``start`` to the socket file ``out``."""
    with open(path, "rb") as f:
        f.seek(start)
        remaining = length
        while remaining > 0:
            chunk = f.read(min(CHUNK, remaining))
            if not chunk:  # the file shrank meanwhile: the client will see a short body
                break
            out.write(chunk)
            remaining -= len(chunk)
