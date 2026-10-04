"""HLS episodes (m3u8): segments downloaded in order, then remuxed into an MP4 by ffmpeg.

Everything on disk is an ``E001.*.part`` file, so the library, the queue and the
trash treat an interrupted HLS download like any other:

- ``E001.<playlist>.ts.part``: the segments, appended in order
- ``E001.<playlist>.idx.part``: one line per finished segment, its end offset in the .ts.part
- ``E001.<playlist>.mp4.part``: the remuxed file, before its checks

Resuming cuts the .ts.part back to the last finished segment and goes on from
there. Encrypted streams (EXT-X-KEY other than NONE) are refused: this engine
only reads what the platform serves in the clear.
"""

from __future__ import annotations

import re
import subprocess
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable
from urllib.parse import urljoin, urlparse

from . import errors
from .download import DURATION_TOLERANCE_S, IntegrityError, UrlRejected, check_duration, finish
from .http import Http, HttpStatusError

REMUX_TIMEOUT_S = 600
_ATTR_RE = re.compile(r'([A-Z0-9-]+)=("[^"]*"|[^,]*)')

Remux = Callable[[Path, Path], None]  # (segments file, mp4 to write)


@dataclass
class Playlist:
    url: str
    segments: list[str] = field(default_factory=list)  # absolute URLs, in order
    durations: list[float] = field(default_factory=list)  # EXTINF, seconds
    init: str | None = None  # EXT-X-MAP (fragmented MP4 segments)

    @property
    def duration_ms(self) -> int:
        return round(sum(self.durations) * 1000)


def parse_attributes(text: str) -> dict[str, str]:
    return {k: v.strip('"') for k, v in _ATTR_RE.findall(text)}


def parse_playlist(text: str, url: str) -> Playlist | list[tuple[int, int, str]]:
    """A media playlist, or the variants of a master playlist as (height, bandwidth, url)."""
    lines = [line.strip() for line in text.splitlines() if line.strip()]
    if not lines or lines[0] != "#EXTM3U":
        raise IntegrityError("réponse qui n'est pas une playlist HLS", errors.HLS_UNSUPPORTED)
    variants: list[tuple[int, int, str]] = []
    playlist = Playlist(url)
    pending_variant: dict | None = None
    pending_duration: float | None = None
    for line in lines[1:]:
        if line.startswith("#EXT-X-STREAM-INF:"):
            pending_variant = parse_attributes(line.split(":", 1)[1])
        elif line.startswith("#EXT-X-KEY:"):
            method = parse_attributes(line.split(":", 1)[1]).get("METHOD", "NONE")
            if method != "NONE":
                raise IntegrityError(f"flux HLS chiffré ({method}) : non pris en charge", errors.HLS_UNSUPPORTED)
        elif line.startswith("#EXT-X-MAP:"):
            uri = parse_attributes(line.split(":", 1)[1]).get("URI")
            playlist.init = urljoin(url, uri) if uri else None
        elif line.startswith("#EXTINF:"):
            pending_duration = float(line.split(":", 1)[1].split(",", 1)[0] or 0)
        elif line.startswith("#"):
            continue
        elif pending_variant is not None:
            resolution = pending_variant.get("RESOLUTION", "")
            height = int(resolution.split("x")[1]) if "x" in resolution else 0
            variants.append((height, int(pending_variant.get("BANDWIDTH") or 0), urljoin(url, line)))
            pending_variant = None
        else:
            playlist.segments.append(urljoin(url, line))
            playlist.durations.append(pending_duration or 0.0)
            pending_duration = None
    if variants:
        return variants
    if not playlist.segments:
        raise IntegrityError("playlist HLS sans segment", errors.HLS_UNSUPPORTED)
    return playlist


def load_playlist(http: Http, url: str) -> Playlist:
    """The media playlist behind ``url``; for a master playlist, its best variant."""
    for _ in range(3):  # master -> media, never deeper in practice
        text = _get(http, url).decode("utf-8", errors="replace")
        parsed = parse_playlist(text, url)
        if isinstance(parsed, Playlist):
            return parsed
        url = max(parsed)[2]
    raise IntegrityError("playlists HLS imbriquées trop profondément", errors.HLS_UNSUPPORTED)


