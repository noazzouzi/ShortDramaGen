"""Orchestration: metadata -> URL resolution -> parallel downloads.

``fetch`` can be driven from outside through a ``FetchControl``: stop event,
shared rate limiter, forced re-downloads, strict quality and structured events.
The web interface will listen to the events; the CLI keeps its text log.

Events (``on_event(name, data)``, called from worker threads, so the handler
must be thread-safe):
- series_loaded, lang_fallback, probe_started, probe_progress, selection_clipped, cover_failed
- episode_skipped, episode_resolving, episode_started, episode_progress (at most 4 per second
  per episode), episode_source_rejected, quality_fallback, episode_retry, episode_done,
  episode_failed, episode_cancelled, disk_full
- fetch_finished
"""

from __future__ import annotations

import threading
import time
from concurrent.futures import ThreadPoolExecutor, wait
from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable

from . import cdn, dramafren, errors, official
from .download import IntegrityError, UrlRejected, check_duration, download
from .http import TRANSIENT_ERRORS, Http, HttpStatusError
from .inputs import EpisodeRanges
from .manifest import Listener, Manifest, now_iso
from .models import BookRef, Episode, Series, VideoSource, quality_from_text

Log = Callable[[str], None]
EventHandler = Callable[[str, dict], None]

MAX_ATTEMPTS = 3
RETRY_BASE_DELAY = 2.0  # seconds; attempt n waits n × this before the next one
MAX_PROBED_EPISODES = 1000
DEFAULT_API_INTERVAL = 0.3  # seconds between two dramafren API calls
PROGRESS_INTERVAL = 0.25  # seconds between two episode_progress events of one episode
BYTES_PER_EPISODE_1080P = 11_300_000  # measured average over 62 episodes (docs/01), for estimates
COVER_FILE = "cover.jpg"


class Cancelled(Exception):
    """The run was asked to stop (Ctrl+C or FetchControl.stop)."""


class RateLimiter:
    """Spaces out calls to the dramafren API (politeness). One can be shared by several runs."""

    def __init__(self, interval: float):
        self.interval = interval
        self._lock = threading.Lock()
        self._next = 0.0

    def wait(self, stop: threading.Event | None = None) -> None:
        with self._lock:
            now = time.monotonic()
            delay = self._next - now
            self._next = max(now, self._next) + self.interval
        if delay <= 0:
            return
        if stop is None:
            time.sleep(delay)
        elif stop.wait(delay):
            raise Cancelled()


@dataclass
class FetchOptions:
    out_dir: Path = Path("downloads")
    lang: str | None = None
    quality: str = "best"
    jobs: int = 3
    episodes: EpisodeRanges | None = None
    api_interval: float = DEFAULT_API_INTERVAL


@dataclass
class FetchControl:
    """How a caller drives a run. Every field is optional; the defaults behave like the CLI."""

    stop: threading.Event = field(default_factory=threading.Event)  # set it to stop cleanly
    limiter: RateLimiter | None = None  # shared between runs by a server
    force: frozenset[int] = frozenset()  # re-download these episodes even if present and valid
    strict_quality: bool = False  # never fall back to another quality (error quality_unavailable)
    on_event: EventHandler | None = None
    manifest_listener: Listener | None = None
    record_request: bool = True  # False for a repair: the manifest keeps what the user first asked for

    def emit(self, name: str, **data) -> None:
        if self.on_event:
            self.on_event(name, data)


@dataclass
class FetchResult:
    series: Series
    series_dir: Path
    done: list[int] = field(default_factory=list)
    skipped: list[int] = field(default_factory=list)
    failed: dict[int, str] = field(default_factory=dict)  # number -> message
    failed_codes: dict[int, str] = field(default_factory=dict)  # number -> errors.* code
    cancelled: bool = False  # stopped before the end; unfinished episodes are "pending"
    stop_reason: str | None = None  # "disk_full" when the engine stopped by itself


