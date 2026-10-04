"""ShortMax: series from the ShortMax player (shortmax.ngeshorts.fun), videos from its video_server API.

The player (a copy of dramafren's, see ``player``) answers without challenge on
shortmax.ngeshorts.fun; shortmax.dramafren.org is behind the Cloudflare
challenge. The official site (www.shortmax.com, now www.shorttv.live) uses the
same ids but publishes no per-episode duration: each file is checked against
its own playlist.

Videos: the watch page asks ``index.php?action=video_server&server={server1|server2}
&id={id}&ep={n}&lang=…&stale=1`` on ``videoServerEndpoints`` (cdn-shortmaxv3 and
cdn-shortmaxv5.dramafren.org, then the player itself), and takes the first
``{"ok": true, "server": {…}}``. ``server.qualities`` lists
``{"quality": "1080p", "url": …}`` (1080p, 720p, 480p): HLS playlists of the
official CDN (akamai-static.shorttv.live/hls/{uuid}_{height}/main.m3u8?auth_key=…),
whose segments are clear MPEG-TS of 10 s that need no signature. An unknown
id or an episode past the last one answers ``{"ok": false, "message": "Server unavailable"}``.
"""

from __future__ import annotations

import re
import threading
from urllib.parse import ParseResult, unquote, urlencode

from .. import errors
from ..http import TRANSIENT_ERRORS, Http, HttpStatusError
from ..models import BookRef, Episode, Series, VideoSource, quality_from_text
from . import player
from .base import Availability, Limiter, Provider

PLAYER_URL = "https://shortmax.ngeshorts.fun/index.php"
PLAYER_HOSTS = ("shortmax.ngeshorts.fun", "shortmax.dramafren.org")  # the second one: links only
VIDEO_ENDPOINTS = (
    "https://cdn-shortmaxv3.dramafren.org/index.php",
    "https://cdn-shortmaxv5.dramafren.org/index.php",
    PLAYER_URL,  # the player's own fallback, slower (8 s seen)
)
SERVERS = ("server1", "server2")  # "Primary", then "Backup"
TIMEOUT_S = 60.0
_ID = r"\d{1,9}"
# /{lang}/drama/{slug}-{id}, /{lang}/episode/{slug}-{id}-{n}
_PATH_RE = re.compile(
    rf"^/(?:[a-z]{{2}}(?:-[a-zA-Z]{{2,4}})?/)?(?:"
    rf"drama/(?:[^/]*-)?(?P<id>{_ID})"
    rf"|episode/(?:[^/]*-)?(?P<eid>{_ID})-(?P<ep>\d{{1,4}})"
    rf")/?$"
)


class ShortMax(Provider):
    name = "shortmax"
    label = "ShortMax"
    hosts = ("shorttv.live", "shortmax.com", *PLAYER_HOSTS)
    home_url = "https://www.shorttv.live/"
    source_urls = (VIDEO_ENDPOINTS[0], PLAYER_URL)
    id_pattern = _ID
    example_link = "https://shortmax.ngeshorts.fun/index.php?page=detail&id=24403&lang=fr"

    def parse_link(self, parsed: ParseResult) -> BookRef | None:
        """Player links (``id``, and ``ep`` counted from 1) and official links."""
        if (parsed.hostname or "").lower() in PLAYER_HOSTS:
            return player.parse_link(parsed, _ID, self.name)
        m = _PATH_RE.match(unquote(parsed.path))
        if not m:
            return None
        episode = int(m.group("ep")) if m.group("ep") else None
        return BookRef(m.group("id") or m.group("eid"), episode=episode, provider=self.name)

    def series_link(self, book_id: str, slug: str | None) -> str:
        return f"{self.name}:{book_id}"

    def fetch_series(self, http: Http, ref: BookRef, lang: str | None) -> Series:
        page = http.get(f"{PLAYER_URL}?{urlencode({'page': 'detail', 'id': ref.book_id})}", timeout=TIMEOUT_S).text()
        return player.parse_detail_page(page, ref.book_id, self.name, "le lecteur ShortMax")

    def resolve(
        self, http: Http, series: Series, ep: Episode, limiter: Limiter | None, stop: threading.Event | None
    ) -> list[VideoSource]:
        if limiter:
            limiter.wait(stop)
        return get_video(http, series.source_book_id, ep.number)

    def availability(
        self, http: Http, series: Series, limiter: Limiter | None, stop: threading.Event | None
    ) -> Availability:
        """The API is asked for the last episode (the most likely to be missing)."""
        if not series.episodes:
            return Availability(False, [], errors.ResolveError("aucun épisode annoncé par le lecteur ShortMax"))
        try:
            sources = self.resolve(http, series, series.episodes[-1], limiter, stop)
        except errors.ResolveError as e:
            return Availability(False, [], e)
        return Availability(True, [s.quality for s in sources if s.quality])


def get_video(http: Http, book_id: str, episode: int) -> list[VideoSource]:
    """Every quality of one episode, best first.

    Each server is asked on the endpoints in turn: a network error moves to the
    next endpoint, a refusal to the next server (the endpoints share one backend).
    """
    problems = []
    refused = False
    for server in SERVERS:
        query = urlencode({"action": "video_server", "server": server, "id": book_id, "ep": episode, "stale": 1})
        for endpoint in VIDEO_ENDPOINTS:
            try:
                data = http.get_json(f"{endpoint}?{query}", timeout=TIMEOUT_S)
            except (HttpStatusError, ValueError, *TRANSIENT_ERRORS) as e:
                problems.append(f"{server} {endpoint.split('/')[2]} : {e}")
                continue
            if isinstance(data, dict) and data.get("ok") and isinstance(data.get("server"), dict):
                sources = parse_server(data["server"])
                if sources:
                    return sources
            refused = True
            problems.append(f"{server} : {(data.get('message') if isinstance(data, dict) else None) or 'réponse invalide'}")
            break
    raise errors.ResolveError(
        f"Épisode {episode} indisponible sur le lecteur ShortMax ({'; '.join(problems)})",
        errors.EP_UNAVAILABLE if refused else errors.NETWORK,
    )


def parse_server(server: dict) -> list[VideoSource]:
    """``qualities`` (direct CDN URLs, not dramafren's ``proxyUrl``), plus ``playUrl`` if missing from them."""
    sources: dict[str, VideoSource] = {}
    for q in server.get("qualities") or []:
        url = q.get("url") if isinstance(q, dict) else None
        if isinstance(url, str) and url.startswith("https://"):
            sources[url] = VideoSource(url, quality_from_text(str(q.get("quality") or "")), "dramafren", "hls")
    main = server.get("playUrl")
    if isinstance(main, str) and main.startswith("https://") and main not in sources:
        sources[main] = VideoSource(main, "", "dramafren", "hls")
    return sorted(sources.values(), key=lambda s: s.height, reverse=True)
