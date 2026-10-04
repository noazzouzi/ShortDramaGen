"""Pages shared by dramafren's player sites: one PHP application per platform
(cdn-flickreels.dramafren.org, shortmax.ngeshorts.fun…), with the same detail
page and the same links.

- Links: ``index.php?page=detail&id={id}`` and ``page=watch&id={id}&ep={n}``,
  ``n`` counted from 1 (GoodShort's player, older, counts from 0).
- Detail page: title (``<h1>``), poster (``og:image``), synopsis,
  ``Total: 61 Eps`` and the episode links. An unknown id gives the player's
  home page.
"""

from __future__ import annotations

import html
import json
import re
from urllib.parse import ParseResult, parse_qs

from .. import errors
from ..models import BookRef, Episode, Series
from .base import ascii_slug

_TITLE_RE = re.compile(r"<h1[^>]*>(.*?)</h1>", re.S)
_COVER_RE = re.compile(r'<meta property="og:image" content="([^"]+)"')
_SYNOPSIS_RE = re.compile(r'<p class="[^"]*leading-relaxed[^"]*">(.*?)</p>', re.S)
_DESCRIPTION_RE = re.compile(r'<meta name="description" content="([^"]*)"')
_TOTAL_RE = re.compile(r"Total:\s*(\d+)\s*Eps")
_TAG_RE = re.compile(r"<[^>]+>")


def parse_link(parsed: ParseResult, id_pattern: str, provider: str) -> BookRef | None:
    """``id`` and ``ep`` of a player link; None without a valid id."""
    query = parse_qs(parsed.query)
    book_id = next((v for v in query.get("id", []) if re.fullmatch(id_pattern, v)), None)
    episode = next((int(v) for v in query.get("ep", []) if v.isdigit() and int(v) > 0), None)
    return BookRef(book_id, episode=episode, provider=provider) if book_id else None


def parse_detail_page(page: str, book_id: str, provider: str, site: str) -> Series:
    """The series as the player's detail page shows it: no per-episode duration, no language."""
    title = _TITLE_RE.search(page)
    total = _TOTAL_RE.search(page)
    episode_links = [int(n) for n in re.findall(rf"page=watch&(?:amp;)?id={book_id}&(?:amp;)?ep=(\d+)", page)]
    count = max([int(total.group(1)) if total else 0, *episode_links])
    if not title or not count:  # an unknown id gives the player's home page
        raise errors.SeriesNotFound(f"Série {book_id} introuvable sur {site}")
    name = text(title.group(1)) or book_id
    synopsis = _SYNOPSIS_RE.search(page) or _DESCRIPTION_RE.search(page)
    cover = _COVER_RE.search(page)
    return Series(
        book_id=book_id,
        source_book_id=book_id,
        lang="",  # not published: the title is in the version's language
        title=name,
        slug=ascii_slug(name) or "serie",
        episodes=[Episode(number=n, chapter_id="", media_id="") for n in range(1, count + 1)],
        cover=html.unescape(cover.group(1)) if cover and cover.group(1).startswith("https://") else None,
        introduction=text(synopsis.group(1)) if synopsis else "",
        title_vo=name,
        provider=provider,
    )


def text(fragment: str) -> str:
    return " ".join(html.unescape(_TAG_RE.sub(" ", fragment)).split())


def json_after(regex: re.Pattern, page: str):
    """The JSON value a script assigns (``var x = …;``), or None."""
    m = regex.search(page)
    if not m:
        return None
    try:
        value, _ = json.JSONDecoder().raw_decode(page, m.end())
    except ValueError:
        return None
    return value
