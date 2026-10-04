from __future__ import annotations

import re
from dataclasses import dataclass, field

_QUALITY_RE = re.compile(r"(\d{3,4})p", re.IGNORECASE)

DEFAULT_PROVIDER = "dramabox"
# Language names used by the platforms' metadata -> locale codes, as in DramaBox URLs.
LANGUAGE_CODES = {
    "ENGLISH": "en", "FRENCH": "fr", "SPANISH": "es", "KOREAN": "ko", "JAPANESE": "ja", "THAI": "th",
    "INDONESIAN": "in", "PORTUGUESE": "pt", "GERMAN": "de", "ITALIAN": "it", "ARABIC": "ar",
    "VIETNAMESE": "vi", "CHINESE": "zh", "TRADITIONAL_CHINESE": "zh", "SIMPLIFIED_CHINESE": "zhHans",
}  # fmt: skip


def ref_key(provider: str, book_id: str) -> str:
    """How a series is written in commands, routes and job inputs: "41000105199", "goodshort:31000662271".

    DramaBox keeps the bare id it always had, so existing folders, links and scripts stay valid.
    """
    return book_id if provider == DEFAULT_PROVIDER else f"{provider}:{book_id}"


@dataclass(frozen=True)
class BookRef:
    """What the user asked for: a series on a platform and, optionally, a language and an episode."""

    book_id: str
    lang: str | None = None
    episode: int | None = None  # set when the link points at one episode (/ep/…, dramafren watch)
    provider: str = DEFAULT_PROVIDER
    slug: str | None = None  # from the link, for platforms whose pages need it in the URL

    @property
    def key(self) -> str:
        return ref_key(self.provider, self.book_id)


@dataclass
class Episode:
    number: int  # 1-based, as displayed on the sites
    chapter_id: str  # the platform's id for this episode (original version)
    media_id: str  # id used in CDN paths; differs from chapter_id for dubbed versions
    duration_ms: int | None = None
    free_url: str | None = None  # official video, only for the free episodes
    free: bool = False  # free on the official site, its video read when downloading (NetShort)


@dataclass
class Series:
    book_id: str
    source_book_id: str  # book holding the videos for the chosen language
    lang: str
    title: str
    slug: str
    episodes: list[Episode]
    languages: list[str] = field(default_factory=list)
    cover: str | None = None
    introduction: str = ""
    from_official: bool = True  # False when metadata was probed from the source only
    title_vo: str | None = None  # title of the original version, when known
    provider: str = DEFAULT_PROVIDER
    free_only: bool = False  # only the free episodes of the official site can be downloaded
    free_url_kind: str = "mp4"  # "mp4" or "hls": how the official site serves its free episodes
    duration_tolerance_s: float = 1.0  # how far a file may be from the announced duration

    @property
    def key(self) -> str:
        return ref_key(self.provider, self.book_id)

    @property
    def total_duration_ms(self) -> int | None:
        durations = [ep.duration_ms for ep in self.episodes]
        return sum(durations) if durations and all(durations) else None

    @property
    def episode_count(self) -> int:
        return len(self.episodes)

    @property
    def free_numbers(self) -> list[int]:
        return [ep.number for ep in self.episodes if ep.free_url or ep.free]


@dataclass(frozen=True)
class VideoSource:
    url: str
    quality: str  # "1080p", "720p", ... or "" when unknown
    origin: str  # "official", "dramafren"…
    kind: str = "mp4"  # "mp4": one file; "hls": an m3u8 playlist of segments
    subtitles: str | None = None  # WebVTT file in the series' language, for a video without burned-in subtitles

    @property
    def height(self) -> int:
        m = _QUALITY_RE.search(self.quality)
        return int(m.group(1)) if m else 0


def quality_from_text(text: str) -> str:
    m = _QUALITY_RE.search(text or "")
    return f"{m.group(1)}p" if m else ""
