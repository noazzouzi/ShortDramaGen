"""Library index: the downloaded series, as the interface shows them.

Each folder ``<bookId>-<slug>[-<lang>]`` with a manifest.json is a *version* of
a series; the versions of one book id form a *group*. What the manifest says
is reconciled with what is really on disk (docs/frontend/spec-v1.md §10.1):
a "done" episode whose file was deleted is "missing", a .part left by an
interrupted run is "partial", and so on.

Two rules keep the server safe:
- a file is served only if its path is rebuilt here (never taken from a
  request or read as is from a manifest) and resolves inside the folder;
- signed CDN URLs never leave this module (error texts are cleaned too).
"""

from __future__ import annotations

import json
import os
import re
import shutil
import stat
import threading
import time
from collections import Counter
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Callable

from . import errors, film, fsutil
from .manifest import FILENAME, ManifestError, read_json
from .models import ref_key
from .pipeline import COVER_FILE
from .providers import registry

# "<id>-<slug>" (DramaBox) or "<platform>-<id>-<slug>" (pipeline.series_dir_name)
KEY_RE = re.compile(r"^(?:[a-z][a-z0-9]{1,19}-)?\d{6,20}-[a-z0-9][a-z0-9._-]{0,159}$")
_EPISODE_FILE_RE = re.compile(r"^E(\d{3,4})\.mp4$")
_PART_FILE_RE = re.compile(r"^E(\d{3,4})\..*\.part$")
_URL_RE = re.compile(r"\b(?:https?|ftp)://\S+", re.IGNORECASE)
RESCAN_INTERVAL = 2.0  # seconds: a GET younger than this reuses the last scan

# Statuses exposed per episode (the manifest only knows pending/downloading/done/failed/removed).
STATUSES = (
    "done", "done_unverified", "missing", "downloading", "partial", "queued",
    "pending", "not_requested", "unavailable", "failed", "removed",
)  # fmt: skip


class LibraryError(Exception):
    """``code``: not_found (unknown series, episode or file) or outside_library."""

    def __init__(self, message: str, code: str = "not_found"):
        super().__init__(message)
        self.code = code


@dataclass(frozen=True)
class FileInfo:
    size: int
    mtime_ns: int


@dataclass
class DirContents:
    episodes: dict[int, FileInfo] = field(default_factory=dict)
    parts: dict[int, int] = field(default_factory=dict)  # episode -> bytes of its largest .part
    mp4: dict[str, FileInfo] = field(default_factory=dict)  # other .mp4 files (films)
    cover: FileInfo | None = None


@dataclass
class Version:
    key: str
    path: Path
    data: dict
    files: DirContents
    stamp: tuple
    summary: dict
    episodes: list[dict]


def clean_text(text) -> str | None:
    """A message without any URL (the manifest keeps signed URLs in some errors)."""
    if text is None:
        return None
    return _URL_RE.sub("[lien masqué]", str(text))


def scan_dir(path: Path) -> DirContents:
    contents = DirContents()
    with os.scandir(path) as entries:
        for entry in entries:
            try:
                if not entry.is_file(follow_symlinks=False):
                    continue
                st = entry.stat(follow_symlinks=False)
            except OSError:
                continue
            info = FileInfo(st.st_size, st.st_mtime_ns)
            name = entry.name
            if m := _EPISODE_FILE_RE.match(name):
                contents.episodes[int(m.group(1))] = info
            elif m := _PART_FILE_RE.match(name):
                n = int(m.group(1))
                contents.parts[n] = max(contents.parts.get(n, 0), info.size)
            elif name == COVER_FILE:
                contents.cover = info
            elif name.lower().endswith(".mp4"):
                contents.mp4[name] = info
    return contents


def _iso_from_ns(ns: int) -> str:
    return datetime.fromtimestamp(ns / 1e9, timezone.utc).isoformat(timespec="seconds")


def _int_list(value) -> list[int]:
    return sorted({v for v in value if isinstance(v, int) and not isinstance(v, bool)}) if isinstance(value, list) else []


