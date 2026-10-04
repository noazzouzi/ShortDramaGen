"""Job queue of the interface: downloads and films, persisted, run in two lanes.

Lifecycle (docs/frontend/brainstorm/4-recherche-architecture.md §4):

    queued → running → done | failed
    running → pausing → paused → (resume) queued
    running → cancelling → cancelled
    running → interrupted (server stopped, or network down) → queued again

- The download lane runs ``concurrent_series`` series at a time (1 by
  default), each with ``parallel_downloads`` episodes in parallel; the film
  lane runs one merge at a time. Two jobs never touch the same series at once.
- ``<downloads>/.sdg/jobs.json`` keeps the queue across restarts. It is
  written on every change of status, never for progress.
- Everything the interface shows live goes through the event bus: ``job``,
  ``progress`` (not replayed), ``episode``, ``log``, ``library``, ``health``.
"""

from __future__ import annotations

import json
import logging
import secrets
import statistics
import threading
import time
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Callable

from . import errors, film, fsutil, inputs, montage, pipeline
from .connectivity import Connectivity
from .events import EventBus
from .http import TRANSIENT_ERRORS, HttpStatusError
from .library import clean_text
from .manifest import Manifest, ManifestError, now_iso
from .models import DEFAULT_PROVIDER, BookRef, ref_key

log = logging.getLogger("shortdramagen.jobs")

STATE_DIR = ".sdg"
JOBS_FILE = "jobs.json"
SCHEMA = 1
HISTORY_LIMIT = 100
LOG_LINES = 300
PERSISTED_LOG_LINES = 50
TICK = 0.25
OFFLINE_RECHECK = 15.0  # seconds between two connectivity checks while jobs wait for the network
PRIOR_BYTES_PER_MS = 124.0  # 1080p: 684 MB for 5 520 s, measured (docs/01)

RUNNING = frozenset({"running", "pausing", "cancelling"})
TERMINAL = frozenset({"done", "failed", "cancelled"})
OPEN = frozenset({"queued", "paused", "interrupted"}) | RUNNING


class JobError(Exception):
    """A refused command: HTTP status, stable code, message for the user."""

    def __init__(self, status: int, code: str, message: str, details: dict | None = None):
        super().__init__(message)
        self.status = status
        self.code = code
        self.details = details or {}


def new_id() -> str:
    return "j-" + secrets.token_hex(3)


def _clock() -> str:
    return datetime.now().strftime("%H:%M:%S")


# --- progress ---------------------------------------------------------------------------


