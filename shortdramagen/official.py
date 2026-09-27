"""Metadata from the official website www.dramaboxdb.com (Next.js, no bot wall).

One request returns the whole chapter list (ids, durations) plus signed MP4
URLs for the free episodes. See docs/01-etude-technique.md §5.
"""

from __future__ import annotations

import json
import re

from . import cdn, errors
from .http import Http, HttpStatusError
from .models import LANGUAGE_CODES, Episode, Series

BASE_URL = "https://www.dramaboxdb.com"
_NEXT_DATA_RE = re.compile(r'<script id="__NEXT_DATA__"[^>]*>(.*?)</script>', re.S)


SeriesNotFound = errors.SeriesNotFound  # shared by every platform


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

    title = info.get("bookName") or book_id
    return Series(
        book_id=str(info.get("bookId") or book_id),
        source_book_id=source_book_id,
        # The language of the videos. A locale without dub serves the original
        # version, whose bookInfo.language tells the real language.
        lang=LANGUAGE_CODES.get(str(info.get("language") or "").upper()) or props.get("locale") or lang or "en",
        title=title,
        slug=info.get("bookNameLower") or _slugify(info.get("bookNameEn") or book_id),
        episodes=episodes,
        languages=languages,
        cover=info.get("cover"),
        introduction=info.get("introduction") or "",
        title_vo=_title_from_slug(info.get("bookNameEn")) or title,
    )


def _title_from_slug(slug: str | None) -> str | None:
    """"One-Night-to-Forever" -> "One Night to Forever" (the site gives the VO title as a slug)."""
    return re.sub(r"-+", " ", slug).strip() or None if slug else None


def _slugify(text: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", text.lower()).strip("-") or "serie"