def _ranges(numbers: list[int]) -> str:
    return film.format_ranges(numbers) if numbers else ""


def _wanted(requested) -> list[tuple[int, int | None]] | None:
    """requested.episodes of the manifest: [[1, 10], [28, 28], [50, null]] or None (all)."""
    ranges = requested.get("episodes") if isinstance(requested, dict) else None
    if not isinstance(ranges, list):
        return None
    out = []
    for r in ranges:
        if isinstance(r, list) and len(r) == 2 and isinstance(r[0], int) and (r[1] is None or isinstance(r[1], int)):
            out.append((r[0], r[1]))
    return out or None


def _in(n: int, wanted) -> bool:
    return wanted is None or any(a <= n and (b is None or n <= b) for a, b in wanted)


# --- one version ----------------------------------------------------------------------


def describe(key: str, data: dict, files: DirContents) -> tuple[dict, list[dict]]:
    """Summary and episode list of one version: the manifest reconciled with the disk."""
    book_id = str(data.get("book_id") or key.split("-", 1)[0])
    provider = registry.get(data.get("platform") if data.get("platform") in registry.names() else None)
    source_book_id = str(data.get("source_book_id") or book_id)
    title = str(data.get("title") or book_id)
    from_official = data.get("from_official")
    if not isinstance(from_official, bool):  # schema 1: a probed series is titled by its id
        from_official = title != book_id
    if title == book_id:  # probed series: no official title
        title = f"Série {book_id}"
    wanted = _wanted(data.get("requested"))
    media = f"/media/series/{key}"

    entries = [e for e in data.get("episodes") or [] if isinstance(e, dict) and isinstance(e.get("number"), int)]
    entries.sort(key=lambda e: e["number"])
    episodes = []
    for e in entries:
        n = e["number"]
        manifest_status = e.get("status") or "pending"
        file = files.episodes.get(n)
        part = files.parts.get(n)
        duration_ms = e.get("duration_ms")
        item: dict = {
            "n": n,
            "duration_s": round(duration_ms / 1000, 3) if isinstance(duration_ms, (int, float)) and duration_ms > 0 else None,
        }
        if file:
            if manifest_status == "done":
                item["status"] = "done" if from_official else "done_unverified"
                if isinstance(e.get("bytes"), int) and e["bytes"] != file.size:
                    item["suspect"] = True  # changed since it was verified
            else:  # pending, failed, removed…: the next fetch will verify it
                item["status"] = "done_unverified"
            item.update(bytes=file.size, media_url=f"{media}/episodes/{n}")
        elif manifest_status == "done":
            item["status"] = "missing"
        elif manifest_status == "removed":
            item["status"] = "removed"
        elif manifest_status == "failed":
            item["status"] = "unavailable" if e.get("error_code") == errors.EP_UNAVAILABLE else "failed"
        elif part:
            item["status"] = "partial"
        else:  # pending, or downloading left by an interrupted run without any byte
            item["status"] = "pending" if _in(n, wanted) else "not_requested"
        if part and not file:
            item["part_bytes"] = part
        if item["status"] in ("failed", "unavailable"):
            item["error_code"] = e.get("error_code") or errors.UNKNOWN
            item["error"] = clean_text(e.get("error"))
        for name in ("quality", "quality_requested", "origin", "attempts", "finished_at"):
            if e.get(name) is not None and (name != "quality" or file or item["status"] == "missing"):
                item[name] = e[name]
        episodes.append(item)

    counts_out = count_statuses(episodes)
    counts = Counter(counts_out)
    present = [item for item in episodes if item.get("media_url")]
    episodes_bytes = sum(item["bytes"] for item in present)
    parts_bytes = sum(files.parts.values())
    qualities = Counter(item["quality"] for item in present if item.get("quality"))

    total_ms = data.get("total_duration_ms")
    if isinstance(total_ms, (int, float)) and total_ms > 0:
        duration_s = round(total_ms / 1000, 3)
    elif episodes and all(item["duration_s"] for item in episodes):
        duration_s = round(sum(item["duration_s"] for item in episodes), 3)
    else:
        duration_s = None

    if counts["partial"]:
        state = "interrupted"
    elif counts["failed"] or counts["unavailable"] or counts["missing"]:
        state = "failed"
    elif len(present) + counts["removed"] < len(episodes) - (counts["not_requested"] if data.get("free_only") else 0):
        state = "incomplete"  # on a free-only platform, the paid episodes can never be downloaded
    else:
        state = "complete"

    languages = [str(x) for x in data.get("languages") or [] if isinstance(x, str)]
    summary = {
        "series_key": key,
        "provider": provider.name,
        "provider_label": provider.label,
        "ref": ref_key(provider.name, book_id),
        "free_only": bool(data.get("free_only")),
        "book_id": book_id,
        "slug": str(data.get("slug") or "") or None,
        "source_book_id": source_book_id,
        "lang": str(data.get("lang") or ""),
        "is_original": source_book_id == book_id,
        "title": title,
        "title_vo": str(data.get("title_vo") or "") or None,
        "from_official": from_official,
        "cover_url": f"{media}/cover?v={files.cover.mtime_ns}" if files.cover else None,
        "state": state,
        "counts": counts_out,
        "bytes": episodes_bytes + parts_bytes,
        "episodes_bytes": episodes_bytes,
        "parts_bytes": parts_bytes,
        "duration_s": duration_s,
        "qualities": dict(qualities.most_common()),
        "film": describe_film(key, data, files, episodes),
        "job": None,
        "ignored": [],
        "languages": languages,
        "created_at": data.get("created_at"),
        "updated_at": data.get("updated_at"),
    }
    return summary, episodes


