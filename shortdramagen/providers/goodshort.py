"""GoodShort: metadata from the official site www.goodshort.com, videos from dramafren.

Metadata. A series page (/drama/{slug}-{bookId}) embeds its state as
``window.__INITIAL_STATE__`` (a JSON object). ``BookInfoModule.book`` holds the
title, cover, synopsis, language and ``chapterCount``; ``chapterVoList`` holds
only the first chapters (11 on the pages seen). The page answers 404 unless the
slug is exactly the site's own: without it (``goodshort:{id}``, dramafren
links), the same data comes from the API the site's pages call, which only
needs the id. Every chapter (its ``id``, its duration ``playTime`` in seconds
and, for the free ones, a signed HLS playlist ``m3u8Path`` with ``expiredTime``
about two weeks ahead) comes from a second API, ``chapter/page``.

Videos. dramafren serves every episode, free or paid, in 1080p, 720p and 540p,
from the book id and the chapter id (see ``dramafren.get_goodshort_video``). The
official playlist of a free episode (720p) is kept as a last resort. Both are
single renditions of clear MPEG-TS segments.
"""

from __future__ import annotations

import json
import re
import threading
from datetime import datetime, timedelta, timezone
from urllib.parse import ParseResult, parse_qs, quote, unquote, urlparse

from .. import dramafren, errors
from ..http import TRANSIENT_ERRORS, Http, HttpStatusError
from ..models import LANGUAGE_CODES, BookRef, Episode, Series, VideoSource
from .base import Availability, Limiter, Provider, ascii_slug

BASE_URL = "https://www.goodshort.com"
BOOK_API_URL = BASE_URL + "/hwycreels/book/detail"  # POST {"bookId": …} -> {"status": 0, "data": {book, chapterVoList…}}
CHAPTERS_API_URL = BASE_URL + "/hwycreels/chapter/page"  # POST {"bookId", "pageNo", "pageSize"} -> {"data": {records…}}
CHAPTERS_PAGE_SIZE = 200  # 61 chapters came back in one page of 500
MAX_CHAPTER_PAGES = 20
# index.php?page=detail&id={bookId} (or page=watch&…&ep={index}); the cdn- host serves the same pages
DRAMAFREN_HOSTS = ("goodshort.dramafren.org", "cdn-goodshort.dramafren.org")
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
    hosts = ("goodshort.com", *DRAMAFREN_HOSTS)
    home_url = BASE_URL + "/"
    source_urls = (dramafren.GOODSHORT_ENDPOINT,)
    id_pattern = _BOOK_ID
    example_link = "https://www.goodshort.com/drama/perfect-love-31000662271"

    def parse_link(self, parsed: ParseResult) -> BookRef | None:
        """Official links, and dramafren links.

        On dramafren, ``id`` is the GoodShort id and ``ep`` the chapter's index
        (0 for the first episode). Its ``slug`` is dramafren's own, not the
        site's, and its ``lang`` changes nothing: each language version has its own id.
        """
        if (parsed.hostname or "").lower() in DRAMAFREN_HOSTS:
            query = parse_qs(parsed.query)
            book_id = next((v for v in query.get("id", []) if re.fullmatch(_BOOK_ID, v)), None)
            episode = next((int(v) + 1 for v in query.get("ep", []) if v.isdigit()), None)
            return BookRef(book_id, episode=episode, provider=self.name) if book_id else None
        m = _PATH_RE.match(parsed.path)
        if not m:
            return None
        episode = int(m.group("ep")) if m.group("ep") else None
        return BookRef(m.group("id"), episode=episode, provider=self.name, slug=unquote(m.group("slug") or "") or None)

    def series_link(self, book_id: str, slug: str | None) -> str:
        # The id is enough, and the stored slug (made ASCII for folder names) may not be the site's.
        return f"{self.name}:{book_id}"

    def series_url(self, book_id: str, slug: str) -> str:
        return f"{BASE_URL}/drama/{quote(slug)}-{book_id}"

    def fetch_series(self, http: Http, ref: BookRef, lang: str | None) -> Series:
        """The series page when the link gives a slug, else (or if the slug is not the site's) the API;
        then every chapter."""
        chapters = fetch_chapters(http, ref.book_id)
        if ref.slug:
            try:
                page = http.get(self.series_url(ref.book_id, ref.slug)).text()
                return parse_series_page(page, ref.book_id, chapters)
            except HttpStatusError as e:
                if e.status not in (404, 410):
                    raise
        return fetch_book(http, ref.book_id, chapters)

    def resolve(
        self, http: Http, series: Series, ep: Episode, limiter: Limiter | None, stop: threading.Event | None
    ) -> list[VideoSource]:
        """dramafren (every episode, up to 1080p), plus the official playlist of a free episode (720p)."""
        sources: list[VideoSource] = []
        error = errors.ResolveError(f"épisode {ep.number} absent de la liste des chapitres du site officiel")
        if ep.chapter_id:
            try:
                if limiter:
                    limiter.wait(stop)
                sources = dramafren.get_goodshort_video(http, series.source_book_id, ep.chapter_id, series.lang)
            except errors.ResolveError as e:
                error = e
        free_url = _free_url(http, series, ep)
        if free_url:
            sources.append(VideoSource(free_url, "", "official", series.free_url_kind))
        if not sources:
            raise error
        return sources

    def availability(
        self, http: Http, series: Series, limiter: Limiter | None, stop: threading.Event | None
    ) -> Availability:
        """dramafren is asked for the last episode (the most likely to be missing)."""
        last = series.episodes[-1] if series.episodes else None
        if not last or not last.chapter_id:
            return Availability(False, [], errors.ResolveError("liste des chapitres incomplète sur le site officiel"))
        try:
            if limiter:
                limiter.wait(stop)
            sources = dramafren.get_goodshort_video(http, series.source_book_id, last.chapter_id, series.lang)
        except errors.ResolveError as e:
            return Availability(False, [], e)
        return Availability(True, [s.quality for s in sources if s.quality])

    def expires_at(self, url: str) -> datetime | None:
        return _expires_at(url)


