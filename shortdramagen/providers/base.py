"""What a platform must provide so the engine can download from it.

The pipeline, the job runner, the library and the web interface only talk to
this interface: adding a platform means writing one module in this package and
registering it in ``registry``, nothing else.
"""

from __future__ import annotations

import threading
from dataclasses import dataclass
from datetime import datetime
from typing import TYPE_CHECKING, Protocol
from urllib.parse import ParseResult

from .. import errors
from ..http import Http
from ..models import BookRef, Episode, Series, VideoSource

if TYPE_CHECKING:
    from ..pipeline import FetchControl


class Limiter(Protocol):
    def wait(self, stop: threading.Event | None = None) -> None: ...


@dataclass
class Availability:
    """Can this series be downloaded right now? Checked once, before downloading anything."""

    available: bool
    qualities: list[str]
    error: errors.ResolveError | None = None


class Provider:
    name = ""  # stable id, stored in manifests and jobs: "dramabox"
    label = ""  # for people: "DramaBox"
    hosts: tuple[str, ...] = ()  # link hosts, subdomains included
    home_url = ""  # probed to tell whether the network is up
    source_urls: tuple[str, ...] = ()  # other hosts the videos come from, probed too
    can_probe = False  # can list the episodes of a series its official site does not know
    id_pattern = r"\d{8,14}"  # a series id, as typed after "name:"
    example_link = ""

    def handles(self, host: str) -> bool:
        return any(host == h or host.endswith("." + h) for h in self.hosts)

    def parse_link(self, parsed: ParseResult) -> BookRef | None:
        """The series a link of this platform points at, or None if it is not a series link."""
        raise NotImplementedError

    def series_link(self, book_id: str, slug: str | None) -> str:
        """What to type again to reach this series (repairs, commands shown to the user)."""
        raise NotImplementedError

    def fetch_series(self, http: Http, ref: BookRef, lang: str | None) -> Series:
        """Official metadata. Raises errors.SeriesNotFound."""
        raise NotImplementedError

    def resolve(
        self, http: Http, series: Series, ep: Episode, limiter: Limiter | None, stop: threading.Event | None
    ) -> list[VideoSource]:
        """Every usable source for one episode. Raises errors.ResolveError."""
        raise NotImplementedError

    def availability(
        self, http: Http, series: Series, limiter: Limiter | None, stop: threading.Event | None
    ) -> Availability:
        raise NotImplementedError

    def probe_series(
        self, http: Http, ref: BookRef, limiter: Limiter, control: "FetchControl"
    ) -> tuple[Series, dict[int, list[VideoSource]]]:
        """Episodes found without official metadata (only when ``can_probe``)."""
        raise errors.SeriesNotFound(f"Série {ref.book_id} introuvable sur {self.label}")

    def probe_first(self, http: Http, ref: BookRef) -> list[VideoSource]:
        """Sources of episode 1 of a series the official site does not know (only when ``can_probe``)."""
        raise errors.ResolveError(f"série inconnue de {self.label}")

    def expires_at(self, url: str) -> datetime | None:
        """When a signed video URL stops working, if the URL says so."""
        return None


def free_sources(series: Series, ep: Episode, origin: str = "official") -> list[VideoSource]:
    """The official free video of an episode, for platforms that only offer those."""
    if ep.free_url:
        return [VideoSource(ep.free_url, "", origin, series.free_url_kind)]
    raise errors.ResolveError(
        f"épisode {ep.number} payant : seuls les épisodes gratuits du site officiel sont téléchargeables",
        errors.EP_UNAVAILABLE,
    )