def count_statuses(episodes: list[dict]) -> dict:
    counts = Counter(item["status"] for item in episodes)
    out = {status: counts.get(status, 0) for status in STATUSES}
    out["total"] = len(episodes)
    out["suspect"] = sum(1 for item in episodes if item.get("suspect"))
    return out


JOB_STATES = {"running": "active", "pausing": "active", "cancelling": "active", "queued": "queued",
              "paused": "paused", "interrupted": "interrupted"}  # fmt: skip


def with_job(summary: dict, episodes: list[dict], data: dict, job: dict | None) -> tuple[dict, list[dict]]:
    """The version as seen while a job works on it: episodes "downloading" or "queued"."""
    if not job:
        return summary, episodes
    info = {k: job.get(k) for k in ("id", "kind", "status", "phase", "position", "film_after")}
    if job.get("kind") != "fetch":
        return {**summary, "job": info}, episodes
    raw = {e.get("number"): e.get("status") for e in data.get("episodes") or [] if isinstance(e, dict)}
    selected = set(job["selected"]) if job.get("selected") else None
    ranges = job.get("ranges")
    running = job["status"] in ("running", "pausing", "cancelling")
    waiting = job["status"] in ("queued", "running", "pausing")
    todo = ("pending", "not_requested", "partial", "failed", "unavailable", "missing")

    def wanted(n: int) -> bool:
        if selected is not None:
            return n in selected
        return ranges is None or any(a <= n and (b is None or n <= b) for a, b in ranges)

    out = []
    for item in episodes:
        status = item["status"]
        if running and raw.get(item["n"]) == "downloading" and not item.get("media_url"):
            status = "downloading"
        elif waiting and status in todo and wanted(item["n"]):
            status = "queued"
        out.append(item if status == item["status"] else {**item, "status": status})
    return {**summary, "counts": count_statuses(out), "state": JOB_STATES.get(job["status"], summary["state"]), "job": info}, out


