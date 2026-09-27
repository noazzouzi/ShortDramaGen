"""GoodShort: everything comes from the official site www.goodshort.com, free episodes only.

A series page (/drama/{slug}-{bookId}) embeds its state as
``window.__INITIAL_STATE__`` (a JSON object). ``BookInfoModule.book`` holds the
title, cover, synopsis, language and ``chapterCount``; ``chapterVoList`` holds
the first chapters (11 on the pages seen) with their duration (``playTime``,
seconds) and, for the free ones (``price`` 0), a signed HLS playlist
(``m3u8Path``, ``expiredTime`` about two weeks ahead). The playlist is a single
rendition of clear MPEG-TS segments, which need no signature. Paid episodes are
listed but never downloaded.
"""

from __future__ import annotations

import json
import re
import threading
from datetime import datetime, timedelta, timezone
from urllib.parse import ParseResult, parse_qs, urlparse

from .. import errors
from ..http import Http, HttpStatusError
from ..models import LANGUAGE_CODES, BookRef, Episode, Series, VideoSource
from .base import Availability, Limiter, Provider, free_sources

BASE_URL = "https://www.goodshort.com"
_BOOK_ID = r"\d{8,14}"
# /drama/{slug}-{id}, /episodes/{slug}-{id}, /episode/{slug}-{id}/{NNN}-{chapterId}
_PATH_RE = re.compile(
    rf"^/(?:[a-z]{{2}}(?:-[a-zA-Z]{{2,4}})?/)?(?:drama|episodes|episode)/"
    rf"(?:(?P<slug>[^/]*?)-)?(?P<id>{_BOOK_ID})(?:/(?P<ep>\d{{1,4}})-\d+)?/?$"
)
_STATE_RE = re.compile(r"window\.__INITIAL_STATE__\s*=\s*")
URL_REFRESH_MARGIN = timedelta(minutes=5)


class GoodShort(Provider):
    name = "goodshort"
    label = "GoodShort"
    hosts = ("goodshort.com",)
    home_url = BASE_URL + "/"
    id_pattern = _BOOK_ID
    example_link = "https://www.goodshort.com/drama/perfect-love-31000662271"

    def parse_link(self, parsed: ParseResult) -> BookRef | None:
        m = _PATH_RE.match(parsed.path)
        if not m:
            return None
        episode = int(m.group("ep")) if m.group("ep") else None
        return BookRef(m.group("id"), episode=episode, provider=self.name, slug=m.group("slug") or None)

    def series_link(self, book_id: str, slug: str | None) -> str:
        return f"{BASE_URL}/drama/{slug}-{book_id}" if slug else f"{self.name}:{book_id}"

    def series_url(self, book_id: str, slug: str | None) -> str:
        # Without the slug the site is expected to redirect to the canonical page (not verified yet).
        return f"{BASE_URL}/drama/{slug}-{book_id}" if slug else f"{BASE_URL}/drama/{book_id}"

    def fetch_series(self, http: Http, ref: BookRef, lang: str | None) -> Series:
        url = self.series_url(ref.book_id, ref.slug)
        try:
            resp = http.get(url)
        except HttpStatusError as e:
            if e.status in (404, 410):
                raise errors.SeriesNotFound(f"Série {ref.book_id} introuvable sur {BASE_URL}") from None
            raise
        return parse_series_page(resp.text(), ref.book_id)

    def resolve(
        self, http: Http, series: Series, ep: Episode, limiter: Limiter | None, stop: threading.Event | None
    ) -> list[VideoSource]:
        if ep.free_url and _expired(ep.free_url):
            fresh = self.fetch_series(http, BookRef(series.book_id, provider=self.name, slug=series.slug), None)
            ep.free_url = next((e.free_url for e in fresh.episodes if e.number == ep.number), None)
        return free_sources(series, ep)

    def availability(
        self, http: Http, series: Series, limiter: Limiter | None, stop: threading.Event | None
    ) -> Availability:
        if series.free_numbers:
            return Availability(True, [])
        return Availability(False, [], errors.ResolveError("aucun épisode gratuit sur le site officiel"))

    def expires_at(self, url: str) -> datetime | None:
        return _expires_at(url)


def parse_series_page(html: str, book_id: str) -> Series:
    m = _STATE_RE.search(html)
    if not m:
        raise errors.SeriesNotFound(f"Pas de données de page pour la série GoodShort {book_id}")
    try:
        state, _ = json.JSONDecoder().raw_decode(html, m.end())
    except ValueError:
        raise errors.SeriesNotFound(f"Données illisibles pour la série GoodShort {book_id}") from None
    return parse_state(state, book_id)


def parse_state(state: dict, book_id: str) -> Series:
    module = state.get("BookInfoModule") or {}
    book = module.get("book") or {}
    if state.get("NotFound404Staus") or state.get("NotFound410Staus") or module.get("nullBook") or not book.get("bookId"):
        raise errors.SeriesNotFound(f"Série {book_id} introuvable sur {BASE_URL}")
    chapters = {}
    for ch in module.get("chapterVoList") or []:
        if isinstance(ch, dict) and isinstance(ch.get("index"), int):
            chapters[ch["index"] + 1] = ch
    count = max(int(book.get("chapterCount") or 0), max(chapters, default=0))
    episodes = []
    for number in range(1, count + 1):
        ch = chapters.get(number, {})
        play = ch.get("playTime")
        chapter_id = str(ch.get("id") or "")
        episodes.append(
            Episode(
                number=number,
                chapter_id=chapter_id,
                media_id=chapter_id,
                duration_ms=round(play * 1000) if isinstance(play, (int, float)) and play > 0 else None,
                free_url=ch.get("m3u8Path") or None,
            )
        )
    resource = str(book.get("bookResourceUrl") or "")
    real_id = str(book.get("bookId"))
    slug = resource[: -len(real_id) - 1] if resource.endswith("-" + real_id) else ""
    title = str(book.get("bookName") or book.get("seoBookName") or real_id)
    return Series(
        book_id=real_id,
        source_book_id=real_id,
        lang=LANGUAGE_CODES.get(str(book.get("language") or "").upper(), "en"),
        title=title,
        slug=slug or "serie",
        episodes=episodes,
        cover=book.get("cover") or None,
        introduction=book.get("introduction") or "",
        title_vo=title,
        provider=GoodShort.name,
        free_only=True,
        free_url_kind="hls",
        # playTime is a whole number of seconds: the file may be up to a second longer
        duration_tolerance_s=1.5,
    )


def _expires_at(url: str) -> datetime | None:
    value = parse_qs(urlparse(url).query).get("expiredTime", [""])[0]
    return datetime.fromtimestamp(int(value), tz=timezone.utc) if value.isdigit() else None


def _expired(url: str) -> bool:
    expires = _expires_at(url)
    return expires is not None and expires - URL_REFRESH_MARGIN <= datetime.now(timezone.utc)