@dataclass
class Preview:
    """What a link points at, without downloading anything."""

    ref: BookRef
    series: Series
    available: bool  # the source answers for the last episode
    qualities: list[str]
    source_error: str | None = None
    source_error_code: str | None = None

    def estimated_bytes(self) -> dict[str, int]:
        # Only 1080p has a measured basis; other qualities are not estimated.
        return {"1080p": self.series.episode_count * BYTES_PER_EPISODE_1080P}

    def to_dict(self) -> dict:
        s = self.series
        durations = [ep.duration_ms / 1000 for ep in s.episodes if ep.duration_ms]
        return {
            "book_id": s.book_id,
            "source_book_id": s.source_book_id,
            "lang": s.lang,
            "is_original": s.source_book_id == s.book_id,
            "title": s.title,
            "title_vo": s.title_vo,
            "introduction": s.introduction,
            "cover_url": s.cover,
            "languages": s.languages,
            "from_official": s.from_official,
            "episode_count": s.episode_count,
            "episode_ref": self.ref.episode,
            "duration_s": round(sum(durations), 3) if durations else None,
            "episode_duration_s": {"min": min(durations), "max": max(durations)} if durations else None,
            "free_episodes": [ep.number for ep in s.episodes if ep.free_url],
            "availability": {
                "source": "ok" if self.available else "unavailable",
                "checked_episode": s.episodes[-1].number if s.episodes else None,
                "qualities": self.qualities,
                "error": self.source_error,
                "error_code": self.source_error_code,
            },
            "estimate": {q: {"bytes": b, "basis": "measured_average"} for q, b in self.estimated_bytes().items()},
        }


# --- metadata -----------------------------------------------------------------


def load_series(
    http: Http,
    ref: BookRef,
    lang: str | None,
    log: Log,
    limiter: RateLimiter | None = None,
    control: FetchControl | None = None,
) -> tuple[Series, dict]:
    """Official metadata, or probing dramafren when the official page is missing.

    Returns the series and the sources already obtained while probing.
    Raises Cancelled if the control is stopped during a probe.
    """
    control = control or FetchControl()
    lang = lang or ref.lang
    try:
        series = official.fetch_series(http, ref.book_id, lang)
    except official.SeriesNotFound as e:
        log(f"Attention : {e}. Détection des épisodes via dramafren (sans contrôle de durée).")
        control.emit("probe_started", book_id=ref.book_id)
        limiter = limiter or control.limiter or RateLimiter(DEFAULT_API_INTERVAL)
        return probe_series(http, ref.book_id, limiter, control)
    if lang and series.languages and lang not in series.languages:
        log(
            f"Attention : langue « {lang} » indisponible pour cette série, version originale utilisée "
            f"(disponibles : {', '.join(series.languages)})"
        )
        control.emit("lang_fallback", requested=lang, used=series.lang, available=series.languages)
    return series, {}


def probe_series(
    http: Http, book_id: str, limiter: RateLimiter, control: FetchControl | None = None
) -> tuple[Series, dict]:
    control = control or FetchControl()
    episodes: list[Episode] = []
    sources: dict[int, list[VideoSource]] = {}
    for number in range(1, MAX_PROBED_EPISODES + 1):
        limiter.wait(control.stop)
        try:
            found = dramafren.get_video(http, book_id, number)
        except dramafren.ResolveError:
            break
        media_id = cdn.media_id_from_url(found[0].url) or ""
        episodes.append(Episode(number=number, chapter_id=media_id, media_id=media_id))
        sources[number] = found
        control.emit("probe_progress", found=number)
    if not episodes:
        raise official.SeriesNotFound(f"Aucun épisode trouvé pour {book_id}, ni sur le site officiel ni sur dramafren")
    series = Series(
        book_id=book_id,
        source_book_id=book_id,
        lang="",
        title=book_id,
        slug="serie",
        episodes=episodes,
        from_official=False,
    )
    return series, sources


def preview_series(
    http: Http, ref: BookRef, lang: str | None = None, control: FetchControl | None = None
) -> Preview:
    """Official metadata plus one availability check on the last episode.

    Never probes and never writes anything: a series missing from the official
    site raises official.SeriesNotFound, and the caller decides whether to probe.
    """
    control = control or FetchControl()
    lang = lang or ref.lang
    series = official.fetch_series(http, ref.book_id, lang)
    if lang and series.languages and lang not in series.languages:
        control.emit("lang_fallback", requested=lang, used=series.lang, available=series.languages)
    try:
        if control.limiter:
            control.limiter.wait(control.stop)
        sources = dramafren.get_video(http, series.source_book_id, series.episodes[-1].number)
    except dramafren.ResolveError as e:
        return Preview(ref, series, False, [], str(e), errors.code_for(e))
    return Preview(ref, series, True, [s.quality for s in sources])