def describe_film(key: str, data: dict, files: DirContents, episodes: list[dict]) -> dict | None:
    record = data.get("film")
    if not isinstance(record, dict) or not isinstance(record.get("file"), str) or not record["file"]:
        return None
    name = record["file"]
    numbers = _int_list(record.get("episodes"))
    out = {
        "file": Path(name).name,
        "episodes": _ranges(numbers),
        "episode_count": len(numbers),
        "missing": _int_list(record.get("missing")),
        "mode": record.get("mode") or "copy",
        "chapters": record.get("chapters") if isinstance(record.get("chapters"), int) else 0,
        "duration_s": record.get("duration_s"),
        "created_at": record.get("created_at"),
    }
    if not film_name_ok(name):
        return {**out, "state": "outside"}  # created elsewhere with -f: never served
    info = files.mp4.get(name)
    if info is None:
        return {**out, "state": "missing_file"}
    in_film = set(numbers)
    present = {item["n"] for item in episodes if item.get("media_url")}
    added = sorted(present - in_film)
    newer = any(files.episodes[n].mtime_ns > info.mtime_ns for n in in_film if n in files.episodes)
    if added or newer:
        state = "stale"
    elif {item["n"] for item in episodes} - in_film:
        state = "partial"
    else:
        state = "ready"
    out.update(
        state=state,
        bytes=info.size,
        added_since=added,
        media_url=f"/media/series/{key}/film",
        chapters_url=f"/media/series/{key}/film/chapters.vtt" if out["chapters"] else None,
    )
    return out


def film_name_ok(name: str) -> bool:
    """A film is served only if the manifest names a plain .mp4 file of the series folder."""
    return (
        Path(name).name == name
        and name not in (".", "..")
        and name.lower().endswith(".mp4")
        and not _EPISODE_FILE_RE.match(name)
        and "\\" not in name
        and "/" not in name
    )


# --- ignored problems ----------------------------------------------------------------------

IGNORABLE = ("failed", "interrupted", "incomplete", "unverified", "film_stale")


class IgnoredStore:
    """``<downloads>/.sdg/ignored.json``: problems the user chose to stop seeing in « À traiter »."""

    def __init__(self, root: Path):
        self.path = Path(root) / ".sdg" / "ignored.json"
        self.version = 0
        self._lock = threading.Lock()
        try:
            data = json.loads(self.path.read_text(encoding="utf-8"))
            self._data = {k: [p for p in v if p in IGNORABLE] for k, v in data.items() if isinstance(v, list)}
        except (OSError, ValueError, AttributeError):
            self._data = {}

    def get(self) -> dict:
        with self._lock:
            return {k: list(v) for k, v in self._data.items()}

    def set(self, key: str, problem: str, ignored: bool) -> list[str]:
        if problem not in IGNORABLE:
            raise ValueError(f"problème inconnu : {problem}")
        with self._lock:
            current = [p for p in self._data.get(key, []) if p != problem] + ([problem] if ignored else [])
            if current:
                self._data[key] = current
            else:
                self._data.pop(key, None)
            self.version += 1
            self.path.parent.mkdir(parents=True, exist_ok=True)
            fsutil.write_text(self.path, json.dumps(self._data, ensure_ascii=False, indent=1))
            return current


# --- the index -------------------------------------------------------------------------


