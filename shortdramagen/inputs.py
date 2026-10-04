"""Turn any supported URL (or a raw id) into a BookRef."""

from __future__ import annotations

import re
from urllib.parse import urlparse

from .models import BookRef
from .providers import registry

_RAW_ID_RE = re.compile(r"^\s*(\d{8,14})\s*$")
_PREFIXED_RE = re.compile(r"^\s*([a-z][a-z0-9]*):(\S+)\s*$")


EpisodeRanges = list[tuple[int, int | None]]  # [(1, 10), (28, 28), (50, None)]; None = open end
_RANGE_RE = re.compile(r"(\d+)(?:\s*-\s*(\d*))?")


class InputError(ValueError):
    pass


def parse_episodes(spec: str | None) -> EpisodeRanges | None:
    """"1-10,28,50-" -> [(1, 10), (28, 28), (50, None)] (None = up to the last episode).

    Spaces and typographic dashes (– —) are accepted, as typed in a text field.
    """
    if not spec or not spec.strip():
        return None
    ranges: EpisodeRanges = []
    for part in re.sub(r"[\u2012-\u2015\u2212]", "-", spec).split(","):
        part = part.strip()
        m = _RANGE_RE.fullmatch(part)
        if not m:
            raise InputError(f"plage d'épisodes invalide : {part!r}")
        start = int(m.group(1))
        if m.group(2) is None:
            ranges.append((start, start))
        else:
            end = int(m.group(2)) if m.group(2) else None
            if end is not None and end < start:
                raise InputError(f"plage d'épisodes à l'envers : {part!r}")
            ranges.append((start, end))
    return ranges


def parse_input(text: str) -> BookRef:
    """Accepts a link of a known platform, a bare DramaBox id, or "platform:id" (goodshort:31000662271)."""
    m = _RAW_ID_RE.match(text)
    if m:
        return BookRef(m.group(1))
    m = _PREFIXED_RE.match(text)
    if m and m.group(1) in registry.names():
        provider = registry.get(m.group(1))
        if not re.fullmatch(provider.id_pattern, m.group(2)):
            raise InputError(f"Identifiant {provider.label} invalide : {m.group(2)!r}")
        return BookRef(m.group(2), provider=provider.name)

    url = text.strip()
    if "://" not in url:
        url = "https://" + url
    parsed = urlparse(url)
    if not parsed.hostname:
        raise InputError(f"URL non reconnue : {text!r}")
    ref = registry.parse_link(parsed)
    if ref:
        return ref
    raise InputError(
        f"Impossible de trouver l'identifiant de la série dans : {text!r}\n"
        f"Formats acceptés : {accepted_formats()}"
    )


def accepted_formats() -> str:
    links = ", ".join(p.example_link for p in registry.PROVIDERS)
    return f"un lien de série ({links}), un n° de série DramaBox (ex. 41000105199) ou plateforme:n° (ex. goodshort:31000662271, flickreels:9561, shortmax:24403, netshort:2103009231354593281)."
