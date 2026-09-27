"""Protection of the local server against the other sites open in the same browser.

The server only listens on 127.0.0.1, but any web page can still make the
browser send requests to it. Hence (docs/frontend/brainstorm/4-recherche-architecture.md §6):
- Host must be ours (DNS rebinding) → 421;
- Sec-Fetch-Site must not be cross-site or same-site (another local port is
  "same-site") → 403;
- /api/* needs the X-SDG-Token header, which only our own page knows (it is
  written into index.html); a custom header also forces a CORS preflight,
  which is never granted;
- /media/* cannot carry a header (<video>, <img>): it relies on the two first
  checks plus Cross-Origin-Resource-Policy: same-origin.
"""

from __future__ import annotations

import hashlib
import hmac

TOKEN_HEADER = "X-SDG-Token"

CSP = (
    "default-src 'none'; script-src 'self'; style-src 'self'; img-src 'self' data:; "
    "media-src 'self'; connect-src 'self'; font-src 'self'; manifest-src 'self'; "
    "base-uri 'none'; form-action 'none'; frame-ancestors 'none'"
)

COMMON_HEADERS = {
    "X-Content-Type-Options": "nosniff",
    "Referrer-Policy": "no-referrer",
    "Cross-Origin-Opener-Policy": "same-origin",
    "Cross-Origin-Resource-Policy": "same-origin",
    "X-Frame-Options": "DENY",
}


def page_token(secret: str) -> str:
    return hmac.new(secret.encode("utf-8"), b"csrf", hashlib.sha256).hexdigest()


def allowed_hosts(port: int) -> set[str]:
    return {f"127.0.0.1:{port}", f"localhost:{port}"}


def host_ok(host: str | None, port: int) -> bool:
    return (host or "").strip().lower() in allowed_hosts(port)


def fetch_site_ok(value: str | None) -> bool:
    """Requests from our own page are same-origin; typed URLs and bookmarks are
    "none"; command-line clients send nothing. Everything else is refused."""
    return value is None or value.strip().lower() in ("same-origin", "none")


def origin_ok(origin: str | None, port: int) -> bool:
    """For mutations: an Origin, when present, must be ours."""
    return origin is None or origin.strip().lower() in {f"http://{h}" for h in allowed_hosts(port)}


def token_ok(sent: str | None, expected: str) -> bool:
    return bool(sent) and hmac.compare_digest(sent.encode("utf-8", "replace"), expected.encode("ascii"))