class FetchProgress:
    """Bytes and episodes of a running download, from the engine's events (in memory only)."""

    def __init__(self):
        self._lock = threading.Lock()
        self.selected: list[int] = []
        self.durations: dict[int, int] = {}
        self.finished: dict[int, int] = {}  # episode -> bytes (done or already there)
        self.counts = {"done": 0, "skipped": 0, "failed": 0}
        self.active: dict[int, list] = {}  # episode -> [written, total, first written seen]
        self.session_bytes = 0  # received during this run by finished episodes
        self.rate = PRIOR_BYTES_PER_MS
        self.probed: int | None = None
        self.started = time.monotonic()
        self.speed: float | None = None
        self._last: tuple[float, int] | None = None
        self.last: dict | None = None

    def start(self, series_dir: Path, selected: list[int]) -> None:
        """Durations and already measured sizes of the series (for the estimated total)."""
        rates, durations = [], {}
        try:
            manifest = Manifest.load(series_dir)
        except ManifestError:
            manifest = None
        for e in (manifest.data.get("episodes") if manifest else None) or []:
            if not isinstance(e, dict) or not isinstance(e.get("number"), int):
                continue
            duration = e.get("duration_ms")
            if isinstance(duration, (int, float)) and duration > 0:
                durations[e["number"]] = duration
                if e.get("status") == "done" and isinstance(e.get("bytes"), int):
                    rates.append(e["bytes"] / duration)
        with self._lock:
            self.selected = list(selected)
            self.durations = durations
            if rates:
                self.rate = statistics.median(rates)

    def on_event(self, name: str, data: dict) -> None:
        n = data.get("n")
        with self._lock:
            if name == "probe_progress":
                self.probed = data.get("found")
            elif name == "episode_skipped":
                self.finished[n] = data.get("bytes") or 0
                self.counts["skipped"] += 1
            elif name == "episode_started":
                self.active[n] = [0, 0, None]
            elif name == "episode_progress":
                entry = self.active.setdefault(n, [0, 0, None])
                if entry[2] is None:
                    entry[2] = data["bytes"]  # resumed .part: bytes before this run do not count for the speed
                entry[0], entry[1] = data["bytes"], data.get("total") or 0
            elif name == "episode_done":
                entry = self.active.pop(n, None)
                size = data.get("bytes") or 0
                self.finished[n] = size
                self.counts["done"] += 1
                self.session_bytes += size - (entry[2] or 0) if entry else size
            elif name in ("episode_failed", "episode_cancelled"):
                entry = self.active.pop(n, None)
                if entry and entry[2] is not None:
                    self.session_bytes += entry[0] - entry[2]
                if name == "episode_failed":
                    self.counts["failed"] += 1

    def snapshot(self, now: float) -> dict:
        with self._lock:
            active_bytes = sum(a[0] for a in self.active.values())
            done_bytes = sum(self.finished.values()) + active_bytes
            known = [b for b in self.finished.values() if b]
            fallback = statistics.median(known) if known else pipeline.BYTES_PER_EPISODE_1080P
            total, estimate = 0, False
            for n in self.selected:
                if n in self.finished:
                    total += self.finished[n]
                elif n in self.active and self.active[n][1]:
                    total += self.active[n][1]
                else:
                    duration = self.durations.get(n)
                    total += int(duration * self.rate) if duration else int(fallback)
                    estimate = True
            session = self.session_bytes + sum(a[0] - a[2] for a in self.active.values() if a[2] is not None)
            if self._last is not None and now > self._last[0]:
                instant = max(0, session - self._last[1]) / (now - self._last[0])
                self.speed = instant if self.speed is None else 0.3 * instant + 0.7 * self.speed
            self._last = (now, session)
            eta = None
            if self.speed and self.speed > 1000 and now - self.started >= 3:
                eta = max(0, round((total - done_bytes) / self.speed))
            finished = sum(self.counts.values())
            self.last = {
                "episodes": {
                    **self.counts,
                    "total": len(self.selected),
                    "active": [{"n": n, "bytes": a[0], "total": a[1]} for n, a in sorted(self.active.items())],
                    "queued": max(0, len(self.selected) - finished - len(self.active)),
                },
                "bytes_done": done_bytes,
                "bytes_total": max(total, done_bytes),
                "total_is_estimate": estimate,
                "speed_bps": round(self.speed) if self.speed is not None else None,
                "eta_s": eta,
                "probed": self.probed,
            }
            return self.last

    def key(self) -> tuple:
        """What must change for a new progress event to be worth sending."""
        last = self.last or {}
        episodes = last.get("episodes") or {}
        return (last.get("bytes_done"), last.get("probed"), tuple(sorted((k, str(v)) for k, v in episodes.items())))


class FilmProgress:
    def __init__(self):
        self.started = time.monotonic()
        self.seconds_done = 0.0
        self.seconds_total = 0.0
        self.last: dict | None = None

    def on_progress(self, done: float, total: float) -> None:
        self.seconds_done, self.seconds_total = done, total

    def snapshot(self, now: float) -> dict:
        elapsed = now - self.started
        eta = None
        if self.seconds_done > 0 and elapsed >= 1:
            eta = max(0, round(elapsed / self.seconds_done * (self.seconds_total - self.seconds_done)))
        self.last = {"seconds_done": round(self.seconds_done, 1), "seconds_total": round(self.seconds_total, 1), "eta_s": eta}
        return self.last

    def key(self) -> tuple:
        return (self.last or {}).get("seconds_done"), (self.last or {}).get("seconds_total")


# --- jobs ------------------------------------------------------------------------------


