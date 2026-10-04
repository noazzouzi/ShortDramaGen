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
SUBTITLES_UNREADABLE = "subtitles_unreadable"  # the subtitles of a video are not a WebVTT file
QUALITY_UNAVAILABLE = "quality_unavailable"  # strict quality requested and not offered
HLS_UNSUPPORTED = "hls_unsupported"  # encrypted stream, or a playlist this engine cannot read
REMUX_FAILED = "remux_failed"  # ffmpeg could not turn the HLS segments into an MP4
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

# Montage codes (montage.py, FilmError.code)
MONTAGE_INVALID = "montage_invalid"  # recipe refused (field in RecipeError.field)
MONTAGE_EMPTY_EPISODE = "montage_empty_episode"  # the trims and cuts would leave almost nothing
MONTAGE_ENCODER_UNAVAILABLE = "montage_encoder_unavailable"  # AMF asked for, not working here
MONTAGE_FORMAT_MISMATCH = "montage_format_mismatch"  # edited episodes that cannot be joined by copy
MONTAGE_DURATION = "montage_duration"  # an edited episode does not have the expected length


class SeriesNotFound(Exception):
    """The platform does not know this series (missing or empty page)."""


class ResolveError(Exception):
    """No usable video URL for an episode. ``code``: ep_unavailable (the source said so), network, url_mismatch…"""

    def __init__(self, message: str, code: str = EP_UNAVAILABLE):
        super().__init__(message)
        self.code = code


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
