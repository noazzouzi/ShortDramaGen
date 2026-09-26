"""Read what we need from MP4 files (duration, codec parameters) without ffmpeg."""

from __future__ import annotations

import struct
from dataclasses import dataclass
from pathlib import Path
from typing import BinaryIO, Iterator


@dataclass(frozen=True)
class TrackInfo:
    kind: str  # "vide" or "soun" (MP4 handler type)
    codec: str  # sample entry fourcc: "avc1", "hvc1", "mp4a", ...
    width: int = 0
    height: int = 0
    channels: int = 0
    sample_rate: int = 0
    config: bytes = b""  # decoder configuration (avcC/hvcC, AAC AudioSpecificConfig)


@dataclass(frozen=True)
class Mp4Info:
    duration: float  # container duration (mvhd): full media extent, AAC priming included
    video: TrackInfo | None
    audio: TrackInfo | None
    presentation: float = 0.0  # what a player shows once edit lists are applied (<= duration)

    @property
    def format_key(self) -> tuple:
        """Files with the same key can be joined without re-encoding.

        Only the decoder configuration matters: DramaBox episodes differ in their
        AAC bitrate fields, which is harmless for a stream copy.
        """
        return (self.video, self.audio)

    def describe(self) -> str:
        parts = []
        if self.video:
            parts.append(f"{self.video.codec} {self.video.width}x{self.video.height}")
        if self.audio:
            parts.append(f"{self.audio.codec} {self.audio.sample_rate} Hz {self.audio.channels} canaux")
        return ", ".join(parts) or "aucune piste"


def _boxes(f: BinaryIO, start: int, end: int) -> Iterator[tuple[bytes, int, int]]:
    """Yield (type, payload_start, box_end) for the boxes in [start, end)."""
    offset = start
    while offset + 8 <= end:
        f.seek(offset)
        header = f.read(8)
        if len(header) < 8:
            return
        size, box_type = struct.unpack(">I4s", header)
        header_size = 8
        if size == 1:
            size = struct.unpack(">Q", f.read(8))[0]
            header_size = 16
        elif size == 0:
            size = end - offset
        if size < header_size:
            return
        yield box_type, offset + header_size, offset + size
        offset += size


def _child(f: BinaryIO, start: int, end: int, *path: bytes) -> tuple[int, int] | None:
    for box_type, payload, box_end in _boxes(f, start, end):
        if box_type == path[0]:
            return (payload, box_end) if len(path) == 1 else _child(f, payload, box_end, *path[1:])
    return None


def _moov(f: BinaryIO, size: int) -> tuple[int, int] | None:
    return _child(f, 0, size, b"moov")


def _timescale_duration(f: BinaryIO, box: tuple[int, int]) -> tuple[int, int]:
    """(timescale, duration) of an mvhd or mdhd box."""
    f.seek(box[0])
    version = f.read(1)[0]
    if version == 1:
        f.seek(box[0] + 20)
        return struct.unpack(">IQ", f.read(12))
    f.seek(box[0] + 12)
    return struct.unpack(">II", f.read(8))


def _mvhd_duration(f: BinaryIO, moov: tuple[int, int]) -> float | None:
    mvhd = _child(f, *moov, b"mvhd")
    if not mvhd:
        return None
    timescale, duration = _timescale_duration(f, mvhd)
    return duration / timescale if timescale else None


def duration_seconds(path: str | Path) -> float | None:
    """Movie duration in seconds, or None if the file is not a readable MP4."""
    path = Path(path)
    with path.open("rb") as f:
        moov = _moov(f, path.stat().st_size)
        return _mvhd_duration(f, moov) if moov else None


def probe(path: str | Path) -> Mp4Info | None:
    """Duration and first video/audio track parameters, or None if not an MP4."""
    path = Path(path)
    with path.open("rb") as f:
        moov = _moov(f, path.stat().st_size)
        if not moov:
            return None
        mvhd = _child(f, *moov, b"mvhd")
        if not mvhd:
            return None
        movie_timescale, movie_duration = _timescale_duration(f, mvhd)
        if not movie_timescale:
            return None
        video = audio = None
        presentation = 0.0
        for box_type, payload, box_end in _boxes(f, *moov):
            if box_type != b"trak":
                continue
            track = _track_info(f, payload, box_end)
            if track and track.kind == "vide" and video is None:
                video = track
            elif track and track.kind == "soun" and audio is None:
                audio = track
            else:
                continue
            presentation = max(presentation, _presented_seconds(f, payload, box_end, movie_timescale))
        duration = movie_duration / movie_timescale
        return Mp4Info(duration, video, audio, presentation or duration)