@dataclass
class Job:
    id: str
    kind: str  # "fetch" or "film"
    params: dict
    status: str = "queued"
    phase: str | None = None
    series_key: str | None = None
    book_id: str | None = None
    lang: str | None = None  # None: original version
    provider: str = DEFAULT_PROVIDER
    title: str | None = None
    cover_url: str | None = None
    created_at: str = field(default_factory=now_iso)
    started_at: str | None = None
    finished_at: str | None = None
    result: dict | None = None
    error: dict | None = None
    reason: str | None = None  # why paused or interrupted: user, shutdown, offline
    then: str | None = None  # film job created at the end of this download
    parent: str | None = None
    selected: list | None = None
    log: list = field(default_factory=list)
    # runtime only
    stop: threading.Event = field(default_factory=threading.Event, repr=False)
    stop_reason: str | None = None
    delete_parts: bool = True
    progress: FetchProgress | FilmProgress | None = None
    fallbacks: dict = field(default_factory=dict)

    PERSISTED = (
        "id", "kind", "params", "status", "phase", "series_key", "book_id", "lang", "provider", "title", "cover_url",
        "created_at", "started_at", "finished_at", "result", "error", "reason", "then", "parent", "selected", "log",
    )  # fmt: skip

    @property
    def lang_key(self) -> str:
        return self.lang or "vo"

    @property
    def ref(self) -> str | None:
        return ref_key(self.provider, self.book_id) if self.book_id else None

    def book_ref(self) -> BookRef:
        """The series to fetch; the typed link is read again for what the id alone lacks (a slug)."""
        try:
            ref = inputs.parse_input(str(self.params.get("input") or ""))
        except inputs.InputError:
            ref = None
        if ref and ref.provider == self.provider and ref.book_id == self.book_id:
            return BookRef(self.book_id, provider=self.provider, slug=ref.slug)
        return BookRef(self.book_id, provider=self.provider)

    def persist(self) -> dict:
        data = {name: getattr(self, name) for name in self.PERSISTED}
        data["log"] = self.log[-PERSISTED_LOG_LINES:]
        return data

    @classmethod
    def restore(cls, data: dict) -> "Job | None":
        if not isinstance(data, dict) or not isinstance(data.get("id"), str) or data.get("kind") not in ("fetch", "film"):
            return None
        values = {name: data.get(name) for name in cls.PERSISTED if name in data}
        values.setdefault("params", {})
        values["log"] = list(values.get("log") or [])
        if not isinstance(values["params"], dict):
            return None
        return cls(**values)

    def to_dict(self, position: int | None = None, with_log: bool = False) -> dict:
        data = {name: getattr(self, name) for name in self.PERSISTED if name != "log"}
        data["ref"] = self.ref
        data["position"] = position
        data["progress"] = self.progress.last if self.progress is not None and self.status in RUNNING else None
        if with_log:
            data["log"] = list(self.log)
        return data


class JobStore:
    """``<downloads>/.sdg/jobs.json``: the queue order and every job, written atomically."""

    def __init__(self, root: Path):
        self.path = Path(root) / STATE_DIR / JOBS_FILE
        self.jobs: dict[str, Job] = {}
        self.order: list[str] = []

    def load(self, resume: bool) -> list[str]:
        """Read the queue after a restart. Returns the ids put back in the queue."""
        data: dict = {}
        if self.path.exists():
            try:
                data = json.loads(self.path.read_text(encoding="utf-8"))
                if not isinstance(data, dict):
                    raise ValueError("not an object")
            except (OSError, ValueError, UnicodeDecodeError):
                log.warning("jobs.json illisible, mis de côté")
                fsutil.replace(self.path, self.path.with_suffix(".bad"))
                data = {}
        jobs = {}
        for raw in (data.get("jobs") or {}).values():
            job = Job.restore(raw)
            if job:
                jobs[job.id] = job
        order = [i for i in data.get("order") or [] if i in jobs]
        order += [i for i in jobs if i not in order]
        for job in jobs.values():
            if job.status in ("running", "pausing"):  # the server stopped while it ran
                job.status, job.phase, job.reason = "interrupted", None, job.reason or "shutdown"
            elif job.status == "cancelling":
                job.status, job.phase, job.finished_at = "cancelled", None, job.finished_at or now_iso()
        requeued = []
        if resume:
            requeued = [i for i in order if jobs[i].status == "interrupted"]
            for i in requeued:
                jobs[i].status, jobs[i].reason = "queued", None
            order = requeued + [i for i in order if i not in requeued]  # interrupted jobs first
        self.jobs, self.order = jobs, order
        return requeued

    def save(self) -> None:
        finished = sorted((j for j in self.jobs.values() if j.status in TERMINAL), key=lambda j: j.finished_at or "")
        for job in finished[: max(0, len(finished) - HISTORY_LIMIT)]:
            del self.jobs[job.id]
        self.order = [i for i in self.order if i in self.jobs]
        data = {"schema": SCHEMA, "order": self.order, "jobs": {i: self.jobs[i].persist() for i in self.order}}
        self.path.parent.mkdir(parents=True, exist_ok=True)
        fsutil.write_text(self.path, json.dumps(data, ensure_ascii=False, indent=1))


# --- runner ----------------------------------------------------------------------------


