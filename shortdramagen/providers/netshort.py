"""NetShort: series from the official site netshort.com, every episode from dramafren's player.

Official site (Next.js, no challenge). Every episode has its own page,
``/episode/{slug}-{id}-ep-{n}`` (``/episode/{slug}-{id}`` for the first); a
wrong slug is redirected to the right one, so ``x`` will do, and an unknown id
answers 404. The page's data (``self.__next_f``) hold:

- ``shortPlayDetailVo``: title, cover, synopsis, ``language`` (``fr_FR``) and
  ``videoEpisodeInfos``, the number and ``isLock`` of every episode;
- ``initialCurrentEpisodeInfo``, the episode shown: ``duration`` in seconds
  and, when it is free, ``playVoucher`` (a 720p MP4 of the official CDN, signed
  ``auth_key={expiry}-…`` for about ten days) and ``subtitleList`` (WebVTT
  files, one per language).

Each language version has its own id. Its video is not always subtitled (the
French version of an English series is not): the subtitles in the version's
language are saved next to the episode (``E001.fr.vtt``).

dramafren's NetShort player (netshort.dramafren.org, same ids, ``ep`` counted
from 1) is behind the Cloudflare challenge, but its watch page fetches the
video from ``index.php?action=resolve_watch&id={id}&ep={n}&server={1|2}``,
which cdn-netshort.dramafren.org answers without challenge (its pages answer
404). ``{"ok": true, "videoUrl", "qualities": [{"quality": "Default", "url"}],
"subtitles": [{"subtitleLanguage": "fr_FR", "url"}]}``: an MP4 of the official
CDN for any episode, paid ones included (540p, signed for about four days),
and the subtitles in the version's language. A refusal is a 404 with
``{"ok": false, "message": …}``. Free episodes keep the official 720p first.
"""

from __future__ import annotations

import json
import re
import threading
from datetime import datetime, timezone
from urllib.parse import ParseResult, parse_qs, quote, unquote, urlencode, urlparse

from .. import errors
from ..http import TRANSIENT_ERRORS, Http, HttpStatusError
from ..models import BookRef, Episode, Series, VideoSource, quality_from_text
from . import player
from .base import Availability, Limiter, Provider, ascii_slug

BASE_URL = "https://netshort.com"
DRAMAFREN_HOSTS = ("netshort.dramafren.org", "cdn-netshort.dramafren.org")
TIMEOUT_S = 60.0  # pages of 330 kB
PLAYER_URL = "https://cdn-netshort.dramafren.org/index.php"
PLAYER_SERVERS = (1, 2)  # the player's "Server 1/2"; the next one is tried when one says no
PLAYER_TIMEOUT_S = 60.0  # 0.1 to 16 s seen
_ID = r"\d{15,20}"
# /{lang}/episode/{slug}-{id}, …-ep-{n}, /full-episodes/{slug}-{id}, /hotseries/{slug}-{id}
_PATH_RE = re.compile(
    rf"^/(?:[a-z]{{2}}(?:-[a-zA-Z]{{2,4}})?/)?(?:episode|full-episodes|hotseries)/"
    rf"(?:[^/]*-)?(?P<id>{_ID})(?:-ep-(?P<ep>\d{{1,4}}))?/?$"
)
_PUSH_RE = re.compile(r'self\.__next_f\.push\(\[1,"((?:[^"\\]|\\.)*)"\]\)')
# The cover's original is a PNG of a few MB; the site's own og:image is this 540x720 WebP.
_COVER_ORIGINAL = "~tplv-vod-noop.image"
_COVER_SMALL = "~tplv-vod-rs:540:720.webp"