def download_hls(
    http: Http,
    url: str,
    dest: Path,
    expected_duration_ms: int | None = None,
    on_progress: Callable[[int, int], None] | None = None,
    tolerance_s: float = DURATION_TOLERANCE_S,
    remux: Remux | None = None,
    ffmpeg_path: str | None = None,
    rendition: str = "",
) -> int:
    """Download the episode behind ``url`` into ``dest`` (an MP4) and return its size.

    Without announced duration, the playlist's own total is checked instead.
    ``rendition`` (the quality) tells apart playlists whose URLs share a name
    (dramafren's ``/proxy?token=…``), so a resume never mixes two qualities.
    """
    playlist = load_playlist(http, url)
    name = ".".join(filter(None, (Path(urlparse(url).path).stem or "video", rendition)))
    ts = dest.with_name(f"{dest.stem}.{name}.ts.part")
    idx = dest.with_name(f"{dest.stem}.{name}.idx.part")
    mp4_part = dest.with_name(f"{dest.stem}.{name}.mp4.part")
    parts = ([playlist.init] if playlist.init else []) + playlist.segments

    offsets = _finished_offsets(idx, ts, len(parts))
    size = offsets[-1] if offsets else 0
    with ts.open("r+b" if ts.exists() else "wb") as out:
        out.truncate(size)  # drops a segment cut short by the last interruption
    idx.write_text("".join(f"{o}\n" for o in offsets), encoding="ascii")

    with ts.open("ab") as out, idx.open("a", encoding="ascii") as index:
        for i in range(len(offsets), len(parts)):
            chunk = _get(http, parts[i])
            out.write(chunk)
            out.flush()
            size += len(chunk)
            index.write(f"{size}\n")
            index.flush()
            if on_progress:
                done = i + 1
                on_progress(size, size * len(parts) // done if done < len(parts) else size)

    (remux or _ffmpeg_remux(ffmpeg_path))(ts, mp4_part)
    check_duration(mp4_part, expected_duration_ms or playlist.duration_ms, tolerance_s)
    return finish(mp4_part, dest)  # also removes the .ts.part and .idx.part


def _finished_offsets(idx: Path, ts: Path, count: int) -> list[int]:
    """End offsets of the segments already in the .ts.part (nothing usable: [])."""
    if not idx.exists() or not ts.exists():
        return []
    offsets: list[int] = []
    for line in idx.read_text(encoding="ascii", errors="replace").split():
        if not line.isdigit() or (offsets and int(line) <= offsets[-1]):
            break
        offsets.append(int(line))
    have = ts.stat().st_size
    offsets = [o for o in offsets if o <= have]
    return offsets if len(offsets) <= count else []  # another playlist: start over


def _get(http: Http, url: str) -> bytes:
    try:
        return http.get(url).body
    except HttpStatusError as e:
        if e.status in (401, 403, 404, 410):
            raise UrlRejected(str(e)) from None
        raise


def _ffmpeg_remux(ffmpeg_path: str | None) -> Remux:
    def remux(src: Path, dst: Path) -> None:
        from . import film  # ffmpeg discovery is shared with the film builder

        try:
            ffmpeg = film.find_ffmpeg(ffmpeg_path)
        except film.FilmError as e:
            raise IntegrityError(f"les épisodes HLS demandent ffmpeg. {e}", errors.FFMPEG_MISSING) from None
        args = [
            ffmpeg, "-hide_banner", "-loglevel", "error", "-nostdin", "-y", "-i", str(src),
            "-map", "0:v?", "-map", "0:a?", "-c", "copy", "-movflags", "+faststart", "-f", "mp4", str(dst),
        ]  # fmt: skip
        flags = subprocess.CREATE_NO_WINDOW if sys.platform == "win32" else 0
        try:
            proc = subprocess.run(args, capture_output=True, text=True, encoding="utf-8", errors="replace",
                                  timeout=REMUX_TIMEOUT_S, creationflags=flags)  # fmt: skip
        except (OSError, subprocess.TimeoutExpired) as e:
            dst.unlink(missing_ok=True)
            raise IntegrityError(f"ffmpeg n'a pas pu assembler l'épisode : {e}", errors.REMUX_FAILED) from None
        if proc.returncode != 0:
            dst.unlink(missing_ok=True)
            detail = (proc.stderr or "").strip().splitlines()[-1:] or ["erreur inconnue"]
            raise IntegrityError(f"ffmpeg n'a pas pu assembler l'épisode : {detail[0]}", errors.REMUX_FAILED)

    return remux