class LibraryIndex:
    """Scan of ``root``, cached per folder (manifest mtime and size, folder mtime)."""

    def __init__(self, root: Path):
        self.root = Path(root)
        self.version = 0
        self._versions: dict[str, Version] = {}
        self._problems: list[dict] = []
        self._root_error: str | None = None
        self._scanned_at: float | None = None
        self._lock = threading.RLock()
        # Set by the server: unfinished jobs per series (step 2) and ignored problems.
        self.job_overlay: Callable[[], dict] = dict
        self.ignored: Callable[[], dict] = dict

    def set_root(self, root: Path) -> None:
        with self._lock:
            self.root = Path(root)
            self._versions, self._problems, self._scanned_at = {}, [], None
            self.refresh(force=True)

    # scanning

    def refresh(self, max_age: float = RESCAN_INTERVAL, force: bool = False) -> bool:
        """Re-read what changed on disk; True if the library changed (version bumped)."""
        with self._lock:
            now = time.monotonic()
            if not force and self._scanned_at is not None and now - self._scanned_at < max_age:
                return False
            found: dict[str, Version] = {}
            problems: list[dict] = []
            root_error = None
            try:
                entries = sorted(os.scandir(self.root), key=lambda e: e.name)
            except FileNotFoundError:
                entries, root_error = [], "not_found"
            except OSError as e:
                entries, root_error = [], f"unreadable: {e.strerror or e}"
            for entry in entries:
                version = self._scan_folder(entry.name, problems)
                if version:
                    found[version.key] = version
            changed = (
                found.keys() != self._versions.keys()
                or any(found[k] is not self._versions[k] for k in found)
                or problems != self._problems
                or root_error != self._root_error
                or self._scanned_at is None
            )
            if changed:
                self.version += 1
            self._versions, self._problems, self._root_error = found, problems, root_error
            self._scanned_at = time.monotonic()
            return changed

    def _scan_folder(self, name: str, problems: list[dict]) -> Version | None:
        if name.startswith("."):
            return None
        path = self.root / name
        try:
            dir_stat = os.lstat(path)
            if not stat.S_ISDIR(dir_stat.st_mode):  # files and symbolic links are ignored
                return None
            manifest_stat = os.stat(path / FILENAME)
        except FileNotFoundError:
            return None
        except OSError as e:
            problems.append({"folder": name, "code": "unreadable", "message": f"Dossier illisible : {e.strerror or e}"})
            return None
        if not KEY_RE.match(name):
            problems.append({
                "folder": name, "code": "invalid_name",
                "message": "Nom de dossier inattendu : il doit commencer par le numéro de la série (ex. 41000105199-titre).",
            })  # fmt: skip
            return None
        stamp = (manifest_stat.st_mtime_ns, manifest_stat.st_size, dir_stat.st_mtime_ns)
        old = self._versions.get(name)
        if old and old.stamp == stamp:
            return old
        try:
            data = read_json(path / FILENAME)
            files = scan_dir(path)
        except ManifestError:
            problems.append({"folder": name, "code": "manifest_unreadable", "message": "manifest.json illisible (fichier abîmé)."})
            return None
        except OSError as e:
            problems.append({"folder": name, "code": "unreadable", "message": f"Dossier illisible : {e.strerror or e}"})
            return None
        summary, episodes = describe(name, data, files)
        if not summary["updated_at"]:
            summary["updated_at"] = _iso_from_ns(manifest_stat.st_mtime_ns)
        return Version(name, path, data, files, stamp, summary, episodes)

    def refresh_keys(self, keys) -> list[str]:
        """Re-read only these folders (during a download); returns those that changed."""
        changed = []
        with self._lock:
            for key in keys:
                if not KEY_RE.match(key or ""):
                    continue
                old = self._versions.get(key)
                new = self._scan_folder(key, [])
                if new is old:
                    continue
                if new is None:
                    del self._versions[key]
                else:
                    self._versions[key] = new
                changed.append(key)
            if changed:
                self.version += 1
        return changed

    # reading

    def _get(self, key: str) -> Version:
        if not KEY_RE.match(key or ""):
            raise LibraryError("Série introuvable dans la bibliothèque.")
        with self._lock:
            version = self._versions.get(key)
            if version is None and self.refresh_keys([key]):  # created since the last scan
                version = self._versions.get(key)
        if version is None:
            raise LibraryError("Série introuvable dans la bibliothèque.")
        return version

    def summary(self, key: str) -> dict:
        return self._get(key).summary

    def _view(self, v: Version, jobs: dict, ignored: dict) -> tuple[dict, list[dict]]:
        summary, episodes = with_job(v.summary, v.episodes, v.data, jobs.get(v.key))
        if ignored.get(v.key):
            summary = {**summary, "ignored": list(ignored[v.key])}
        return summary, episodes

    def keys(self) -> list[str]:
        with self._lock:
            return list(self._versions)

    def library(self, preferred_langs: list[str] = (), title_lang: str = "preferred") -> dict:
        with self._lock:
            versions = list(self._versions.values())
            problems = list(self._problems)
            version, root_error = self.version, self._root_error
        jobs, ignored = self.job_overlay(), self.ignored()
        views = {v.key: self._view(v, jobs, ignored)[0] for v in versions}
        groups: dict[str, list[Version]] = {}
        for v in versions:
            groups.setdefault(v.summary["ref"], []).append(v)
        out_groups = [self._group(ref, vs, preferred_langs, title_lang, views) for ref, vs in groups.items()]
        out_groups.sort(key=lambda g: g["updated_at"] or "", reverse=True)

        episodes_bytes = sum(v.summary["episodes_bytes"] for v in versions)
        parts_bytes = sum(v.summary["parts_bytes"] for v in versions)
        films = [v.summary["film"] for v in versions if v.summary["film"] and v.summary["film"].get("bytes")]
        films_bytes = sum(f["bytes"] for f in films)
        freeable = sum(
            v.summary["episodes_bytes"] for v in versions if (v.summary["film"] or {}).get("state") == "ready"
        )
        try:
            free_bytes = shutil.disk_usage(self.root).free if not root_error else None
        except OSError:
            free_bytes = None
        return {
            "version": version,
            "root": str(self.root),
            "root_error": root_error,
            "stats": {
                "groups": len(out_groups),
                "versions": len(versions),
                "bytes": episodes_bytes + parts_bytes + films_bytes,
                "episodes_bytes": episodes_bytes,
                "parts_bytes": parts_bytes,
                "films_bytes": films_bytes,
                "freeable_bytes": freeable,
                "free_bytes": free_bytes,
            },
            "groups": out_groups,
            "problems": problems,
        }

    @staticmethod
    def _order(vs: list[Version]) -> list[Version]:
        """VO first, then the order of the series' languages, then alphabetical."""
        languages = next((v.summary["languages"] for v in vs if v.summary["languages"]), [])

        def rank(v: Version):
            lang = v.summary["lang"]
            return (not v.summary["is_original"], languages.index(lang) if lang in languages else len(languages), lang, v.key)

        return sorted(vs, key=rank)

    def _group(self, ref: str, vs: list[Version], preferred_langs, title_lang: str, views: dict) -> dict:
        vs = self._order(vs)
        summaries = [views[v.key] for v in vs]
        original = next((s for s in summaries if s["is_original"]), None)
        title_vo = (original or {}).get("title") or summaries[0]["title_vo"] or summaries[0]["title"]
        display = None
        if title_lang == "preferred":
            for lang in preferred_langs:
                display = next((s["title"] for s in summaries if s["lang"] == lang), None)
                if display:
                    break
        if not display:
            display = title_vo if title_lang == "original" else (original or summaries[0])["title"]
        languages: list[str] = []
        for s in summaries:
            languages += [lang for lang in s["languages"] if lang not in languages]
        cover = next((s["cover_url"] for s in ([original] if original else []) + summaries if s["cover_url"]), None)
        return {
            "ref": ref,
            "provider": summaries[0]["provider"],
            "provider_label": summaries[0]["provider_label"],
            "book_id": summaries[0]["book_id"],
            "display_title": display,
            "title_vo": title_vo,
            "titles": {(s["lang"] or "vo"): s["title"] for s in summaries},
            "cover_url": cover,
            "languages_available": languages,
            "updated_at": max((s["updated_at"] or "" for s in summaries), default="") or None,
            "versions": summaries,
        }

    def series(self, key: str) -> dict:
        v = self._get(key)
        data = v.data
        jobs, ignored = self.job_overlay(), self.ignored()
        summary, episodes = self._view(v, jobs, ignored)
        siblings = []
        for s in self._order([x for x in self._all() if x.summary["ref"] == v.summary["ref"]]):
            view = self._view(s, jobs, ignored)[0]
            siblings.append({
                "series_key": s.key, "lang": view["lang"], "is_original": view["is_original"], "title": view["title"],
                "state": view["state"], "done": len([e for e in s.episodes if e.get("media_url")]), "total": view["counts"]["total"],
            })  # fmt: skip
        expiries = [e.get("url_expires_at") for e in data.get("episodes") or [] if isinstance(e, dict)]
        expiries = [x for x in expiries if isinstance(x, str)]
        requested = data.get("requested") if isinstance(data.get("requested"), dict) else None
        return {
            **summary,
            "introduction": data.get("introduction"),
            "episode_count": data.get("episode_count") or v.summary["counts"]["total"],
            "requested": {k: requested.get(k) for k in ("lang", "quality", "episodes", "at")} if requested else None,
            "path": str(v.path.resolve()),
            "versions": siblings,
            "active_job_id": (summary.get("job") or {}).get("id"),
            "manifest_updated_at": v.summary["updated_at"],
            "url_expires_at_min": min(expiries) if expiries else None,
            "episodes": episodes,
        }

    def _all(self) -> list[Version]:
        with self._lock:
            return list(self._versions.values())

    # files (the only way the server finds a path)

    def _safe_file(self, v: Version, name: str) -> Path:
        candidate = v.path / name
        try:
            real = candidate.resolve(strict=True)
            folder = v.path.resolve(strict=True)
            root = self.root.resolve(strict=True)
        except (OSError, RuntimeError):
            raise LibraryError("Fichier introuvable.") from None
        if real.parent != folder or not real.is_relative_to(root) or not real.is_file():
            raise LibraryError("Ce fichier est en dehors de la bibliothèque.", "outside_library")
        return real

    def episode_file(self, key: str, n: int) -> Path:
        v = self._get(key)
        if not any(e["n"] == n for e in v.episodes):
            raise LibraryError(f"Épisode {n} inconnu pour cette série.")
        return self._safe_file(v, f"E{n:03d}.mp4")

    def film_record(self, key: str) -> tuple[Version, dict]:
        v = self._get(key)
        record = v.data.get("film")
        if not isinstance(record, dict) or not isinstance(record.get("file"), str):
            raise LibraryError("Aucun film pour cette série.")
        if not film_name_ok(record["file"]):
            raise LibraryError("Ce film a été créé en dehors du dossier de la série.", "outside_library")
        return v, record

    def film_file(self, key: str) -> Path:
        v, record = self.film_record(key)
        return self._safe_file(v, record["file"])

    def cover_file(self, key: str) -> Path:
        return self._safe_file(self._get(key), COVER_FILE)

    def chapters_vtt(self, key: str) -> str:
        v, record = self.film_record(key)
        self._safe_file(v, record["file"])
        marks = chapter_marks(v, record)
        if not marks:
            raise LibraryError("Ce film n'a pas de chapitres.")
        lines = ["WEBVTT", ""]
        for i, (n, start, end) in enumerate(marks, 1):
            lines += [str(i), f"{_vtt_time(start)} --> {_vtt_time(end)}", f"Épisode {n}", ""]
        return "\n".join(lines)