def fetch_book(http: Http, book_id: str, chapters: list[dict] | None = None) -> Series:
    """The series from the API behind the pages: same ``book`` and ``chapterVoList`` as the page state.

    An unknown id still answers ``status`` 0, with only ``seo404Vo`` in ``data``.
    """
    try:
        answer = http.post_json(BOOK_API_URL, {"bookId": book_id})
    except HttpStatusError as e:
        if e.status in (404, 410):
            raise errors.SeriesNotFound(f"Série {book_id} introuvable sur {BASE_URL}") from None
        raise
    data = answer.get("data") if isinstance(answer, dict) and answer.get("status") == 0 else None
    if not isinstance(data, dict):
        raise errors.SeriesNotFound(f"Série {book_id} introuvable sur {BASE_URL}")
    return parse_state({"BookInfoModule": data}, book_id, chapters)


def fetch_chapters(http: Http, book_id: str) -> list[dict]:
    """Every chapter of a series, from the API behind the episode lists (the pages embed only the first ones).

    An unknown id answers ``status`` 12000 ("Book not exists"): no chapter.
    """
    chapters: list[dict] = []
    for page in range(1, MAX_CHAPTER_PAGES + 1):
        answer = http.post_json(CHAPTERS_API_URL, {"bookId": book_id, "pageNo": page, "pageSize": CHAPTERS_PAGE_SIZE})
        data = answer.get("data") if isinstance(answer, dict) and answer.get("status") == 0 else None
        records = data.get("records") if isinstance(data, dict) else None
        if not isinstance(records, list):
            break
        chapters += [r for r in records if isinstance(r, dict)]
        pages = data.get("pages")
        if not records or not isinstance(pages, int) or page >= pages:
            break
    return chapters


def parse_series_page(html: str, book_id: str, chapters: list[dict] | None = None) -> Series:
    m = _STATE_RE.search(html)
    if not m:
        raise errors.SeriesNotFound(f"Pas de données de page pour la série GoodShort {book_id}")
    try:
        state, _ = json.JSONDecoder().raw_decode(html, m.end())
    except ValueError:
        raise errors.SeriesNotFound(f"Données illisibles pour la série GoodShort {book_id}") from None
    return parse_state(state, book_id, chapters)


def parse_state(state: dict, book_id: str, chapters: list[dict] | None = None) -> Series:
    """``chapters``: the full list from ``fetch_chapters``, over the few chapters the state embeds."""
    module = state.get("BookInfoModule") or {}
    book = module.get("book") or {}
    if state.get("NotFound404Staus") or state.get("NotFound410Staus") or module.get("nullBook") or not book.get("bookId"):
        raise errors.SeriesNotFound(f"Série {book_id} introuvable sur {BASE_URL}")
    by_number = {}
    for ch in [*(module.get("chapterVoList") or []), *(chapters or [])]:
        if isinstance(ch, dict) and isinstance(ch.get("index"), int):
            by_number[ch["index"] + 1] = ch
    count = max(int(book.get("chapterCount") or 0), max(by_number, default=0))
    episodes = []
    for number in range(1, count + 1):
        ch = by_number.get(number, {})
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
    slug = ascii_slug(resource[: -len(real_id) - 1]) if resource.endswith("-" + real_id) else ""
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
        free_url_kind="hls",
        # playTime is a whole number of seconds: the file may be up to a second longer
        duration_tolerance_s=1.5,
    )


def _free_url(http: Http, series: Series, ep: Episode) -> str | None:
    """The official playlist of a free episode, read again if its signature expires soon (series loaded long ago)."""
    if not ep.free_url or not _expired(ep.free_url):
        return ep.free_url
    try:
        fresh = {ch.get("index"): ch for ch in fetch_chapters(http, series.book_id)}
    except (HttpStatusError, ValueError, *TRANSIENT_ERRORS):
        return None  # dramafren's sources remain
    ep.free_url = (fresh.get(ep.number - 1) or {}).get("m3u8Path") or None
    return ep.free_url


def _expires_at(url: str) -> datetime | None:
    value = parse_qs(urlparse(url).query).get("expiredTime", [""])[0]
    return datetime.fromtimestamp(int(value), tz=timezone.utc) if value.isdigit() else None


def _expired(url: str) -> bool:
    expires = _expires_at(url)
    return expires is not None and expires - URL_REFRESH_MARGIN <= datetime.now(timezone.utc)
