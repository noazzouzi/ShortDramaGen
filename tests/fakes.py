"""Offline doubles for the network layer."""

from __future__ import annotations

import io
import json
import struct
from contextlib import contextmanager
from pathlib import Path

from shortdramagen import dramafren
from shortdramagen.http import HttpStatusError, Response

FIXTURES = Path(__file__).parent / "fixtures"
AKAMAI = "https://hwztakavideoto.dramaboxdb.com/" + "0" * 32 + "/6ad5b861"
OFFICIAL_EN_URL = "https://www.dramaboxdb.com/movie/41000105199/"


def cdn_url(book_id: str, media_id: str, quality: str) -> str:
    """A signed-looking CDN URL whose path matches the episode (see cdn.expected_path)."""
    r = book_id[::-1]
    seg = media_id[-2:][::-1]
    return f"{AKAMAI}/{seg}/{r[0]}x{r[1]}/{r[:2]}x{r[2]}/{r[:3]}x{r[3]}/{r}/{media_id}_1/{media_id}.{quality}.mp4"


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


def series_http(dramafren_answers=None, broken=(), qualities=("720p", "1080p"), payload=5_000):
    """FakeHttp for the 3-episode fixture (episodes 1, 2 and 28): official page, dramafren API
    answers and CDN files. ``broken``: episodes whose dramafren URLs the CDN refuses (403)."""
    props = fixture_json("official_en.json")
    book = "41000105199"
    pages = {OFFICIAL_EN_URL: official_html(props)}
    files = {}
    answers = dict(dramafren_answers or {})
    for ch in props["chapterList"]:
        number, media_id = ch["index"] + 1, ch["id"]
        video = make_mp4(ch["duration"] / 1000, payload=payload)
        sources = [{"quality": f"Server 1 {q}", "url": cdn_url(book, media_id, q)} for q in qualities]
        for q in sources:
            files[q["url"]] = 403 if number in broken else video
        if ch.get("mp4"):
            files[ch["mp4"]] = video
        answers.setdefault(number, {"ok": True, "videoUrl": sources[0]["url"], "qualities": sources})

    def api(url):
        ep = int(url.split("&ep=")[1].split("&")[0])
        return answers.get(ep, {"ok": False, "error": "Video unavailable"})

    pages[dramafren.ENDPOINTS[0]] = api
    pages[dramafren.ENDPOINTS[1]] = api
    return FakeHttp(pages=pages, files=files)


class FakeHttp:
    """Routes URLs to canned answers.

    ``pages``: url prefix -> str (HTML) | bytes | dict/list (JSON) | int (HTTP status) | callable(url)
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

    def get(self, url, headers=None, timeout=None):
        self.calls.append((url, dict(headers or {})))
        answer = self._lookup(self.pages, url)
        if callable(answer):
            answer = answer(url)
        if isinstance(answer, int):
            raise HttpStatusError(url, answer)
        if isinstance(answer, (dict, list)):
            answer = json.dumps(answer)
        body = answer if isinstance(answer, bytes) else answer.encode("utf-8")
        return Response(url, 200, {}, body)

    def get_json(self, url, headers=None, timeout=None):
        return self.get(url, headers, timeout).json()

    def post_json(self, url, payload, headers=None):
        """Same table as GET; a callable answer receives the payload instead of the URL."""
        self.calls.append((url, dict(headers or {})))
        answer = self._lookup(self.pages, url)
        if callable(answer):
            answer = answer(payload)
        if isinstance(answer, int):
            raise HttpStatusError(url, answer)
        return json.loads(json.dumps(answer))

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
