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
_QUERY_KEYS = ("bookId", "book_id", "bid", "id")
_ANY_ID_RE = re.compile(rf"(?<!\d)(4[12]\d{{9}})(?!\d)")


class InputError(ValueError):
    pass


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
            return BookRef(m.group("id"), lang)

    query = parse_qs(parsed.query)
    for key in _QUERY_KEYS:
        for value in query.get(key, []):
            if re.fullmatch(_BOOK_ID, value):
                return BookRef(value)

    m = _ANY_ID_RE.search(parsed.path + "?" + parsed.query)
    if m:
        return BookRef(m.group(1))

    raise InputError(
        f"Impossible de trouver l'identifiant de la série dans : {text!r}\n"
        "Formats acceptés : URL dramaboxdb.com / dramabox.com, lien de partage, "
        "URL dramafren ou identifiant numérique (ex. 41000105199)."
    )
