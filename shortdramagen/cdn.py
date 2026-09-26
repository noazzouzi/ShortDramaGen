"""Knowledge about DramaBox CDN URLs (see docs/01-etude-technique.md §4).

Paths are deterministic:
    {rev(cid[-2:])}/{r0}x{r1}/{r0r1}x{r2}/{r0r1r2}x{r3}/{rev(book_id)}/{cid}_1/{cid}.<quality>.mp4
Only the signature (Akamai path token or CloudFront query) cannot be computed,
so these helpers are used to *check* URLs, never to build downloadable ones.
"""

from __future__ import annotations

import re
from datetime import datetime, timezone
from urllib.parse import parse_qs, urlparse

_AKAMAI_TOKEN_RE = re.compile(r"^/[0-9a-f]{32}/([0-9a-f]{8})/")
_MEDIA_ID_RE = re.compile(r"/(\d+)_1/(?:m3u8/)?\1\.")


def expected_path(book_id: str, media_id: str) -> str:
    r = book_id[::-1]
    seg = media_id[-2:][::-1]
    return f"/{seg}/{r[0]}x{r[1]}/{r[:2]}x{r[2]}/{r[:3]}x{r[3]}/{r}/{media_id}_1/"


def matches_episode(url: str, book_id: str, media_id: str) -> bool:
    """True if the URL points at this book/episode (guards against mix-ups)."""
    return expected_path(book_id, media_id) in urlparse(url).path


def media_id_from_url(url: str | None) -> str | None:
    if not url:
        return None
    m = _MEDIA_ID_RE.search(urlparse(url).path)
    return m.group(1) if m else None


def expires_at(url: str) -> datetime | None:
    parsed = urlparse(url)
    m = _AKAMAI_TOKEN_RE.match(parsed.path)
    if m:
        return datetime.fromtimestamp(int(m.group(1), 16), tz=timezone.utc)
    expires = parse_qs(parsed.query).get("Expires")
    if expires and expires[0].isdigit():
        return datetime.fromtimestamp(int(expires[0]), tz=timezone.utc)
    return None
