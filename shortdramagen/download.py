"""Resumable download of one file, with integrity checks."""

from __future__ import annotations

import re
import struct
from pathlib import Path
from typing import Callable
from urllib.parse import urlparse

from . import errors, fsutil, mp4
from .http import Http, HttpStatusError

CHUNK_SIZE = 256 * 1024
DURATION_TOLERANCE_S = 1.0
_CONTENT_RANGE_RE = re.compile(r"bytes\s+(\d+)-\d+/(\d+)")


class UrlRejected(Exception):
    """The CDN refused the URL (expired or invalid signature): resolve it again."""

    code = errors.URL_REJECTED


class IntegrityError(Exception):
    def __init__(self, message: str, code: str = errors.SIZE_MISMATCH):
        super().__init__(message)
        self.code = code


def download(
    http: Http,
    url: str,
    dest: Path,
    expected_duration_ms: int | None = None,
    on_progress: Callable[[int, int], None] | None = None,
) -> int:
    """Download ``url`` to ``dest`` and return its size in bytes.

    Writes to a ``.part`` file first and resumes it with a Range request if it
    already exists, so an interrupted run picks up where it stopped.
    """
    part = part_path(dest, url)
    offset = part.stat().st_size if part.exists() else 0
    headers = {"Range": f"bytes={offset}-"} if offset else {}

    try:
        with http.stream(url, headers) as (status, resp_headers, body):
            total = _total_size(status, resp_headers, offset)
            mode = "ab" if status == 206 else "wb"  # 200 = server ignored Range: restart
            written = offset if status == 206 else 0
            with part.open(mode) as f:
                while chunk := body.read(CHUNK_SIZE):
                    f.write(chunk)
                    written += len(chunk)
                    if on_progress:
                        on_progress(written, total)
    except HttpStatusError as e:
        if e.status == 416 and offset:
            # Stale .part (e.g. the file changed on the CDN): start over.
            part.unlink()
            return download(http, url, dest, expected_duration_ms, on_progress)
        if e.status in (401, 403, 404, 410):
            raise UrlRejected(str(e)) from None
        raise

    size = part.stat().st_size
    if total and size != total:
        raise IntegrityError(f"téléchargement incomplet : {size} octets reçus sur {total}")
    check_duration(part, expected_duration_ms)
    fsutil.replace(part, dest)  # the antivirus may still be scanning the .part
    for stale in dest.parent.glob(f"{dest.stem}.*.part"):  # other qualities tried before
        stale.unlink(missing_ok=True)
    return size


def part_path(dest: Path, url: str) -> Path:
    """One .part per rendition (E028.577159363.1080p.nav2.mp4.part), so resuming
    never appends the bytes of one quality to a file of another."""
    name = Path(urlparse(url).path).name or "video"
    return dest.with_name(f"{dest.stem}.{name}.part")


def check_duration(path: Path, expected_duration_ms: int | None) -> None:
    try:
        seconds = mp4.duration_seconds(path)
    except (OSError, IndexError, struct.error) as e:  # truncated or corrupt file
        path.unlink(missing_ok=True)
        raise IntegrityError(f"MP4 illisible : {e}", errors.MP4_UNREADABLE) from None
    if seconds is None:
        path.unlink(missing_ok=True)
        raise IntegrityError("MP4 illisible (pas de boîte moov/mvhd)", errors.MP4_UNREADABLE)
    if expected_duration_ms and abs(seconds - expected_duration_ms / 1000) > DURATION_TOLERANCE_S:
        path.unlink(missing_ok=True)
        raise IntegrityError(
            f"durée {seconds:.1f} s au lieu de {expected_duration_ms / 1000:.1f} s (mauvais fichier ?)",
            errors.DURATION_MISMATCH,
        )


def _total_size(status: int, headers, offset: int) -> int:
    lowered = {k.lower(): v for k, v in headers.items()}
    if status == 206:
        m = _CONTENT_RANGE_RE.match(lowered.get("content-range", ""))
        if m:
            return int(m.group(2))
    length = lowered.get("content-length")
    if length and length.isdigit():
        return int(length) + (offset if status == 206 else 0)
    return 0
