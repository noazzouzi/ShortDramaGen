from __future__ import annotations

import re
from dataclasses import dataclass, field

_QUALITY_RE = re.compile(r"(\d{3,4})p", re.IGNORECASE)


@dataclass(frozen=True)
class BookRef:
    """What the user asked for: a book id and, optionally, a language and an episode."""

    book_id: str
    lang: str | None = None
    episode: int | None = None  # set when the link points at one episode (/ep/…, dramafren watch)


@dataclass
class Episode:
    number: int  # 1-based, as displayed on the sites
    chapter_id: str  # id from the official chapter list (original version)
    media_id: str  # id used in CDN paths; differs from chapter_id for dubbed versions
    duration_ms: int | None = None
    free_url: str | None = None  # official MP4, only for the free episodes


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
    from_official: bool = True  # False when metadata was probed from dramafren only
    title_vo: str | None = None  # title of the original version, when known

    @property
    def total_duration_ms(self) -> int | None:
        durations = [ep.duration_ms for ep in self.episodes]
        return sum(durations) if durations and all(durations) else None

    @property
    def episode_count(self) -> int:
        return len(self.episodes)


@dataclass(frozen=True)
class VideoSource:
    url: str
    quality: str  # "1080p", "720p", ... or "" when unknown
    origin: str  # "dramafren" or "official"

    @property
    def height(self) -> int:
        m = _QUALITY_RE.search(self.quality)
        return int(m.group(1)) if m else 0


def quality_from_text(text: str) -> str:
    m = _QUALITY_RE.search(text or "")
    return f"{m.group(1)}p" if m else ""
