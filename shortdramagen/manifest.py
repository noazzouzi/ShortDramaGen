"""manifest.json: per-series state, so that a re-run only does what is missing.

Schema version 2 adds what an interface needs: when and how the series was
requested, languages, the local cover, and per episode an error code, the
number of attempts and the end time. Version-1 manifests are read as is and
upgraded on the next ``open``.
"""

from __future__ import annotations

import json
import threading
from datetime import datetime, timezone
from pathlib import Path
from typing import Callable

from . import fsutil
from .models import Series

FILENAME = "manifest.json"
SCHEMA_VERSION = 2

# Called after every save with the manifest and the episode number that changed
# (None when the change is not about one episode).
Listener = Callable[["Manifest", "int | None"], None]


class ManifestError(Exception):
    pass


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def read_json(path: Path) -> dict:
    """The manifest as a dict; a clear error instead of a traceback when it is corrupt."""
    try:
        data = json.loads(fsutil.read_text(path))
    except (json.JSONDecodeError, UnicodeDecodeError) as e:
        raise ManifestError(f"{path} est illisible ({e}).") from None
    if not isinstance(data, dict):
        raise ManifestError(f"{path} est illisible (pas un objet JSON).")
    return data


class Manifest:
    def __init__(self, path: Path, data: dict, listener: Listener | None = None):
        self.path = path
        self.data = data
        self.listener = listener
        self._lock = threading.Lock()

    @classmethod
    def open(
        cls,
        series_dir: Path,
        series: Series,
        requested: dict | None = None,
        listener: Listener | None = None,
    ) -> "Manifest":
        """Create or refresh the manifest from fresh metadata, at the start of a fetch.

        A corrupt file is set aside (manifest.corrupt-<date>.json) and rebuilt:
        the episodes on disk are then found again by their verification.
        Episodes left in "downloading" by an interrupted run go back to "pending",
        since no download can be running while a new fetch starts.
        """
        path = series_dir / FILENAME
        data: dict = {}
        if path.exists():
            try:
                data = read_json(path)
            except ManifestError:
                stamp = datetime.now().strftime("%Y%m%d-%H%M%S")
                fsutil.replace(path, path.with_name(f"manifest.corrupt-{stamp}.json"))
        previous = {e["number"]: e for e in data.get("episodes", []) if isinstance(e, dict) and "number" in e}
        data.update(
            schema_version=SCHEMA_VERSION,
            platform=series.provider,
            book_id=series.book_id,
            source_book_id=series.source_book_id,
            lang=series.lang,
            title=series.title,
            title_vo=series.title_vo,
            slug=series.slug,
            cover=series.cover,
            introduction=series.introduction,
            languages=series.languages,
            from_official=series.from_official,
            free_only=series.free_only,
            episode_count=series.episode_count,
            total_duration_ms=series.total_duration_ms,
        )
        data.setdefault("created_at", now_iso())
        if requested is not None:
            data["requested"] = requested
        episodes = []
        for ep in series.episodes:
            entry = {**previous.get(ep.number, {"status": "pending"})}
            if entry.get("status") == "downloading":
                entry["status"] = "pending"  # interrupted run: nothing is downloading now
            entry.update(number=ep.number, chapter_id=ep.chapter_id, media_id=ep.media_id, duration_ms=ep.duration_ms)
            episodes.append(entry)
        data["episodes"] = episodes
        manifest = cls(path, data, listener)
        manifest.save()
        return manifest

    @classmethod
    def load(cls, series_dir: Path, listener: Listener | None = None) -> "Manifest | None":
        """Existing manifest as is (no network, no merge with fresh metadata)."""
        path = series_dir / FILENAME
        if not path.exists():
            return None
        return cls(path, read_json(path), listener)

    def set(self, key: str, value) -> None:
        with self._lock:
            self.data[key] = value
            self._save_locked()
        self._notify(None)

    def episode(self, number: int) -> dict:
        for entry in self.data["episodes"]:
            if entry["number"] == number:
                return entry
        raise KeyError(number)

    def update(self, number: int, **fields) -> None:
        with self._lock:
            entry = self.episode(number)
            status = fields.get("status")
            if status in ("downloading", "done", "pending"):
                # A previous failure no longer describes this episode.
                entry.pop("error", None)
                entry.pop("error_code", None)
            if status in ("done", "failed"):
                fields.setdefault("finished_at", now_iso())
            entry.update(fields)
            self._save_locked()
        self._notify(number)

    def count_attempt(self, number: int) -> int:
        with self._lock:
            entry = self.episode(number)
            entry["attempts"] = entry.get("attempts", 0) + 1
            self._save_locked()
            attempts = entry["attempts"]
        self._notify(number)
        return attempts

    def save(self) -> None:
        with self._lock:
            self._save_locked()
        self._notify(None)

    def _save_locked(self) -> None:
        self.data["updated_at"] = now_iso()
        fsutil.write_text(self.path, json.dumps(self.data, ensure_ascii=False, indent=2))

    def _notify(self, number: int | None) -> None:
        if self.listener:
            self.listener(self, number)
