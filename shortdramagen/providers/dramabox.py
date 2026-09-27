"""DramaBox: metadata from dramaboxdb.com, videos from the dramafren API and the official free MP4.

See docs/01-etude-technique.md. The official page gives the chapter list and
durations; every URL returned by the source is checked against the episode's
CDN path, so a wrong answer can never be saved as another episode.
"""

from __future__ import annotations

import re
import threading
from datetime import datetime
from urllib.parse import ParseResult, parse_qs

from .. import cdn, dramafren, errors, official
from ..http import Http
from ..models import BookRef, Episode, Series, VideoSource, quality_from_text
from .base import Availability, Limiter, Provider

MAX_PROBED_EPISODES = 1000

_BOOK_ID = r"\d{8,14}"
# dramaboxdb.com/{locale?}/movie/{id}/..., /ep/{id}_{slug}/..., dramabox(app).com/drama/{id}/...
_PATH_RE = re.compile(
    rf"^/(?:(?P<locale>[a-zA-Z]{{2}}(?:-[a-zA-Z]{{2,4}})?)/)?"
    rf"(?:movie|drama|video|book)/(?P<id>{_BOOK_ID})(?:[/_?#]|$)"
)
_EP_PATH_RE = re.compile(
    rf"^/(?:(?P<locale>[a-zA-Z]{{2}}(?:-[a-zA-Z]{{2,4}})?)/)?ep/(?P<id>{_BOOK_ID})_"
)
_EP_NUMBER_RE = re.compile(r"_Episode-(\d+)", re.IGNORECASE)
_QUERY_KEYS = ("bookId", "book_id", "bid", "id")
_ANY_ID_RE = re.compile(r"(?<!\d)(4[12]\d{9})(?!\d)")


class DramaBox(Provider):
    name = "dramabox"
    label = "DramaBox"
    hosts = ("dramaboxdb.com", "dramabox.com", "dramaboxapp.com", "dramafren.org")
    home_url = official.BASE_URL + "/"
    source_urls = (dramafren.ENDPOINTS[0],)
    can_probe = True
    id_pattern = _BOOK_ID
    example_link = "https://www.dramaboxdb.com/movie/41000105199/one-night-to-forever"

    def parse_link(self, parsed: ParseResult) -> BookRef | None:
        """Official URLs, share links, dramafren URLs.

        Only official-site URLs carry a meaningful language: on dramafren the
        ``lang`` parameter does not change the video, so it is ignored.
        """
        host = (parsed.hostname or "").lower()
        for regex in (_EP_PATH_RE, _PATH_RE):
            m = regex.match(parsed.path)
            if m:
                locale = m.group("locale")
                lang = locale.lower() if locale and "dramaboxdb" in host else None
                ep = _EP_NUMBER_RE.search(parsed.path) if regex is _EP_PATH_RE else None
                return BookRef(m.group("id"), lang, int(ep.group(1)) if ep else None)

        query = parse_qs(parsed.query)
        episode = next((int(v) for v in query.get("ep", []) if v.isdigit()), None)
        for key in _QUERY_KEYS:
            for value in query.get(key, []):
                if re.fullmatch(_BOOK_ID, value):
                    return BookRef(value, episode=episode)

        m = _ANY_ID_RE.search(parsed.path + "?" + parsed.query)
        return BookRef(m.group(1)) if m else None

    def series_link(self, book_id: str, slug: str | None) -> str:
        return book_id

    def fetch_series(self, http: Http, ref: BookRef, lang: str | None) -> Series:
        return official.fetch_series(http, ref.book_id, lang)

    def resolve(
        self, http: Http, series: Series, ep: Episode, limiter: Limiter | None, stop: threading.Event | None
    ) -> list[VideoSource]:
        """dramafren (all episodes, up to 1080p) plus the official free MP4 (episodes 1-10, 720p).

        URLs that do not point at this episode are dropped.
        """
        sources: list[VideoSource] = []
        error = None
        try:
            if limiter:
                limiter.wait(stop)
            sources = dramafren.get_video(http, series.source_book_id, ep.number)
        except errors.ResolveError as e:
            error = e
        if series.from_official:
            sources = [s for s in sources if cdn.matches_episode(s.url, series.source_book_id, ep.media_id)]
        if ep.free_url:
            sources.append(VideoSource(ep.free_url, quality_from_text(ep.free_url), "official"))
        if not sources:
            if error:
                raise error
            raise errors.ResolveError("aucune URL ne correspond à cet épisode", errors.URL_MISMATCH)
        return sources

    def availability(
        self, http: Http, series: Series, limiter: Limiter | None, stop: threading.Event | None
    ) -> Availability:
        """The source is asked for the last episode (the most likely to be missing)."""
        try:
            if limiter:
                limiter.wait(stop)
            sources = dramafren.get_video(http, series.source_book_id, series.episodes[-1].number)
        except errors.ResolveError as e:
            return Availability(False, [], e)
        return Availability(True, [s.quality for s in sources])

    def probe_series(self, http: Http, ref: BookRef, limiter: Limiter, control) -> tuple[Series, dict]:
        """A series missing from the official site: episodes asked one by one until the source says no."""
        episodes: list[Episode] = []
        sources: dict[int, list[VideoSource]] = {}
        for number in range(1, MAX_PROBED_EPISODES + 1):
            limiter.wait(control.stop)
            try:
                found = dramafren.get_video(http, ref.book_id, number)
            except errors.ResolveError:
                break
            media_id = cdn.media_id_from_url(found[0].url) or ""
            episodes.append(Episode(number=number, chapter_id=media_id, media_id=media_id))
            sources[number] = found
            control.emit("probe_progress", found=number)
        if not episodes:
            raise errors.SeriesNotFound(
                f"Aucun épisode trouvé pour {ref.book_id}, ni sur le site officiel ni sur dramafren"
            )
        series = Series(
            book_id=ref.book_id,
            source_book_id=ref.book_id,
            lang="",
            title=ref.book_id,
            slug="serie",
            episodes=episodes,
            from_official=False,
        )
        return series, sources

    def probe_first(self, http: Http, ref: BookRef) -> list[VideoSource]:
        return dramafren.get_video(http, ref.book_id, 1)

    def expires_at(self, url: str) -> datetime | None:
        return cdn.expires_at(url)