def _presented_seconds(f: BinaryIO, start: int, end: int, movie_timescale: int) -> float:
    """Track length once its edit list is applied (sum of the edit segments)."""
    elst = _child(f, start, end, b"edts", b"elst")
    if elst:
        f.seek(elst[0])
        version = f.read(1)[0]
        f.seek(elst[0] + 4)
        (count,) = struct.unpack(">I", f.read(4))
        entry = ">QqI" if version == 1 else ">IiI"  # segment duration, media time, rate
        total = sum(struct.unpack(entry, f.read(struct.calcsize(entry)))[0] for _ in range(count))
        if total:
            return total / movie_timescale
    mdhd = _child(f, start, end, b"mdia", b"mdhd")
    if mdhd:
        timescale, duration = _timescale_duration(f, mdhd)
        return duration / timescale if timescale else 0.0
    return 0.0


def _track_info(f: BinaryIO, start: int, end: int) -> TrackInfo | None:
    mdia = _child(f, start, end, b"mdia")
    if not mdia:
        return None
    hdlr = _child(f, *mdia, b"hdlr")
    stsd = _child(f, *mdia, b"minf", b"stbl", b"stsd")
    if not hdlr or not stsd:
        return None
    f.seek(hdlr[0] + 8)
    kind = f.read(4).decode("latin-1")
    # stsd: version/flags (4) + entry count (4), then the first sample entry.
    f.seek(stsd[0] + 8)
    entry_size, fourcc = struct.unpack(">I4s", f.read(8))
    body = f.read(max(0, entry_size - 8))
    codec = fourcc.decode("latin-1")

    if kind == "vide" and len(body) >= 78:
        width, height = struct.unpack(">HH", body[24:28])
        config = _find_config(body, 78, (b"avcC", b"hvcC", b"av1C", b"vpcC"))
        return TrackInfo(kind, codec, width=width, height=height, config=config)
    if kind == "soun" and len(body) >= 28:
        sound_version = struct.unpack(">H", body[8:10])[0]
        channels = struct.unpack(">H", body[16:18])[0]
        sample_rate = struct.unpack(">I", body[24:28])[0] >> 16
        extra = {1: 16, 2: 36}.get(sound_version, 0)  # QuickTime sound description v1/v2
        esds = _find_config(body, 28 + extra, (b"esds",))
        return TrackInfo(kind, codec, channels=channels, sample_rate=sample_rate, config=_aac_config(esds))
    return TrackInfo(kind, codec)


def _find_config(body: bytes, offset: int, names: tuple[bytes, ...]) -> bytes:
    while offset + 8 <= len(body):
        size, box_type = struct.unpack(">I4s", body[offset : offset + 8])
        if size < 8:
            break
        if box_type in names:
            return body[offset + 8 : offset + size]
        offset += size
    return b""


def _aac_config(esds: bytes) -> bytes:
    """AudioSpecificConfig from an esds box (falls back to the raw box)."""

    def descriptor(pos: int) -> tuple[int, int, int]:  # (tag, payload_start, payload_end)
        tag = esds[pos]
        pos += 1
        size = 0
        for _ in range(4):
            byte = esds[pos]
            pos += 1
            size = (size << 7) | (byte & 0x7F)
            if not byte & 0x80:
                break
        return tag, pos, pos + size

    try:
        tag, pos, _ = descriptor(4)  # skip version/flags
        if tag != 0x03:  # ES_Descriptor
            return esds
        flags = esds[pos + 2]
        pos += 3 + (2 if flags & 0x80 else 0) + (2 if flags & 0x20 else 0)
        if flags & 0x40:
            pos += 1 + esds[pos]
        tag, pos, end = descriptor(pos)
        if tag != 0x04:  # DecoderConfigDescriptor
            return esds
        object_type = esds[pos]
        tag, pos, end = descriptor(pos + 13)  # skip the fixed fields (incl. bitrates)
        if tag != 0x05:  # DecoderSpecificInfo
            return esds
        return bytes([object_type]) + esds[pos:end]
    except IndexError:
        return esds
