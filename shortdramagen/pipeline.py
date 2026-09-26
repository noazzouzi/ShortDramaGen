"""Orchestration: metadata -> URL resolution -> parallel downloads."""

from __future__ import annotations

import threading
import time
from concurrent.futures import ThreadPoolExecutor, wait
from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable

from . import cdn, dramafren, official
from .download import IntegrityError, UrlRejected, check_duration, download
from .http import TRANSIENT_ERRORS, Http, HttpStatusError
from .manifest import Manifest
from .models import BookRef, Episode, Series, VideoSource, quality_from_text

Log = Callable[[str], None]
EpisodeRanges = list[tuple[int, int | None]]  # [(1, 10), (28, 28), (50, None)]; None = open end

MAX_ATTEMPTS = 3
MAX_PROBED_EPISODES = 1000
DEFAULT_API_INTERVAL = 0.3  # seconds between two dramafren API calls


class RateLimiter:
    """Spaces out calls to the dramafren API (politeness)."""

    def __init__(self, interval: float):
        self.interval = interval
        self._lock = threading.Lock()
        self._next = 0.0

    def wait(self) -> None:
        with self._lock:
            now = time.monotonic()
            delay = self._next - now
            self._next = max(now, self._next) + self.interval
        if delay > 0:
            time.sleep(delay)


@dataclass
class FetchOptions:
    out_dir: Path = Path("downloads")
    lang: str | None = None
    quality: str = "best"
    jobs: int = 3
    episodes: EpisodeRanges | None = None
    api_interval: float = DEFAULT_API_INTERVAL


@dataclass
class FetchResult:
    series: Series
    series_dir: Path
    done: list[int] = field(default_factory=list)
    skipped: list[int] = field(default_factory=list)
    failed: dict[int, str] = field(default_factory=dict)


# --- metadata -----------------------------------------------------------------


def load_series(
    http: Http, ref: BookRef, lang: str | None, log: Log, limiter: RateLimiter | None = None
) -> tuple[Series, dict]:
    """Official metadata, or probing dramafren when the official page is missing.

    Returns the series and the sources already obtained while probing.
    """
    lang = lang or ref.lang
    try:
        series = official.fetch_series(http, ref.book_id, lang)
    except official.SeriesNotFound as e:
        log(f"Attention : {e}. Détection des épisodes via dramafren (sans contrôle de durée).")
        return probe_series(http, ref.book_id, limiter or RateLimiter(DEFAULT_API_INTERVAL))
    if lang and series.languages and lang not in series.languages:
        log(
            f"Attention : langue « {lang} » indisponible pour cette série, version originale utilisée "
            f"(disponibles : {', '.join(series.languages)})"
        )
    return series, {}


def probe_series(http: Http, book_id: str, limiter: RateLimiter) -> tuple[Series, dict]:
    episodes: list[Episode] = []
    sources: dict[int, list[VideoSource]] = {}
    for number in range(1, MAX_PROBED_EPISODES + 1):
        limiter.wait()
        try:
            found = dramafren.get_video(http, book_id, number)
        except dramafren.ResolveError:
            break
        media_id = cdn.media_id_from_url(found[0].url) or ""
        episodes.append(Episode(number=number, chapter_id=media_id, media_id=media_id))
        sources[number] = found
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


# --- resolution ---------------------------------------------------------------


def resolve_episode(http: Http, series: Series, ep: Episode, limiter: RateLimiter | None = None) -> list[VideoSource]:
    """Every usable source for an episode.

    dramafren (all episodes, up to 1080p) plus the official free MP4
    (episodes 1-10, 720p). URLs that do not point at this episode are dropped.
    """
    sources: list[VideoSource] = []
    error = None
    try:
        if limiter:
            limiter.wait()
        sources = dramafren.get_video(http, series.source_book_id, ep.number)
    except dramafren.ResolveError as e:
        error = e
    if series.from_official:
        sources = [s for s in sources if cdn.matches_episode(s.url, series.source_book_id, ep.media_id)]
    if ep.free_url:
        sources.append(VideoSource(ep.free_url, quality_from_text(ep.free_url), "official"))
    if not sources:
        raise dramafren.ResolveError(str(error) if error else "aucune URL ne correspond à cet épisode")
    return sources


def rank_sources(sources: list[VideoSource], quality: str) -> list[VideoSource]:
    """The preferred source first, then the others as fallbacks (best quality first)."""
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


