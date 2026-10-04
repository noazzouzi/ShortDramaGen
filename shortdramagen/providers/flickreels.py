"""FlickReels: series and videos from dramafren's FlickReels player (cdn-flickreels.dramafren.org).

The official site (www.flickreels.net) signs every call to its API with an MD5
of the parameters and a salt written in its JavaScript. This project does not
forge signatures (docs/01 §7), so the official metadata is not used: no
per-episode duration, each file is checked against its own playlist instead.

``flickreels.dramafren.org`` is behind the Cloudflare challenge;
``cdn-flickreels.dramafren.org`` serves the same PHP application without it.
Its detail page is the one of every player site (see ``player``). The watch
page (``page=watch&id={id}&ep={n}``) sets
``var availableQualities = [{"quality": "Default Auto", "url": …}]``, the HLS
playlist of the official CDN (``…/playlet-hls/{name}.m3u8?verify={unix}-{signature}``,
valid about two hours). Its segments are clear MPEG-TS of 10 s that need no
signature (1080×1920 on the series seen). Past the last episode the list is
empty. ``lang`` changes neither the title nor the video: each language
version has its own id.
"""

from __future__ import annotations

import re
import threading
from datetime import datetime, timezone
from urllib.parse import ParseResult, parse_qs, unquote, urlencode, urlparse

from .. import errors
from ..http import TRANSIENT_ERRORS, Http, HttpStatusError
from ..models import BookRef, Episode, Series, VideoSource, quality_from_text
from . import player
from .base import Availability, Limiter, Provider

PLAYER_URL = "https://cdn-flickreels.dramafren.org/index.php"
DRAMAFREN_HOSTS = ("flickreels.dramafren.org", "cdn-flickreels.dramafren.org")
TIMEOUT_S = 60.0  # about 1 s seen, but GoodShort's player took 45 s on a first call
_ID = r"\d{1,9}"
# /{lang}/episodes-list/{slug}-{id}, /movie/{slug}-{id}, /playlist/{slug}/{id}/episode-{n} (or /full-movie)
_PATH_RE = re.compile(
    rf"^/(?:[a-z]{{2}}(?:-[a-zA-Z]{{2,4}})?/)?(?:"
    rf"(?:episodes-list|movie)/(?:[^/]*-)?(?P<id>{_ID})"
    rf"|playlist/[^/]+/(?P<pid>{_ID})(?:/(?:episode-(?P<ep>\d{{1,4}})|full-movie))?"
    rf")/?$"
)
_QUALITIES_RE = re.compile(r"var availableQualities\s*=\s*")
_INITIAL_RE = re.compile(r"var initialVideoUrl\s*=\s*")


class FlickReels(Provider):
    name = "flickreels"
    label = "FlickReels"
    hosts = ("flickreels.net", *DRAMAFREN_HOSTS)
    home_url = "https://www.flickreels.net/"
    source_urls = (PLAYER_URL,)
    id_pattern = _ID
    example_link = "https://flickreels.dramafren.org/index.php?page=detail&id=9561&lang=fr"

    def parse_link(self, parsed: ParseResult) -> BookRef | None:
        """dramafren links (``id``, and ``ep`` counted from 1) and official links."""
        if (parsed.hostname or "").lower() in DRAMAFREN_HOSTS:
            return player.parse_link(parsed, _ID, self.name)
        m = _PATH_RE.match(unquote(parsed.path))
        if not m:
            return None
        episode = int(m.group("ep")) if m.group("ep") else None
        return BookRef(m.group("id") or m.group("pid"), episode=episode, provider=self.name)

    def series_link(self, book_id: str, slug: str | None) -> str:
        return f"{self.name}:{book_id}"

    def fetch_series(self, http: Http, ref: BookRef, lang: str | None) -> Series:
        page = _player_page(http, page="detail", id=ref.book_id)
        return player.parse_detail_page(page, ref.book_id, self.name, "dramafren (FlickReels)")

    def resolve(
        self, http: Http, series: Series, ep: Episode, limiter: Limiter | None, stop: threading.Event | None
    ) -> list[VideoSource]:
        if limiter:
            limiter.wait(stop)
        try:
            page = _player_page(http, page="watch", id=series.source_book_id, ep=ep.number)
        except (HttpStatusError, *TRANSIENT_ERRORS) as e:
            raise errors.ResolveError(f"pas de réponse de dramafren ({e})", errors.NETWORK) from None
        return parse_watch_page(page, ep.number)

    def availability(
        self, http: Http, series: Series, limiter: Limiter | None, stop: threading.Event | None
    ) -> Availability:
        """The player is asked for the last episode (the most likely to be missing)."""
        if not series.episodes:
            return Availability(False, [], errors.ResolveError("aucun épisode annoncé par dramafren"))
        try:
            sources = self.resolve(http, series, series.episodes[-1], limiter, stop)
        except errors.ResolveError as e:
            return Availability(False, [], e)
        return Availability(True, [s.quality for s in sources if s.quality])

    def expires_at(self, url: str) -> datetime | None:
        """``verify={unix}-{signature}``."""
        m = re.match(r"(\d+)-", parse_qs(urlparse(url).query).get("verify", [""])[0])
        return datetime.fromtimestamp(int(m.group(1)), tz=timezone.utc) if m else None


def _player_page(http: Http, **query) -> str:
    return http.get(f"{PLAYER_URL}?{urlencode(query)}", timeout=TIMEOUT_S).text()


def parse_watch_page(page: str, number: int) -> list[VideoSource]:
    """The playlists the player would play, best first."""
    qualities = player.json_after(_QUALITIES_RE, page)
    initial = player.json_after(_INITIAL_RE, page)
    if qualities is None and initial is None:
        raise errors.ResolveError(f"page du lecteur dramafren sans vidéo pour l'épisode {number}")
    sources: dict[str, VideoSource] = {}
    for q in qualities if isinstance(qualities, list) else []:
        url = q.get("url") if isinstance(q, dict) else None
        if isinstance(url, str) and url.startswith("https://"):
            sources[url] = VideoSource(url, quality_from_text(str(q.get("quality") or "")), "dramafren", "hls")
    if isinstance(initial, str) and initial.startswith("https://") and initial not in sources:
        sources[initial] = VideoSource(initial, "", "dramafren", "hls")
    if not sources:
        raise errors.ResolveError(f"Épisode {number} indisponible sur dramafren", errors.EP_UNAVAILABLE)
    return sorted(sources.values(), key=lambda s: s.height, reverse=True)