# --- resolution ---------------------------------------------------------------


def resolve_episode(
    http: Http,
    series: Series,
    ep: Episode,
    limiter: RateLimiter | None = None,
    stop: threading.Event | None = None,
) -> list[VideoSource]:
    """Every usable source for an episode.

    dramafren (all episodes, up to 1080p) plus the official free MP4
    (episodes 1-10, 720p). URLs that do not point at this episode are dropped.
    """
    sources: list[VideoSource] = []
    error = None
    try:
        if limiter:
            limiter.wait(stop)
        sources = dramafren.get_video(http, series.source_book_id, ep.number)
    except dramafren.ResolveError as e:
        error = e
    if series.from_official:
        sources = [s for s in sources if cdn.matches_episode(s.url, series.source_book_id, ep.media_id)]
    if ep.free_url:
        sources.append(VideoSource(ep.free_url, quality_from_text(ep.free_url), "official"))
    if not sources:
        if error:
            raise error
        raise dramafren.ResolveError("aucune URL ne correspond à cet épisode", errors.URL_MISMATCH)
    return sources


def rank_sources(sources: list[VideoSource], quality: str, strict: bool = False) -> list[VideoSource]:
    """The preferred source first, then the others as fallbacks (best quality first).

    ``strict``: only sources of exactly the requested quality, no fallback.
    """
    if strict and quality != "best":
        target = int(quality.rstrip("pP"))
        exact = [s for s in sources if s.height == target]
        if not exact:
            offered = ", ".join(sorted({s.quality for s in sources if s.quality}, reverse=True)) or "aucune"
            raise dramafren.ResolveError(
                f"qualité {quality} indisponible (proposées : {offered})", errors.QUALITY_UNAVAILABLE
            )
        return exact
    first = pick_source(sources, quality)
    rest = sorted((s for s in sources if s is not first), key=lambda s: s.height, reverse=True)
    return [first, *rest]


def pick_source(sources: list[VideoSource], quality: str) -> VideoSource:
    ordered = sorted(sources, key=lambda s: s.height, reverse=True)
    if quality == "best":
        return ordered[0]
    target = int(quality.rstrip("pP"))
    for source in ordered:
        if source.height <= target:
            return source
    return ordered[-1]


def _beyond(wanted: EpisodeRanges | None, count: int) -> list[str]:
    """The requested ranges that go past the last episode, as typed ("70-80", "90")."""
    return [
        str(a) if a == b else f"{a}-{b or ''}"
        for a, b in wanted or []
        if a > count or (b is not None and b > count)
    ]


def select_episodes(series: Series, wanted: EpisodeRanges | None, log: Log) -> list[Episode]:
    if not wanted:
        return list(series.episodes)
    count = series.episode_count
    beyond = _beyond(wanted, count)
    if beyond:
        log(f"Attention : la série compte {count} épisodes, ignoré au-delà : {', '.join(beyond)}")
    return [ep for ep in series.episodes if any(a <= ep.number and (b is None or ep.number <= b) for a, b in wanted)]


def series_dir_name(series: Series) -> str:
    name = f"{series.book_id}-{series.slug}"
    if series.source_book_id != series.book_id and series.lang:
        name += f"-{series.lang}"
    return name


# --- download -----------------------------------------------------------------


