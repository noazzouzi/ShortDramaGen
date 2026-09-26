"""Tiny HTTP layer over urllib (no third-party dependency).

Everything network-related goes through ``Http`` so tests can swap in a fake.
Proxies (HTTPS_PROXY) and custom CA bundles (SSL_CERT_FILE) are honoured by
urllib/OpenSSL out of the box.
"""

from __future__ import annotations

import http.client
import json
import time
import urllib.error
import urllib.request
from contextlib import contextmanager
from dataclasses import dataclass
from typing import IO, Iterator, Mapping

USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/140.0.0.0 Safari/537.36"
)

# Errors worth retrying: no usable HTTP answer, or the body was cut short.
# URLError, timeouts and connection resets are all OSError subclasses;
# IncompleteRead is an http.client.HTTPException.
TRANSIENT_ERRORS = (OSError, http.client.HTTPException)


class HttpStatusError(Exception):
    def __init__(self, url: str, status: int, body: bytes = b""):
        super().__init__(f"HTTP {status} pour {url}")
        self.url = url
        self.status = status
        self.body = body


@dataclass
class Response:
    url: str  # final URL, after redirects
    status: int
    headers: Mapping[str, str]
    body: bytes

    def text(self) -> str:
        return self.body.decode("utf-8", errors="replace")

    def json(self):
        return json.loads(self.body)


class Http:
    def __init__(self, timeout: float = 30.0, retries: int = 3, backoff: float = 2.0):
        self.timeout = timeout
        self.retries = retries
        self.backoff = backoff

    def _request(self, url: str, headers: Mapping[str, str] | None) -> urllib.request.Request:
        h = {"User-Agent": USER_AGENT, "Accept-Language": "en-US,en;q=0.9"}
        h.update(headers or {})
        return urllib.request.Request(url, headers=h)

    def get(self, url: str, headers: Mapping[str, str] | None = None) -> Response:
        """GET with retries on network errors and 5xx. 4xx raise immediately."""
        attempt = 0
        while True:
            attempt += 1
            try:
                with urllib.request.urlopen(self._request(url, headers), timeout=self.timeout) as r:
                    return Response(r.geturl(), r.status, dict(r.headers.items()), r.read())
            except urllib.error.HTTPError as e:
                body = e.read() if e.fp else b""
                if e.code < 500 or attempt > self.retries:
                    raise HttpStatusError(url, e.code, body) from None
            except TRANSIENT_ERRORS:
                if attempt > self.retries:
                    raise
            time.sleep(self.backoff * 2 ** (attempt - 1))

    def get_json(self, url: str, headers: Mapping[str, str] | None = None):
        h = {"Accept": "application/json"}
        h.update(headers or {})
        return self.get(url, h).json()

    @contextmanager
    def stream(
        self, url: str, headers: Mapping[str, str] | None = None
    ) -> Iterator[tuple[int, Mapping[str, str], IO[bytes]]]:
        """Open a streaming GET. HTTP errors raise HttpStatusError; no retry here."""
        try:
            r = urllib.request.urlopen(self._request(url, headers), timeout=self.timeout)
        except urllib.error.HTTPError as e:
            raise HttpStatusError(url, e.code) from None
        try:
            yield r.status, dict(r.headers.items()), r
        finally:
            r.close()
