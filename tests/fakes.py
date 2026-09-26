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


def box(kind: bytes, *payload: bytes) -> bytes:
    body = b"".join(payload)
    return struct.pack(">I4s", 8 + len(body), kind) + body


def full_box(kind: bytes, *payload: bytes, version: int = 0) -> bytes:
    return box(kind, bytes([version, 0, 0, 0]), *payload)


def video_track(width: int, height: int, avcc: bytes, seconds: float, edit_s: float | None = None) -> bytes:
    entry_body = bytes(24) + struct.pack(">HH", width, height) + bytes(50) + box(b"avcC", avcc)
    return _track(b"vide", box(b"avc1", entry_body), 12800, seconds, edit_s)


def audio_track(asc: bytes, bitrate: int, seconds: float, edit_s: float | None = None, rate: int = 44100) -> bytes:
    """mp4a entry whose esds carries ``bitrate``: it must not affect the format key."""
    dsi = bytes([0x05, len(asc)]) + asc
    dcd_body = bytes([0x40, 0x15]) + bytes(3) + struct.pack(">II", bitrate, bitrate) + dsi
    dcd = bytes([0x04, len(dcd_body)]) + dcd_body
    es_body = bytes(3) + dcd + bytes([0x06, 0x01, 0x02])
    esds = full_box(b"esds", bytes([0x03, len(es_body)]) + es_body)
    entry_body = bytes(16) + struct.pack(">HHHHI", 2, 16, 0, 0, rate << 16) + esds
    return _track(b"soun", box(b"mp4a", entry_body), rate, seconds, edit_s)


def _track(handler: bytes, sample_entry: bytes, timescale: int, seconds: float, edit_s: float | None) -> bytes:
    mdhd = full_box(b"mdhd", bytes(8), struct.pack(">II", timescale, int(seconds * timescale)), bytes(4))
    hdlr = full_box(b"hdlr", bytes(4), handler, bytes(12), b"\0")
    stsd = full_box(b"stsd", struct.pack(">I", 1), sample_entry)
    parts = [box(b"mdia", mdhd, hdlr, box(b"minf", box(b"stbl", stsd)))]
    if edit_s is not None:  # one edit segment, in the movie timescale (1000)
        elst = full_box(b"elst", struct.pack(">IIiI", 1, int(edit_s * 1000), 0, 1 << 16))
        parts.insert(0, box(b"edts", elst))
    return box(b"trak", *parts)


def make_mp4(duration_s: float, payload: int = 1000, timescale: int = 1000, tracks: tuple[bytes, ...] = ()) -> bytes:
    """Smallest file the mp4 module understands: ftyp + moov (mvhd + tracks) + mdat."""
    mvhd = full_box(b"mvhd", bytes(8), struct.pack(">II", timescale, int(duration_s * timescale)), bytes(80))
    ftyp = box(b"ftyp", b"isom", bytes(4))
    return ftyp + box(b"moov", mvhd, *tracks) + box(b"mdat", bytes(payload))


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
