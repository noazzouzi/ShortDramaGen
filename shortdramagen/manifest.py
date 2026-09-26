"""manifest.json: per-series state, so that a re-run only does what is missing."""

from __future__ import annotations

import json
import os
import threading
from datetime import datetime, timezone
from pathlib import Path

from .models import Series

FILENAME = "manifest.json"


class Manifest:
    def __init__(self, path: Path, data: dict):
        self.path = path
        self.data = data
        self._lock = threading.Lock()

    @classmethod
    def open(cls, series_dir: Path, series: Series) -> "Manifest":
        path = series_dir / FILENAME
        data = json.loads(path.read_text(encoding="utf-8")) if path.exists() else {}
        previous = {e["number"]: e for e in data.get("episodes", [])}
        data.update(
            platform="dramabox",
            book_id=series.book_id,
            source_book_id=series.source_book_id,
            lang=series.lang,
            title=series.title,
            slug=series.slug,
            cover=series.cover,
            introduction=series.introduction,
            episode_count=series.episode_count,
        )
        data["episodes"] = [
            {
                **previous.get(ep.number, {"status": "pending"}),
                "number": ep.number,
                "chapter_id": ep.chapter_id,
                "media_id": ep.media_id,
                "duration_ms": ep.duration_ms,
            }
            for ep in series.episodes
        ]
        manifest = cls(path, data)
        manifest.save()
        return manifest

    @classmethod
    def load(cls, series_dir: Path) -> "Manifest | None":
        """Existing manifest as is (no network, no merge with fresh metadata)."""
        path = series_dir / FILENAME
        if not path.exists():
            return None
        return cls(path, json.loads(path.read_text(encoding="utf-8")))

    def set(self, key: str, value) -> None:
        with self._lock:
            self.data[key] = value
            self._save_locked()

    def episode(self, number: int) -> dict:
        for entry in self.data["episodes"]:
            if entry["number"] == number:
                return entry
        raise KeyError(number)

    def update(self, number: int, **fields) -> None:
        with self._lock:
            entry = self.episode(number)
            entry.update(fields)
            if fields.get("status") == "done":
                entry.pop("error", None)
            self._save_locked()

    def save(self) -> None:
        with self._lock:
            self._save_locked()

    def _save_locked(self) -> None:
        self.data["updated_at"] = datetime.now(timezone.utc).isoformat(timespec="seconds")
        tmp = self.path.with_name(self.path.name + ".tmp")
        tmp.write_text(json.dumps(self.data, ensure_ascii=False, indent=2), encoding="utf-8")
        os.replace(tmp, self.path)
