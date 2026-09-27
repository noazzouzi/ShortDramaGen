"""The platforms the engine knows, and how a link or an id is matched to one of them."""

from __future__ import annotations

from urllib.parse import ParseResult

from ..models import DEFAULT_PROVIDER, BookRef
from .base import Provider
from .dramabox import DramaBox
from .goodshort import GoodShort

PROVIDERS: tuple[Provider, ...] = (DramaBox(), GoodShort())
_BY_NAME = {p.name: p for p in PROVIDERS}


def get(name: str | None) -> Provider:
    """The platform stored in a manifest or a job; old data without one is DramaBox."""
    try:
        return _BY_NAME[name or DEFAULT_PROVIDER]
    except KeyError:
        raise ValueError(f"plateforme inconnue : {name}") from None


def names() -> list[str]:
    return list(_BY_NAME)


def parse_link(parsed: ParseResult) -> BookRef | None:
    """The series a link points at. A host no platform claims gets DramaBox's permissive rules,
    as before platforms existed (the app's share links use changing domains)."""
    host = (parsed.hostname or "").lower()
    for provider in PROVIDERS:
        if provider.handles(host):
            return provider.parse_link(parsed)
    return get(DEFAULT_PROVIDER).parse_link(parsed)