class NetShort(Provider):
    name = "netshort"
    label = "NetShort"
    hosts = ("netshort.com", *DRAMAFREN_HOSTS)
    home_url = BASE_URL + "/"
    source_urls = (PLAYER_URL,)
    id_pattern = _ID
    example_link = "https://netshort.com/episode/naked-tide-2103009231354593281"

    def parse_link(self, parsed: ParseResult) -> BookRef | None:
        """Official links (the slug is not needed) and dramafren links."""
        if (parsed.hostname or "").lower() in DRAMAFREN_HOSTS:
            return player.parse_link(parsed, _ID, self.name)
        m = _PATH_RE.match(unquote(parsed.path))
        if not m:
            return None
        episode = int(m.group("ep")) if m.group("ep") else None
        return BookRef(m.group("id"), episode=episode, provider=self.name)

    def series_link(self, book_id: str, slug: str | None) -> str:
        return f"{self.name}:{book_id}"

    def fetch_series(self, http: Http, ref: BookRef, lang: str | None) -> Series:
        try:
            page = http.get(episode_url(ref.book_id, 1), timeout=TIMEOUT_S).text()
        except HttpStatusError as e:
            if e.status in (404, 410):
                raise errors.SeriesNotFound(f"Série {ref.book_id} introuvable sur {BASE_URL}") from None
            raise
        return parse_series(page_data(page)[0], ref.book_id)

    def resolve(
        self, http: Http, series: Series, ep: Episode, limiter: Limiter | None, stop: threading.Event | None
    ) -> list[VideoSource]:
        """The official video of a free episode (720p), then dramafren's (540p, every episode).

        The episode's official page also gives its duration (set on ``ep``), paid
        episodes included: without it, dramafren's file is only checked as an MP4.
        """
        sources: list[VideoSource] = []
        if limiter:
            limiter.wait(stop)
        try:
            page = http.get(episode_url(series.source_book_id, ep.number), timeout=TIMEOUT_S).text()
            sources += official_sources(*page_data(page), ep)
        except (HttpStatusError, *TRANSIENT_ERRORS, errors.ResolveError):
            pass  # no answer, or the page showed another episode: dramafren may still have it
        if limiter:
            limiter.wait(stop)
        try:
            sources += player_sources(http, series, ep.number)
        except errors.ResolveError:
            if not sources:
                raise
        return sources

    def availability(
        self, http: Http, series: Series, limiter: Limiter | None, stop: threading.Event | None
    ) -> Availability:
        """dramafren is asked for the last episode (the most likely to be missing)."""
        if not series.episodes:
            return Availability(False, [], errors.ResolveError("aucun épisode annoncé par le site officiel NetShort"))
        if limiter:
            limiter.wait(stop)
        try:
            sources = player_sources(http, series, series.episodes[-1].number)
        except errors.ResolveError as e:
            return Availability(False, [], e)
        return Availability(True, [s.quality for s in sources if s.quality])

    def expires_at(self, url: str) -> datetime | None:
        """``auth_key={expiry}-{random}-0-{md5}``."""
        m = re.match(r"(\d+)-", parse_qs(urlparse(url).query).get("auth_key", [""])[0])
        return datetime.fromtimestamp(int(m.group(1)), tz=timezone.utc) if m else None


def episode_url(book_id: str, number: int) -> str:
    return f"{BASE_URL}/episode/x-{book_id}" + (f"-ep-{number}" if number > 1 else "")


def page_data(page: str) -> tuple[dict | None, dict | None]:
    """``shortPlayDetailVo`` and ``initialCurrentEpisodeInfo`` from the page's Next.js data."""
    try:
        flight = "".join(json.loads(f'"{chunk}"', strict=False) for chunk in _PUSH_RE.findall(page))
    except ValueError:
        return None, None
    return _object_after("shortPlayDetailVo", flight), _object_after("initialCurrentEpisodeInfo", flight)


def _object_after(key: str, text: str) -> dict | None:
    m = re.search(rf'"{key}"\s*:\s*', text)
    if not m:
        return None
    try:
        value, _ = json.JSONDecoder().raw_decode(text, m.end())
    except ValueError:
        return None
    return value if isinstance(value, dict) else None


def parse_series(detail: dict | None, book_id: str) -> Series:
    """No duration here (each episode's page has its own): they are read when downloading.

    ``free``: free on the official site, which then serves it in 720p.
    """
    infos = [e for e in (detail or {}).get("videoEpisodeInfos") or [] if isinstance(e, dict)]
    by_number = {e["episodeNo"]: e for e in infos if isinstance(e.get("episodeNo"), int) and e["episodeNo"] > 0}
    if not detail or not detail.get("shortPlayId") or not by_number:
        raise errors.SeriesNotFound(f"Série {book_id} introuvable sur {BASE_URL}")
    delisted = bool(detail.get("isDelisted"))  # the site then plays nothing
    episodes = []
    for n in range(1, max(by_number) + 1):
        info = by_number.get(n, {})
        episode_id = str(info.get("episodeId") or "")
        free = info.get("isLock") is False and not delisted
        episodes.append(Episode(number=n, chapter_id=episode_id, media_id=episode_id, free=free))
    real_id = str(detail["shortPlayId"])
    title = player.text(str(detail.get("shortPlayName") or "")) or real_id
    url_slug = str(detail.get("shortPlayUrl") or "").rsplit("/", 1)[-1]
    slug = ascii_slug(url_slug[: -len(real_id) - 1]) if url_slug.endswith("-" + real_id) else ""
    return Series(
        book_id=real_id,
        source_book_id=real_id,
        lang=_lang(detail.get("language")),
        title=title,
        slug=slug or ascii_slug(title) or "serie",
        episodes=episodes,
        cover=_cover(detail.get("shortPlayCover")),
        introduction=player.text(str(detail.get("shotIntroduce") or "")),
        title_vo=title,
        provider=NetShort.name,
    )


