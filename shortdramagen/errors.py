"""Stable error codes, stored in the manifest and sent with events.

Messages stay free French text for people; codes are what programs (the
future web interface, tests) rely on.
"""

from __future__ import annotations

import errno
import http.client

from .http import HttpStatusError

# Episode-level codes (manifest "error_code")
EP_UNAVAILABLE = "ep_unavailable"  # the source says the episode does not exist or is unavailable
URL_MISMATCH = "url_mismatch"  # the source returned a URL for another episode
URL_REJECTED = "url_rejected"  # the CDN refused the signed URL (expired, invalid)
SIZE_MISMATCH = "size_mismatch"  # fewer bytes than announced
DURATION_MISMATCH = "duration_mismatch"  # MP4 duration differs from the official one
MP4_UNREADABLE = "mp4_unreadable"  # not an MP4 (HTML page, truncated file…)
QUALITY_UNAVAILABLE = "quality_unavailable"  # strict quality requested and not offered
NETWORK = "network"
DISK_FULL = "disk_full"
FILE_LOCKED = "file_locked"  # Windows: file open in a player
UNKNOWN = "unknown"

# Film codes (FilmError.code)
FFMPEG_MISSING = "ffmpeg_missing"
SERIES_DIR_NOT_FOUND = "not_found"  # nothing downloaded for this series
AMBIGUOUS_VERSION = "ambiguous_version"  # several languages downloaded, none chosen
NO_EPISODES = "no_episodes"
FILM_MISSING_EPISODES = "film_missing_episodes"
FILM_MIXED_FORMATS = "film_mixed_formats"
FILM_EXISTS = "film_exists"
FILM_DURATION = "film_duration"  # the joined file does not have the expected duration
FILM_FAILED = "film_failed"  # ffmpeg error
CANCELLED = "cancelled"


def code_for(exc: BaseException) -> str:
    """The stable code of an exception raised while fetching an episode."""
    code = getattr(exc, "code", None)
    if isinstance(code, str) and code:
        return code
    if isinstance(exc, OSError):
        if exc.errno == errno.ENOSPC:
            return DISK_FULL
        if isinstance(exc, PermissionError):
            return FILE_LOCKED
        return NETWORK  # URLError, timeouts, resets are all OSError
    if isinstance(exc, (http.client.HTTPException, HttpStatusError)):
        return NETWORK
    return UNKNOWN
