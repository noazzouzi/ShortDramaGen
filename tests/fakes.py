"""Offline doubles for the network layer."""

from __future__ import annotations

import io
import json
import struct
from contextlib import contextmanager
from pathlib import Path

from shortdramagen.http import HttpStatusError, Response

FIXTURES = Path(__file__).parent / "fixtures"


def fixture_json(name: str):
    return json.loads((FIXTURES / name).read_text(encoding="utf-8"))


def official_html(props: dict) -> str:
    data = {"page": "/movie/[bookId]/[bookNameEn]", "props": {"pageProps": props}}
    return f'<html><script id="__NEXT_DATA__" type="application/json">{json.dumps(data)}</script></html>'


def make_mp4(duration_s: float, payload: int = 1000, timescale: int = 1000) -> bytes:
    """Smallest file mp4.duration_seconds() understands: ftyp + moov/mvhd + mdat."""
    mvhd_body = bytes(4) + bytes(8) + struct.pack(">II", timescale, int(duration_s * timescale)) + bytes(80)
    mvhd = struct.pack(">I4s", 8 + len(mvhd_body), b"mvhd") + mvhd_body
    moov = struct.pack(">I4s", 8 + len(mvhd), b"moov") + mvhd
    ftyp = struct.pack(">I4s", 16, b"ftyp") + b"isom" + bytes(4)
    mdat = struct.pack(">I4s", 8 + payload, b"mdat") + bytes(payload)
    return ftyp + moov + mdat


class FakeHttp:
    """Routes URLs to canned answers.

    ``pages``: url prefix -> str (HTML) | dict/list (JSON) | int (HTTP status) | callable(url)
    ``files``: url prefix -> bytes (served with Range support) | int (HTTP status)
    """

    def __init__(self, pages=None, files=None):
        self.pages = dict(pages or {})
        self.files = dict(files or {})
        self.calls: list[tuple[str, dict]] = []

    @staticmethod
    def _lookup(table, url):
        for prefix in sorted(table, key=len, reverse=True):
            if url.startswith(prefix):
                return table[prefix]
        raise HttpStatusError(url, 404)

    def get(self, url, headers=None):
        self.calls.append((url, dict(headers or {})))
        answer = self._lookup(self.pages, url)
        if callable(answer):
            answer = answer(url)
        if isinstance(answer, int):
            raise HttpStatusError(url, answer)
        if isinstance(answer, (dict, list)):
            answer = json.dumps(answer)
        return Response(url, 200, {}, answer.encode("utf-8"))

    def get_json(self, url, headers=None):
        return self.get(url, headers).json()

    @contextmanager
    def stream(self, url, headers=None):
        self.calls.append((url, dict(headers or {})))
        data = self._lookup(self.files, url)
        if isinstance(data, int):
            raise HttpStatusError(url, data)
        range_header = (headers or {}).get("Range")
        if range_header:
            start = int(range_header.split("=")[1].rstrip("-"))
            if start >= len(data):
                raise HttpStatusError(url, 416)
            chunk = data[start:]
            yield 206, {
                "Content-Length": str(len(chunk)),
                "Content-Range": f"bytes {start}-{len(data) - 1}/{len(data)}",
            }, io.BytesIO(chunk)
        else:
            yield 200, {"Content-Length": str(len(data))}, io.BytesIO(data)