def fetch(
    http: Http, ref: BookRef, opts: FetchOptions, log: Log = print, control: FetchControl | None = None
) -> FetchResult:
    """Download the requested episodes of a series.

    Without ``control`` it behaves like the CLI: Ctrl+C stops cleanly and
    raises KeyboardInterrupt. With a control, setting ``control.stop`` ends the
    run early and returns a result with ``cancelled=True``; in both cases the
    unfinished episodes go back to "pending" and keep their .part for the next run.
    """
    control = control or FetchControl()
    limiter = control.limiter or RateLimiter(opts.api_interval)
    series, prefetched = load_series(http, ref, opts.lang, log, limiter, control)
    episodes = select_episodes(series, opts.episodes, log)
    ignored = _beyond(opts.episodes, series.episode_count)
    if ignored:
        control.emit("selection_clipped", episode_count=series.episode_count, ignored=ignored)
    series_dir = opts.out_dir / series_dir_name(series)
    series_dir.mkdir(parents=True, exist_ok=True)
    requested = {
        "lang": opts.lang or ref.lang,
        "quality": opts.quality,
        "episodes": [list(r) for r in opts.episodes] if opts.episodes else None,
        "at": now_iso(),
    }
    manifest = Manifest.open(series_dir, series, requested if control.record_request else None, control.manifest_listener)
    _ensure_cover(http, series, series_dir, manifest, control)
    result = FetchResult(series, series_dir)
    counter = _Counter(len(episodes))
    stop = control.stop

    log(f"« {series.title} » : {series.episode_count} épisodes -> {series_dir}")
    control.emit(
        "series_loaded",
        book_id=series.book_id,
        source_book_id=series.source_book_id,
        lang=series.lang,
        title=series.title,
        title_vo=series.title_vo,
        from_official=series.from_official,
        episode_count=series.episode_count,
        selected=[ep.number for ep in episodes],
        series_key=series_dir.name,
        series_dir=str(series_dir),
    )

    def progress_callback(n: int):
        last = [0.0]

        def on_progress(written: int, total: int) -> None:
            if stop.is_set():
                raise Cancelled()  # leaves the .part file for the next run
            if control.on_event:
                now = time.monotonic()
                if now - last[0] >= PROGRESS_INTERVAL or (total and written >= total):
                    last[0] = now
                    control.emit("episode_progress", n=n, bytes=written, total=total)

        return on_progress

    def cancelled(n: int) -> None:
        manifest.update(n, status="pending")
        control.emit("episode_cancelled", n=n)

    def process(ep: Episode) -> None:
        n = ep.number
        if stop.is_set():
            return
        dest = series_dir / f"E{n:03d}.mp4"
        if dest.exists() and n not in control.force:
            try:
                check_duration(dest, ep.duration_ms)
                size = dest.stat().st_size
                manifest.update(n, status="done", file=dest.name, bytes=size)
                result.skipped.append(n)
                control.emit("episode_skipped", n=n, bytes=size)
                log(f"[{counter.next()}] E{n:03d} déjà présent")
                return
            except IntegrityError as e:
                log(f"[....] E{n:03d} fichier existant invalide ({e}), nouveau téléchargement")

        error, code = "inconnue", errors.UNKNOWN
        for attempt in range(1, MAX_ATTEMPTS + 1):
            if stop.is_set():
                return cancelled(n)
            manifest.count_attempt(n)
            control.emit("episode_resolving", n=n, attempt=attempt)
            try:
                sources = prefetched.pop(n, None) or resolve_episode(http, series, ep, limiter, stop)
                ranked = rank_sources(sources, opts.quality, control.strict_quality)
            except Cancelled:
                return cancelled(n)
            except dramafren.ResolveError as e:
                error, code = str(e), errors.code_for(e)
                break  # both endpoints (with retries) already failed, or the quality does not exist
            wanted = opts.quality if opts.quality != "best" else ranked[0].quality
            for source in ranked:
                expires = cdn.expires_at(source.url)
                manifest.update(
                    n,
                    status="downloading",
                    url=source.url,
                    quality=source.quality,
                    origin=source.origin,
                    url_expires_at=expires.isoformat() if expires else None,
                )
                control.emit("episode_started", n=n, quality=source.quality, origin=source.origin, attempt=attempt)
                try:
                    size = download(http, source.url, dest, ep.duration_ms, progress_callback(n))
                except Cancelled:
                    return cancelled(n)
                except (UrlRejected, IntegrityError) as e:
                    error, code = f"{source.origin} {source.quality} : {e}", errors.code_for(e)
                    control.emit(
                        "episode_source_rejected", n=n, quality=source.quality, origin=source.origin,
                        code=code, message=str(e),
                    )  # fmt: skip
                    continue  # this source is bad: try the next one
                except (HttpStatusError, *TRANSIENT_ERRORS) as e:
                    error, code = str(e), errors.code_for(e)
                    if code == errors.DISK_FULL:
                        manifest.update(n, status="pending")
                        result.stop_reason = errors.DISK_FULL
                        stop.set()  # every other episode would fail the same way
                        control.emit("disk_full", n=n, message=error)
                        log(f"Téléchargements arrêtés : disque plein ({error}).")
                        return
                    break  # network trouble: wait, then start again from a fresh resolution
                fallback = source.quality != wanted
                manifest.update(
                    n, status="done", file=dest.name, bytes=size, quality_requested=wanted if fallback else None
                )
                if fallback:
                    control.emit("quality_fallback", n=n, requested=wanted, got=source.quality)
                result.done.append(n)
                control.emit("episode_done", n=n, bytes=size, quality=source.quality, origin=source.origin)
                log(f"[{counter.next()}] E{n:03d} {source.quality:>5} {size / 1e6:6.1f} Mo  OK")
                return
            if attempt < MAX_ATTEMPTS:
                delay = RETRY_BASE_DELAY * attempt
                control.emit("episode_retry", n=n, attempt=attempt, delay=delay, code=code, message=error)
                if stop.wait(delay):
                    return cancelled(n)
        manifest.update(n, status="failed", error=error, error_code=code)
        result.failed[n] = error
        result.failed_codes[n] = code
        control.emit("episode_failed", n=n, code=code, message=error)
        log(f"[{counter.next()}] E{n:03d} ÉCHEC : {error}")

    pool = ThreadPoolExecutor(max_workers=max(1, opts.jobs))
    futures = [pool.submit(process, ep) for ep in episodes]
    try:
        pending = set(futures)
        while pending:  # short timeouts keep Ctrl+C responsive, Windows included
            _, pending = wait(pending, timeout=0.5)
            if stop.is_set():
                break
    except KeyboardInterrupt:
        stop.set()
        pool.shutdown(wait=True, cancel_futures=True)
        raise
    pool.shutdown(wait=True, cancel_futures=True)  # after a stop: running episodes end within a chunk
    for future in futures:
        if not future.cancelled():
            future.result()  # surface unexpected errors (bugs), not download failures

    result.done.sort()
    result.skipped.sort()
    result.cancelled = stop.is_set()
    control.emit(
        "fetch_finished",
        done=result.done,
        skipped=result.skipped,
        failed=result.failed_codes,
        cancelled=result.cancelled,
        stop_reason=result.stop_reason,
    )
    return result