def official_sources(detail: dict | None, current: dict | None, ep: Episode) -> list[VideoSource]:
    """The MP4 of a free episode, with the subtitles in the version's language; none for a paid one."""
    if not current or current.get("episodeNo") != ep.number:
        raise errors.ResolveError(f"page du site officiel sans l'épisode {ep.number}", errors.URL_MISMATCH)
    try:
        ep.duration_ms = round(float(current.get("duration")) * 1000) or None
    except (TypeError, ValueError):
        pass
    video = current.get("playVoucher")
    if current.get("isLock") or not isinstance(video, str) or not video.startswith("https://"):
        return []
    language = (detail or {}).get("language")
    subtitles = next(
        (s.get("url") for s in current.get("subtitleList") or [] if isinstance(s, dict) and s.get("subtitleLanguage") == language),
        None,
    )
    subtitles = subtitles if isinstance(subtitles, str) and subtitles.startswith("https://") else None
    return [VideoSource(video, "", "official", "mp4", subtitles=subtitles)]


def player_sources(http: Http, series: Series, number: int) -> list[VideoSource]:
    """dramafren's MP4 of any episode. A refusal asks the next server; a network error ends the
    search, since both servers are behind the same host."""
    problems = []
    for server in PLAYER_SERVERS:
        query = urlencode({"action": "resolve_watch", "id": series.source_book_id, "ep": number, "server": server})
        try:
            data = http.get_json(f"{PLAYER_URL}?{query}", timeout=PLAYER_TIMEOUT_S)
        except HttpStatusError as e:
            data = _json(e.body)  # a refusal: 404 with {"ok": false, "message": …}
            if not isinstance(data, dict):
                raise errors.ResolveError(f"pas de réponse utilisable de dramafren ({e})", errors.NETWORK) from None
        except (ValueError, *TRANSIENT_ERRORS) as e:
            raise errors.ResolveError(f"pas de réponse utilisable de dramafren ({e})", errors.NETWORK) from None
        sources = parse_player_payload(data, series.lang)
        if sources:
            return sources
        message = data.get("message") if isinstance(data, dict) else None
        problems.append(f"serveur {server} : {message or 'réponse invalide'}")
    raise errors.ResolveError(f"Épisode {number} indisponible sur dramafren ({'; '.join(problems)})", errors.EP_UNAVAILABLE)


def parse_player_payload(data, lang: str) -> list[VideoSource]:
    """The MP4s of a ``resolve_watch`` answer, best first, with the subtitles in the series' language."""
    if not isinstance(data, dict) or not data.get("ok"):
        return []
    subtitles = next(
        (s.get("url") for s in data.get("subtitles") or [] if isinstance(s, dict) and _lang(s.get("subtitleLanguage")) == lang),
        None,
    )
    subtitles = subtitles if isinstance(subtitles, str) and subtitles.startswith("https://") else None
    sources: dict[str, VideoSource] = {}
    for q in data.get("qualities") or []:
        url = q.get("url") if isinstance(q, dict) else None
        if isinstance(url, str) and url.startswith("https://"):
            sources[url] = VideoSource(url, quality_from_text(str(q.get("quality") or "")), "dramafren", "mp4", subtitles)
    main = data.get("videoUrl")
    if isinstance(main, str) and main.startswith("https://") and main not in sources:
        sources[main] = VideoSource(main, "", "dramafren", "mp4", subtitles)
    return sorted(sources.values(), key=lambda s: s.height, reverse=True)


def _json(body: bytes):
    try:
        return json.loads(body)
    except ValueError:
        return None


def _lang(locale) -> str:
    """``fr_FR`` -> ``fr``."""
    return str(locale or "").split("_")[0].lower()


def _cover(url) -> str | None:
    if not isinstance(url, str) or not url.startswith("https://"):
        return None
    if url.endswith(_COVER_ORIGINAL):
        url = url[: -len(_COVER_ORIGINAL)] + _COVER_SMALL
    return quote(url, safe=":/?#[]@!$&'()*+,;=%~")  # the paths hold "3比4"