class JobRunner:
    def __init__(
        self,
        root: Path,
        settings,
        bus: EventBus,
        http,
        library,
        connectivity: Connectivity | None = None,
        limiter: pipeline.RateLimiter | None = None,
        find_ffmpeg: Callable[[str | None], str] = film.find_ffmpeg,
    ):
        self.root = Path(root)
        self.settings = settings
        self.bus = bus
        self.http = http
        self.library = library
        self.connectivity = connectivity or Connectivity()
        self.limiter = limiter or pipeline.RateLimiter(pipeline.DEFAULT_API_INTERVAL)
        self.find_ffmpeg = find_ffmpeg
        self.store = JobStore(self.root)
        self.version = 0  # bumped on every job change (ETag of the library)
        self.tick_hooks: list[Callable[[], None]] = []
        self._lock = threading.RLock()
        self._cond = threading.Condition(self._lock)
        self._threads: dict[str, threading.Thread] = {}
        self._dirty: set[str] = set()
        self._sent: dict[str, tuple] = {}
        self._closing = False
        self._loops: list[threading.Thread] = []
        self._last_offline_check = 0.0

    # life cycle

    def start(self) -> list[str]:
        with self._lock:
            requeued = self.store.load(self.settings["resume_on_start"])
            self.store.save()
            self._closing = False
        self._loops = [
            threading.Thread(target=self._schedule_loop, name="sdg-scheduler", daemon=True),
            threading.Thread(target=self._tick_loop, name="sdg-ticker", daemon=True),
        ]
        for thread in self._loops:
            thread.start()
        return requeued

    def close(self, timeout: float = 5.0) -> None:
        """Stop everything: running jobs become "interrupted" and resume at the next start."""
        with self._cond:
            self._closing = True
            for job in self._running():
                job.stop_reason = "shutdown"
                job.stop.set()
            threads = list(self._threads.values())
            self._cond.notify_all()
        deadline = time.monotonic() + timeout
        for thread in threads:
            thread.join(max(0.0, deadline - time.monotonic()))
        for thread in self._loops:
            thread.join(1.0)
        with self._lock:
            for job in self._running():  # still blocked (frozen network): recorded as interrupted
                job.status, job.phase, job.reason = "interrupted", None, "shutdown"
            self.store.save()

    def set_root(self, root: Path) -> None:
        """Another downloads folder: its own queue (only when nothing is running)."""
        with self._cond:
            if self._threads:
                raise JobError(409, "series_busy", "Tu pourras changer de dossier quand les téléchargements seront finis.")
            self.root = Path(root)
            self.store = JobStore(self.root)
            self.store.load(resume=False)
            self.version += 1
            self._cond.notify_all()

    # queries

    def _running(self) -> list[Job]:
        return [j for j in self.store.jobs.values() if j.status in RUNNING]

    def _position(self, job: Job) -> int | None:
        if job.status != "queued":
            return None
        queued = [i for i in self.store.order if self.store.jobs[i].status == "queued"]
        return queued.index(job.id) + 1

    def get(self, job_id: str) -> Job:
        with self._lock:
            job = self.store.jobs.get(job_id)
            if job is None:
                raise JobError(404, "not_found", "Tâche introuvable.")
            return job

    def describe(self, job: Job, with_log: bool = False) -> dict:
        with self._lock:
            return job.to_dict(self._position(job), with_log)

    def list(self) -> dict:
        with self._lock:
            jobs = [self.store.jobs[i] for i in self.store.order]
            rank = {"running": 0, "pausing": 0, "cancelling": 0, "queued": 1, "interrupted": 2, "paused": 3}
            active = sorted((j for j in jobs if j.status in OPEN), key=lambda j: rank.get(j.status, 4))
            history = sorted((j for j in jobs if j.status in TERMINAL), key=lambda j: j.finished_at or "", reverse=True)
            return {
                "active": [j.to_dict(self._position(j)) for j in active],
                "history": [j.to_dict() for j in history[:50]],
            }

    def counts(self) -> dict:
        with self._lock:
            statuses = [j.status for j in self.store.jobs.values()]
            return {
                "running": sum(s in RUNNING for s in statuses),
                "queued": statuses.count("queued"),
                "paused": statuses.count("paused"),
                "interrupted": statuses.count("interrupted"),
            }

    def has_work(self) -> bool:
        with self._lock:
            return any(j.status in RUNNING or j.status == "queued" for j in self.store.jobs.values())

    def busy(self, series_key: str) -> Job | None:
        """An unfinished job on this series (deletion and a new film must wait)."""
        with self._lock:
            return next(
                (j for j in self.store.jobs.values() if j.status in OPEN and j.series_key == series_key), None
            )

    def open_job_for(self, book_id: str, lang: str | None, provider: str = DEFAULT_PROVIDER) -> Job | None:
        with self._lock:
            return next(
                (j for j in self.store.jobs.values()
                 if j.kind == "fetch" and j.status in OPEN and j.provider == provider and j.book_id == book_id
                 and j.lang_key == (lang or "vo")),
                None,
            )  # fmt: skip

    def overlay(self) -> dict[str, dict]:
        """For the library: which series have an unfinished job, and on which episodes."""
        with self._lock:
            out: dict[str, dict] = {}
            for job_id in self.store.order:
                job = self.store.jobs[job_id]
                if job.status in OPEN and job.series_key and job.series_key not in out:
                    out[job.series_key] = {
                        "id": job.id, "kind": job.kind, "status": job.status, "phase": job.phase,
                        "position": self._position(job), "selected": job.selected,
                        "film_after": bool(job.kind == "fetch" and job.params.get("film_after")),
                    }  # fmt: skip
            return out

    # commands

    def create_fetch(
        self,
        book_id: str,
        lang: str | None,
        params: dict,
        series_key: str | None = None,
        title: str | None = None,
        cover_url: str | None = None,
        parent: str | None = None,
        provider: str = DEFAULT_PROVIDER,
    ) -> Job:
        with self._cond:
            duplicate = self.open_job_for(book_id, lang, provider) or (self.busy(series_key) if series_key else None)
            if duplicate:
                raise JobError(409, "duplicate_job", "Cette série est déjà dans la file.", {"job_id": duplicate.id})
            job = Job(new_id(), "fetch", params, book_id=book_id, lang=lang, provider=provider, series_key=series_key,
                      title=title, cover_url=cover_url, parent=parent)  # fmt: skip
            self._add(job)
            return job

    def create_film(self, series_key: str, book_id: str, lang: str | None, params: dict,
                    title: str | None = None, cover_url: str | None = None, parent: str | None = None,
                    provider: str = DEFAULT_PROVIDER) -> Job:  # fmt: skip
        with self._cond:
            duplicate = next(
                (j for j in self.store.jobs.values() if j.kind == "film" and j.status in OPEN and j.series_key == series_key),
                None,
            )
            if duplicate:
                raise JobError(409, "duplicate_job", "Un film de cette série est déjà en préparation.", {"job_id": duplicate.id})
            job = Job(new_id(), "film", params, book_id=book_id, lang=lang, provider=provider, series_key=series_key,
                      title=title, cover_url=cover_url, parent=parent)  # fmt: skip
            self._add(job)
            return job

    def _add(self, job: Job) -> None:
        self.store.jobs[job.id] = job
        self.store.order.append(job.id)
        self._changed(job, "created")
        self._cond.notify_all()

    def pause(self, job_id: str) -> Job:
        with self._cond:
            job = self.get(job_id)
            if job.status in ("queued", "interrupted"):
                job.status, job.reason = "paused", "user"
                self._changed(job)
            elif job.status == "running":
                job.stop_reason = "pause"
                job.stop.set()
                job.status = "pausing"
                self._changed(job)
            elif job.status not in ("paused", "pausing"):
                raise JobError(409, "invalid_state", "Cette tâche ne peut pas être mise en pause.")
            return job

    def resume(self, job_id: str) -> Job:
        with self._cond:
            job = self.get(job_id)
            if job.status in ("paused", "interrupted", "failed"):
                job.status, job.reason, job.error = "queued", None, None
                self._changed(job)
                self._cond.notify_all()
            elif job.status not in ("queued", "running"):
                raise JobError(409, "invalid_state", "Cette tâche ne peut pas être reprise.")
            return job

    def cancel(self, job_id: str, delete_parts: bool = True) -> Job:
        with self._cond:
            job = self.get(job_id)
            if job.status in ("queued", "paused", "interrupted", "failed"):
                if delete_parts:
                    self._delete_parts(job)
                self._finish(job, "cancelled")
            elif job.status in ("running", "pausing"):
                job.stop_reason = "cancel"
                job.delete_parts = delete_parts
                job.stop.set()
                job.status = "cancelling"
                self._changed(job)
            elif job.status != "cancelling":
                raise JobError(409, "invalid_state", "Cette tâche est déjà terminée.")
            return job

    def remove(self, job_id: str) -> None:
        with self._cond:
            job = self.get(job_id)
            if job.status not in TERMINAL:
                raise JobError(409, "invalid_state", "Mets d'abord la tâche en pause ou annule-la.")
            del self.store.jobs[job_id]
            self.store.order.remove(job_id)
            self.version += 1
            self.store.save()
            self.bus.publish("job", {"op": "removed", "job": {"id": job_id}})

    def connectivity_changed(self) -> None:
        """Back online: the downloads that were waiting for the network start again."""
        if self.connectivity.online is not True:
            return
        with self._cond:
            for job in self.store.jobs.values():
                if job.status == "interrupted" and job.reason == "offline":
                    job.status, job.reason = "queued", None
                    self._changed(job)
            self._cond.notify_all()

    # internals: state changes (always under the lock)

    def _changed(self, job: Job, op: str = "updated") -> None:
        self.version += 1
        self.store.save()
        self.bus.publish("job", {"op": op, "job": job.to_dict(self._position(job))})
        if job.series_key:
            self._dirty.add(job.series_key)

    def _finish(self, job: Job, status: str, result: dict | None = None, error: dict | None = None, reason: str | None = None) -> None:
        job.status, job.phase, job.reason = status, None, reason
        job.finished_at = now_iso() if status in TERMINAL or status == "interrupted" else None
        if result is not None:
            job.result = result
        job.error = error
        if job.series_key:  # the library is up to date before the interface hears about the end
            for key in self.library.refresh_keys([job.series_key]):
                self.bus.publish("library", {"op": "upserted", "series_key": key, "version": self.library.version})
        self._changed(job)
        if status in TERMINAL or status == "interrupted":
            level = {"done": "info", "cancelled": "info", "interrupted": "warn"}.get(status, "error")
            self._log(job, self._summary(job), level, error["code"] if error else None)

    def _summary(self, job: Job) -> str:
        if job.status == "done" and job.kind == "fetch":
            r = job.result or {}
            failed = r.get("failed") or {}
            text = f"Terminé : {len(r.get('done', [])) + len(r.get('skipped', []))} épisode(s) présents"
            return text + (f", {len(failed)} échec(s) ({', '.join(failed)})." if failed else ".")
        if job.status == "done":
            return f"Film prêt : {(job.result or {}).get('file')}"
        if job.status == "interrupted":
            return "En attente du réseau : reprise automatique au retour de la connexion." if job.reason == "offline" else "Interrompu."
        if job.status == "cancelled":
            return "Annulé."
        return (job.error or {}).get("message") or job.status

    def _log(self, job: Job, message: str, level: str = "info", code: str | None = None) -> None:
        message = clean_text(message) or ""
        with self._lock:
            job.log.append(f"{_clock()} {message}")
            del job.log[:-LOG_LINES]
        self.bus.publish("log", {"job_id": job.id, "level": level, "code": code, "message": message, "at": now_iso()})

    def _delete_parts(self, job: Job) -> None:
        if not job.series_key:
            return
        folder = self.root / job.series_key
        for part in folder.glob("E*.part"):
            try:
                part.unlink()
            except OSError:
                pass
        self._dirty.add(job.series_key)

    # scheduling

    def _schedule_loop(self) -> None:
        with self._cond:
            while not self._closing:
                self._start_ready()
                self._cond.wait(1.0)

    def _start_ready(self) -> None:
        running = self._running()
        lanes = {"fetch": self.settings["concurrent_series"], "film": 1}
        for job_id in list(self.store.order):
            job = self.store.jobs[job_id]
            if job.status != "queued" or job.id in self._threads:
                continue
            if sum(r.kind == job.kind for r in running) >= lanes[job.kind]:
                continue
            if any(self._conflict(job, r) for r in running):
                continue
            self._launch(job)
            running.append(job)

    @staticmethod
    def _conflict(a: Job, b: Job) -> bool:
        if a.series_key and b.series_key:
            return a.series_key == b.series_key
        return a.provider == b.provider and a.book_id == b.book_id and a.lang_key == b.lang_key

    def _launch(self, job: Job) -> None:
        job.stop = threading.Event()
        job.stop_reason, job.delete_parts = None, True
        job.status, job.reason, job.error, job.result = "running", None, None, None
        job.phase = "metadata" if job.kind == "fetch" else "merging"
        job.started_at, job.finished_at = now_iso(), None
        job.progress = FetchProgress() if job.kind == "fetch" else FilmProgress()
        job.fallbacks = {}
        thread = threading.Thread(target=self._run, args=(job,), name=f"sdg-{job.id}", daemon=True)
        self._threads[job.id] = thread
        self._changed(job)
        thread.start()

    def _run(self, job: Job) -> None:
        try:
            if job.kind == "fetch":
                self._run_fetch(job)
            else:
                self._run_film(job)
        except Exception as e:  # a bug: the job fails, the server keeps running
            log.exception("Tâche %s", job.id)
            with self._lock:
                self._finish(job, "failed", error={"code": "internal", "message": f"Erreur interne : {e}"})
        finally:
            with self._cond:
                self._threads.pop(job.id, None)
                if job.status in RUNNING:
                    self._finish(job, "failed", error={"code": "internal", "message": "La tâche s'est arrêtée sans résultat."})
                self._sent.pop(job.id, None)
                self._cond.notify_all()

    def _stopped(self, job: Job, result: dict | None = None) -> None:
        with self._lock:
            if job.stop_reason == "pause":
                self._finish(job, "paused", result, reason="user")
            elif job.stop_reason == "cancel":
                if job.delete_parts:
                    self._delete_parts(job)
                self._finish(job, "cancelled", result)
            else:
                self._finish(job, "interrupted", result, reason="shutdown")

    def _set_phase(self, job: Job, phase: str) -> None:
        with self._lock:
            if job.phase != phase and job.status in RUNNING:
                job.phase = phase
                self._changed(job)

    def _offline(self) -> bool:
        changed = self.connectivity.check()
        if changed:
            self.bus.publish("health", self.connectivity.snapshot())
        return self.connectivity.online is False

    # downloads

    def _run_fetch(self, job: Job) -> None:
        p = job.params
        opts = pipeline.FetchOptions(
            out_dir=self.root,
            lang=job.lang,
            quality=p.get("quality") or "best",
            jobs=self.settings["parallel_downloads"],
            episodes=[tuple(r) for r in p["episodes"]] if p.get("episodes") else None,
            ffmpeg_path=self.settings["ffmpeg_path"],
        )
        control = pipeline.FetchControl(
            stop=job.stop,
            limiter=self.limiter,
            force=frozenset(p.get("force") or ()),
            strict_quality=bool(p.get("strict_quality")),
            on_event=lambda name, data: self._on_fetch_event(job, name, data),
            manifest_listener=lambda manifest, n: self._on_manifest(job, manifest, n),
            record_request=p.get("record_request", True),
        )
        try:
            result = pipeline.fetch(self.http, job.book_ref(), opts, log=lambda m: self._log(job, m), control=control)
        except pipeline.Cancelled:
            self._stopped(job)
            return
        except errors.SeriesNotFound as e:
            with self._lock:
                self._finish(job, "failed", error={"code": "series_not_found", "message": str(e)})
            return
        except ManifestError as e:
            with self._lock:
                self._finish(job, "failed", error={"code": "internal", "message": str(e)})
            return
        except (HttpStatusError, *TRANSIENT_ERRORS) as e:
            code = errors.code_for(e)
            if code == errors.NETWORK and self._offline():
                with self._lock:
                    self._finish(job, "interrupted", reason="offline")
                return
            api_code = {errors.DISK_FULL: "disk_space", errors.FILE_LOCKED: "file_locked"}.get(code, "network")
            with self._lock:
                self._finish(job, "failed", error={"code": api_code, "message": clean_text(f"{e}")})
            return

        summary = {
            "done": result.done,
            "skipped": result.skipped,
            "failed": {str(n): {"code": result.failed_codes.get(n, errors.UNKNOWN), "message": clean_text(msg)}
                       for n, msg in sorted(result.failed.items())},
            "quality_fallback": dict(job.fallbacks),
            "cancelled": result.cancelled,
        }  # fmt: skip
        if job.stop.is_set() and job.stop_reason:
            self._stopped(job, summary)
            return
        if result.stop_reason == errors.DISK_FULL:
            with self._lock:
                self._finish(job, "failed", summary, {"code": "disk_space", "message": "Disque plein : libère de la place puis reprends."})
            return
        codes = set(result.failed_codes.values())
        if result.failed and codes <= {errors.NETWORK} and self._offline():
            with self._lock:
                self._finish(job, "interrupted", summary, reason="offline")
            return
        with self._lock:
            self._finish(job, "done", summary)
            if p.get("film_after") and not result.failed and job.series_key:
                self._chain_film(job)

    def _chain_film(self, job: Job) -> None:
        try:
            film_job = self.create_film(
                job.series_key, job.book_id, job.lang,
                {"reencode": False, "allow_missing": False, "chapters": True, "output_name": None, "replace": "auto"},
                title=job.title, cover_url=job.cover_url, parent=job.id, provider=job.provider,
            )  # fmt: skip
        except JobError as e:
            self._log(job, f"Film non lancé : {e}", "warn", e.code)
            return
        job.then = film_job.id
        self._changed(job)

    def _on_fetch_event(self, job: Job, name: str, data: dict) -> None:
        if job.progress is not None:
            job.progress.on_event(name, data)
        n = data.get("n")
        if name == "probe_started":
            self._set_phase(job, "probing")
        elif name == "series_loaded":
            with self._lock:
                job.series_key = data["series_key"]
                job.title = data.get("title") or job.title
                job.selected = list(data.get("selected") or [])
                job.cover_url = f"/media/series/{job.series_key}/cover"
                job.phase = "downloading"
                self._changed(job)
            job.progress.start(Path(data["series_dir"]), job.selected)
        elif name == "episode_resolving":
            self.bus.publish("episode", {"series_key": job.series_key, "job_id": job.id, "n": n, "status": "resolving",
                                         "quality": None, "bytes": None, "error_code": None})  # fmt: skip
        elif name == "quality_fallback":
            job.fallbacks[str(n)] = {"requested": data.get("requested"), "got": data.get("got")}
            self._log(job, f"Épisode {n} : {data.get('got')} au lieu de {data.get('requested')} (non disponible).", "warn", "quality_fallback")
        elif name == "lang_fallback":
            self._log(job, f"Langue « {data.get('requested')} » indisponible : version originale utilisée.", "warn", "lang_unavailable")
        elif name == "episode_failed":
            self._log(job, f"Épisode {n} : échec ({data.get('code')}).", "error", data.get("code"))
        elif name == "disk_full":
            self._log(job, "Disque plein : téléchargements arrêtés.", "error", "disk_space")
        elif name == "selection_clipped":
            self._log(job, f"Épisodes ignorés (la série en compte {data.get('episode_count')}) : {', '.join(data.get('ignored', []))}.", "warn", "selection_clipped")
        elif name == "fetch_finished":
            self._set_phase(job, "finishing")

    def _on_manifest(self, job: Job, manifest: Manifest, n: int | None) -> None:
        key = manifest.path.parent.name
        with self._lock:
            self._dirty.add(key)
        if n is None:
            return
        try:
            entry = dict(manifest.episode(n))
        except KeyError:
            return
        self.bus.publish("episode", {
            "series_key": key, "job_id": job.id, "n": n, "status": entry.get("status"),
            "quality": entry.get("quality"), "bytes": entry.get("bytes"), "error_code": entry.get("error_code"),
        })  # fmt: skip

    # films

    def _run_film(self, job: Job) -> None:
        p = job.params
        folder = self.root / (job.series_key or "")
        if not job.series_key or not folder.is_dir():
            with self._lock:
                self._finish(job, "failed", error={"code": "not_found", "message": "Dossier de la série introuvable."})
            return
        options = {
            "output": folder / p["output_name"] if p.get("output_name") else None,
            "reencode": bool(p.get("reencode")),
            "allow_missing": bool(p.get("allow_missing")),
            "chapters": p.get("chapters", True) is not False,
            "only": set(p["episodes"]) if p.get("episodes") else None,
            "stop": job.stop,
            "on_progress": job.progress.on_progress,
        }
        replace = p.get("replace")
        try:
            ffmpeg = self.find_ffmpeg(self.settings["ffmpeg_path"])
            say = lambda m: self._log(job, m)  # noqa: E731
            if p.get("montage"):  # edited episodes first, then the film (it replaces our plain one)

                def phase(name: str) -> None:
                    job.progress.started = time.monotonic()  # the time left is estimated per phase
                    self._set_phase(job, name)

                del options["reencode"]
                made = montage.make_montage_film(
                    folder, ffmpeg, log=say, recipe=p.get("montage_recipe"), on_phase=phase, **options
                )
            else:
                try:
                    made = film.make_film(folder, ffmpeg, log=say, replace=replace is True, **options)
                except film.FilmError as e:
                    if e.code != errors.FILM_EXISTS or replace != "auto":
                        raise
                    made = film.make_film(folder, ffmpeg, log=say, replace=True, **options)  # an outdated film is rebuilt
        except film.FilmError as e:
            if e.code == errors.CANCELLED or job.stop.is_set():
                self._stopped(job)
            else:
                with self._lock:
                    self._finish(job, "failed", error={"code": e.code, "message": str(e)})
            return
        finally:
            with self._lock:
                self._dirty.add(job.series_key)
        with self._lock:
            self._finish(job, "done", {
                "file": made.path.name, "duration_s": round(made.duration, 3), "bytes": made.size,
                "mode": made.mode, "chapters": made.chapters, "reused": made.reused,
            })  # fmt: skip

    # periodic work: progress events, library updates, network recheck

    def _tick_loop(self) -> None:
        while not self._closing:
            time.sleep(TICK)
            try:
                self._tick(time.monotonic())
            except Exception:
                log.exception("Tick")

    def _tick(self, now: float) -> None:
        with self._lock:
            running = [j for j in self._running() if j.progress is not None]
            dirty, self._dirty = self._dirty, set()
            waiting_network = any(j.status == "interrupted" and j.reason == "offline" for j in self.store.jobs.values())
        for job in running:
            snapshot = job.progress.snapshot(now)
            key = job.progress.key()
            if self._sent.get(job.id) != key:
                self._sent[job.id] = key
                self.bus.publish("progress", {"job_id": job.id, "kind": job.kind, **snapshot}, replay=False)
        if dirty:
            for key in self.library.refresh_keys(dirty):
                self.bus.publish("library", {"op": "upserted", "series_key": key, "version": self.library.version})
        if waiting_network and now - self._last_offline_check >= OFFLINE_RECHECK:
            self._last_offline_check = now
            if not self._offline():
                self.connectivity_changed()
        for hook in list(self.tick_hooks):
            hook()