def _ensure_cover(http: Http, series: Series, series_dir: Path, manifest: Manifest, control: FetchControl) -> None:
    """cover.jpg next to the episodes, so a library can be shown offline."""
    cover = series_dir / COVER_FILE
    if series.cover and not cover.exists():
        try:
            official.download_cover(http, series.cover, cover)
        except (HttpStatusError, ValueError, *TRANSIENT_ERRORS) as e:
            control.emit("cover_failed", message=str(e))
    if cover.exists() and manifest.data.get("cover_file") != COVER_FILE:
        manifest.set("cover_file", COVER_FILE)


def resolve_links(http: Http, ref: BookRef, opts: FetchOptions, log: Log = print) -> tuple[Series, list[dict]]:
    """Resolve without downloading (for external tools such as aria2c or IDM)."""
    limiter = RateLimiter(opts.api_interval)
    series, prefetched = load_series(http, ref, opts.lang, log, limiter)
    links = []
    for ep in select_episodes(series, opts.episodes, log):
        try:
            sources = prefetched.get(ep.number) or resolve_episode(http, series, ep, limiter)
        except dramafren.ResolveError as e:
            log(f"E{ep.number:03d} ÉCHEC : {e}")
            continue
        source = pick_source(sources, opts.quality)
        expires = cdn.expires_at(source.url)
        links.append(
            {
                "episode": ep.number,
                "file": f"E{ep.number:03d}.mp4",
                "quality": source.quality,
                "url": source.url,
                "expires_at": expires.isoformat() if expires else None,
            }
        )
    return series, links


class _Counter:
    def __init__(self, total: int):
        self.total = total
        self._n = 0
        self._lock = threading.Lock()

    def next(self) -> str:
        with self._lock:
            self._n += 1
            width = len(str(self.total))
            return f"{self._n:>{width}}/{self.total}"
