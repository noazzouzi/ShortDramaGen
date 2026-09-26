"""Signed video URLs from dramafren's JSON API.

The player page calls ``cdn-dramabox.dramafren.org/index.php?action=get_video``
(found in the HAR captures). Unlike the HTML pages, this endpoint is not behind
the Cloudflare challenge and needs no cookie. ``lang`` does not change the
video (the dubbed versions have their own book id), ``sv=1`` is the only
server that answers for DramaBox.
"""

from __future__ import annotations

from urllib.parse import urlencode

from .http import Http, HttpStatusError, TRANSIENT_ERRORS
from .models import VideoSource, quality_from_text

ENDPOINTS = (
    "https://cdn-dramabox.dramafren.org/index.php",
    "https://cdn-dramaboxv2.dramafren.org/index.php",  # fallback used by the site itself
)
_HEADERS = {"Origin": "https://dramabox.dramafren.org", "Referer": "https://dramabox.dramafren.org/"}


class ResolveError(Exception):
    pass


def get_video(http: Http, book_id: str, episode: int, lang: str = "en") -> list[VideoSource]:
    """All qualities available for one episode, best first."""
    query = urlencode({"action": "get_video", "id": book_id, "ep": episode, "lang": lang, "sv": 1})
    errors = []
    for endpoint in ENDPOINTS:
        try:
            data = http.get_json(f"{endpoint}?{query}", _HEADERS)
        except (HttpStatusError, ValueError, *TRANSIENT_ERRORS) as e:
            errors.append(f"{endpoint}: {e}")
            continue
        if not isinstance(data, dict) or not data.get("ok") or not data.get("videoUrl"):
            errors.append(f"{endpoint}: {(data or {}).get('error', 'réponse invalide')}")
            continue
        return parse_video_payload(data)
    raise ResolveError(f"Épisode {episode} indisponible sur dramafren ({'; '.join(errors)})")


def parse_video_payload(data: dict) -> list[VideoSource]:
    sources: dict[str, VideoSource] = {}
    for q in data.get("qualities") or []:
        url = q.get("url")
        if url:
            sources[url] = VideoSource(url, quality_from_text(q.get("quality", "")) or quality_from_text(url), "dramafren")
    main = data["videoUrl"]
    if main not in sources:
        sources[main] = VideoSource(main, quality_from_text(main), "dramafren")
    return sorted(sources.values(), key=lambda s: s.height, reverse=True)
