"""Metadata from the official website www.dramaboxdb.com (Next.js, no bot wall).

One request returns the whole chapter list (ids, durations) plus signed MP4
URLs for the free episodes. See docs/01-etude-technique.md §5.
"""

from __future__ import annotations

import json
import re

from . import cdn
from .http import Http, HttpStatusError
from .models import Episode, Series

BASE_URL = "https://www.dramaboxdb.com"
_NEXT_DATA_RE = re.compile(r'<script id="__NEXT_DATA__"[^>]*>(.*?)</script>', re.S)


class SeriesNotFound(Exception):
    pass


def series_url(book_id: str, lang: str | None = None) -> str:
    # English is the site default and has no locale prefix (/en/ redirects).
    prefix = f"/{lang}" if lang and lang != "en" else ""
    return f"{BASE_URL}{prefix}/movie/{book_id}/"


def fetch_series(http: Http, book_id: str, lang: str | None = None) -> Series:
    url = series_url(book_id, lang)
    try:
        resp = http.get(url)
    except HttpStatusError as e:
        if e.status == 404:
            raise SeriesNotFound(f"Série {book_id} introuvable sur {BASE_URL}") from None
        raise
    return parse_series_page(resp.text(), book_id, lang)


def parse_series_page(html: str, book_id: str, lang: str | None = None) -> Series:
    m = _NEXT_DATA_RE.search(html)
    if not m:
        raise SeriesNotFound(f"Pas de données __NEXT_DATA__ pour la série {book_id}")
    props = json.loads(m.group(1)).get("props", {}).get("pageProps", {})
    return parse_page_props(props, book_id, lang)


def parse_page_props(props: dict, book_id: str, lang: str | None = None) -> Series:
    info = props.get("bookInfo")
    chapters = props.get("chapterList")
    if not info or not chapters:
        raise SeriesNotFound(f"Série {book_id} introuvable (page vide ou 404)")

    languages = list(props.get("languages") or [])
    source_book_id = str(props.get("sourceBookId") or info.get("bookId") or book_id)
    episodes = []
    for ch in sorted(chapters, key=lambda c: c.get("index", 0)):
        chapter_id = str(ch["id"])
        media_id = (
            cdn.media_id_from_url(ch.get("mp4"))
            or cdn.media_id_from_url(ch.get("cover"))
            or chapter_id
        )
        episodes.append(
            Episode(
                number=int(ch.get("index", len(episodes))) + 1,
                chapter_id=chapter_id,
                media_id=media_id,
                duration_ms=ch.get("duration") or None,
                free_url=ch.get("mp4") if ch.get("unlock") else None,
            )
        )

    return Series(
        book_id=str(info.get("bookId") or book_id),
        source_book_id=source_book_id,
        lang=props.get("locale") or lang or "en",
        title=info.get("bookName") or book_id,
        slug=info.get("bookNameLower") or _slugify(info.get("bookNameEn") or book_id),
        episodes=episodes,
        languages=languages,
        cover=info.get("cover"),
        introduction=info.get("introduction") or "",
    )


def _slugify(text: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", text.lower()).strip("-") or "serie"