def chapter_marks(v: Version, record: dict) -> list[tuple[int, float, float]]:
    """Chapter times of a film: from the manifest, else recomputed like film.py does."""
    stored = record.get("chapter_times")
    if isinstance(stored, list) and stored:
        try:
            return [(int(n), float(start), float(end)) for n, start, end in stored]
        except (TypeError, ValueError):
            pass
    if not record.get("chapters"):
        return []
    numbers = _int_list(record.get("episodes"))
    if not numbers:
        return []
    try:  # films made before chapter_times was stored: same computation as the build
        plan = film.plan_film(v.path, allow_missing=True, only=set(numbers))
        if [p.number for p in plan.parts] == numbers:
            return film.chapter_marks(plan, record.get("mode") == "reencode")
    except (film.FilmError, OSError):
        pass
    durations = {e["n"]: e.get("duration_s") for e in v.episodes}
    if not all(durations.get(n) for n in numbers):
        return []
    marks, start = [], 0.0
    for n in numbers:
        marks.append((n, start, start + durations[n]))
        start += durations[n]
    return marks


def _vtt_time(seconds: float) -> str:
    ms = round(seconds * 1000)
    h, rest = divmod(ms, 3_600_000)
    m, rest = divmod(rest, 60_000)
    s, ms = divmod(rest, 1000)
    return f"{h:02d}:{m:02d}:{s:02d}.{ms:03d}"