def select_episodes(series: Series, wanted: EpisodeRanges | None, log: Log) -> list[Episode]:
    if not wanted:
        return list(series.episodes)
    count = series.episode_count
    beyond = [
        str(a) if a == b else f"{a}-{b or ''}"
        for a, b in wanted
        if a > count or (b is not None and b > count)
    ]
    if beyond:
        log(f"Attention : la série compte {count} épisodes, ignoré au-delà : {', '.join(beyond)}")
    return [ep for ep in series.episodes if any(a <= ep.number and (b is None or ep.number <= b) for a, b in wanted)]


def series_dir_name(series: Series) -> str:
    name = f"{series.book_id}-{series.slug}"
    if series.source_book_id != series.book_id and series.lang:
        name += f"-{series.lang}"
    return name


# --- download -----------------------------------------------------------------


class Cancelled(Exception):
    pass


def fetch(http: Http, ref: BookRef, opts: FetchOptions, log: Log = print) -> FetchResult:
    limiter = RateLimiter(opts.api_interval)
    series, prefetched = load_series(http, ref, opts.lang, log, limiter)
    episodes = select_episodes(series, opts.episodes, log)
    series_dir = opts.out_dir / series_dir_name(series)
    series_dir.mkdir(parents=True, exist_ok=True)
    manifest = Manifest.open(series_dir, series)
    result = FetchResult(series, series_dir)
    counter = _Counter(len(episodes))
    stop = threading.Event()

    def check_stop(_written: int, _total: int) -> None:
        if stop.is_set():
            raise Cancelled()  # leaves the .part file for the next run

    log(f"« {series.title} » : {series.episode_count} épisodes -> {series_dir}")

    def process(ep: Episode) -> None:
        if stop.is_set():
            return
        dest = series_dir / f"E{ep.number:03d}.mp4"
        if dest.exists():
            try:
                check_duration(dest, ep.duration_ms)
                manifest.update(ep.number, status="done", file=dest.name, bytes=dest.stat().st_size)
                result.skipped.append(ep.number)
                log(f"[{counter.next()}] E{ep.number:03d} déjà présent")
                return
            except IntegrityError as e:
                log(f"[....] E{ep.number:03d} fichier existant invalide ({e}), nouveau téléchargement")

        error = "inconnue"
        for attempt in range(1, MAX_ATTEMPTS + 1):
            if stop.is_set():
                return
            try:
                sources = prefetched.pop(ep.number, None) or resolve_episode(http, series, ep, limiter)
            except dramafren.ResolveError as e:
                error = str(e)
                break  # both endpoints (with retries) already failed
            for source in rank_sources(sources, opts.quality):
                expires = cdn.expires_at(source.url)
                manifest.update(
                    ep.number,
                    status="downloading",
                    url=source.url,
                    quality=source.quality,
                    origin=source.origin,
                    url_expires_at=expires.isoformat() if expires else None,
                )
                try:
                    size = download(http, source.url, dest, ep.duration_ms, check_stop)
                except (UrlRejected, IntegrityError) as e:
                    error = f"{source.origin} {source.quality} : {e}"
                    continue  # this source is bad: try the next one
                except (HttpStatusError, *TRANSIENT_ERRORS) as e:
                    error = str(e)
                    break  # network trouble: wait, then start again from a fresh resolution
                manifest.update(ep.number, status="done", file=dest.name, bytes=size)
                result.done.append(ep.number)
                log(f"[{counter.next()}] E{ep.number:03d} {source.quality:>5} {size / 1e6:6.1f} Mo  OK")
                return
            if attempt < MAX_ATTEMPTS:
                time.sleep(2 * attempt)
        manifest.update(ep.number, status="failed", error=error)
        result.failed[ep.number] = error
        log(f"[{counter.next()}] E{ep.number:03d} ÉCHEC : {error}")

    pool = ThreadPoolExecutor(max_workers=max(1, opts.jobs))
    futures = [pool.submit(process, ep) for ep in episodes]
    try:
        pending = set(futures)
        while pending:  # short timeouts keep Ctrl+C responsive, Windows included
            _, pending = wait(pending, timeout=0.5)
    except KeyboardInterrupt:
        stop.set()
        pool.shutdown(wait=True, cancel_futures=True)
        raise
    pool.shutdown()
    for future in futures:
        future.result()  # surface unexpected errors (bugs), not download failures

    result.done.sort()
    result.skipped.sort()
    return result


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
