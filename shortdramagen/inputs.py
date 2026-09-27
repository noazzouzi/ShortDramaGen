"""Turn any supported URL (or a raw id) into a BookRef."""

from __future__ import annotations

import re
from urllib.parse import parse_qs, urlparse

from .models import BookRef

_BOOK_ID = r"\d{8,14}"
_RAW_ID_RE = re.compile(rf"^\s*({_BOOK_ID})\s*$")
# dramaboxdb.com/{locale?}/movie/{id}/..., /ep/{id}_{slug}/..., dramabox(app).com/drama/{id}/...
_PATH_RE = re.compile(
    rf"^/(?:(?P<locale>[a-zA-Z]{{2}}(?:-[a-zA-Z]{{2,4}})?)/)?"
    rf"(?:movie|drama|video|book)/(?P<id>{_BOOK_ID})(?:[/_?#]|$)"
)
_EP_PATH_RE = re.compile(
    rf"^/(?:(?P<locale>[a-zA-Z]{{2}}(?:-[a-zA-Z]{{2,4}})?)/)?ep/(?P<id>{_BOOK_ID})_"
)
_EP_NUMBER_RE = re.compile(r"_Episode-(\d+)", re.IGNORECASE)
_QUERY_KEYS = ("bookId", "book_id", "bid", "id")
_ANY_ID_RE = re.compile(rf"(?<!\d)(4[12]\d{{9}})(?!\d)")


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
    """Accepts official URLs, share links, dramafren URLs or a bare book id.

    Only official-site URLs carry a meaningful language: on dramafren the
    ``lang`` parameter does not change the video, so it is ignored.
    """
    m = _RAW_ID_RE.match(text)
    if m:
        return BookRef(m.group(1))

    url = text.strip()
    if "://" not in url:
        url = "https://" + url
    parsed = urlparse(url)
    host = (parsed.hostname or "").lower()
    if not host:
        raise InputError(f"URL non reconnue : {text!r}")

    for regex in (_EP_PATH_RE, _PATH_RE):
        m = regex.match(parsed.path)
        if m:
            locale = m.group("locale")
            lang = locale.lower() if locale and "dramaboxdb" in host else None
            ep = _EP_NUMBER_RE.search(parsed.path) if regex is _EP_PATH_RE else None
            return BookRef(m.group("id"), lang, int(ep.group(1)) if ep else None)

    query = parse_qs(parsed.query)
    episode = next((int(v) for v in query.get("ep", []) if v.isdigit()), None)
    for key in _QUERY_KEYS:
        for value in query.get(key, []):
            if re.fullmatch(_BOOK_ID, value):
                return BookRef(value, episode=episode)

    m = _ANY_ID_RE.search(parsed.path + "?" + parsed.query)
    if m:
        return BookRef(m.group(1))

    raise InputError(
        f"Impossible de trouver l'identifiant de la série dans : {text!r}\n"
        "Formats acceptés : URL dramaboxdb.com / dramabox.com, lien de partage, "
        "URL dramafren ou identifiant numérique (ex. 41000105199)."
    )
