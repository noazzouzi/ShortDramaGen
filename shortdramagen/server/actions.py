"""Commands of the API (step 2): jobs, preview, repair, film, deletion, settings, events.

Every input is validated here (docs/frontend/brainstorm/4-recherche-architecture.md
§6.5): the server never contacts a URL given by the client (only the book id
is kept), never uses a path given by the client, and answers with stable
error codes.
"""

from __future__ import annotations

import json
import logging
import re
import shutil
import threading
import time
from pathlib import Path
from typing import TYPE_CHECKING

from .. import desktop, dramafren, errors, film, inputs, official, pipeline
from ..events import Event
from ..http import TRANSIENT_ERRORS, HttpStatusError
from ..library import IGNORABLE, LibraryError
from ..settings import LANG_RE, QUALITIES, validate
from .replies import ApiError, Reply, StreamReply, json_reply

if TYPE_CHECKING:
    from .app import App, Request

log = logging.getLogger("shortdramagen.server")

PREVIEW_TTL = 15 * 60
PING_INTERVAL = 15.0
MAX_EPISODE = 10_000
_CONTROL_RE = re.compile(r"[\x00-\x1f\x7f]")
_OUTPUT_NAME_RE = re.compile(r"^[^\\/:*?\"<>|\x00-\x1f]{1,150}$")
_FILM_STATUS = {
    errors.FFMPEG_MISSING: 422, errors.FILM_MISSING_EPISODES: 422, errors.FILM_MIXED_FORMATS: 422,
    errors.NO_EPISODES: 422, errors.AMBIGUOUS_VERSION: 422, errors.SERIES_DIR_NOT_FOUND: 404,
    errors.FILM_EXISTS: 409,
}  # fmt: skip


# --- validation --------------------------------------------------------------------------


def body(req: "Request") -> dict:
    if not req.body:
        return {}
    try:
        data = json.loads(req.body)
    except (ValueError, UnicodeDecodeError):
        raise ApiError(400, "invalid_input", "Corps JSON illisible.") from None
    if not isinstance(data, dict):
        raise ApiError(400, "invalid_input", "Objet JSON attendu.")
    return data


def flag(data: dict, name: str, default: bool = False) -> bool:
    value = data.get(name, default)
    if not isinstance(value, bool):
        raise ApiError(422, "invalid_input", f"« {name} » doit valoir true ou false.", {"field": name})
    return value


def text_input(data: dict) -> str:
    value = data.get("input")
    if not isinstance(value, str) or not value.strip() or len(value) > 2048 or _CONTROL_RE.search(value.strip()):
        raise ApiError(422, "invalid_input", "Colle le lien d'une série DramaBox ou son numéro (ex. 41000105199).", {"field": "input"})
    return value.strip()


def lang_value(value) -> str | None:
    if value in (None, "", "vo"):
        return None
    if not isinstance(value, str) or not LANG_RE.match(value):
        raise ApiError(422, "invalid_lang", "Code de langue invalide (ex. fr, es, en).", {"field": "lang"})
    return value


def quality_value(value, default: str = "best") -> str:
    value = default if value is None else value
    if value not in QUALITIES:
        raise ApiError(422, "invalid_input", f"Qualité attendue : {', '.join(QUALITIES)}.", {"field": "quality"})
    return value


def episode_numbers(value, field: str = "episodes") -> list[int] | None:
    """null, "1-10,28", or a list of numbers → sorted numbers (None = all)."""
    if value is None:
        return None
    if isinstance(value, str):
        try:
            ranges = inputs.parse_episodes(value)
        except inputs.InputError as e:
            raise ApiError(422, "invalid_episodes", str(e), {"field": field}) from None
        if ranges is None:
            return None
        if any(b is None for _, b in ranges) or sum(b - a + 1 for a, b in ranges) > MAX_EPISODE:
            raise ApiError(422, "invalid_episodes", "Plage ouverte ou trop grande : utilise une liste de numéros.", {"field": field})
        return sorted({n for a, b in ranges for n in range(a, b + 1)})
    if isinstance(value, list) and len(value) <= MAX_EPISODE and all(
        isinstance(n, int) and not isinstance(n, bool) and 1 <= n <= MAX_EPISODE for n in value
    ):
        return sorted(set(value)) or None
    raise ApiError(422, "invalid_episodes", "Épisodes attendus : null, \"1-10,28\" ou une liste de numéros.", {"field": field})


def episode_ranges(value) -> list[list] | None:
    """Like episode_numbers, but open ranges ("50-") are kept: [[1, 10], [50, None]]."""
    if isinstance(value, str):
        try:
            ranges = inputs.parse_episodes(value)
        except inputs.InputError as e:
            raise ApiError(422, "invalid_episodes", str(e), {"field": "episodes"}) from None
        if ranges is not None and len(ranges) > 100:
            raise ApiError(422, "invalid_episodes", "Trop de plages (100 au plus).", {"field": "episodes"})
        return [list(r) for r in ranges] if ranges else None
    return compress(episode_numbers(value))


def compress(numbers: list[int] | None) -> list[list] | None:
    if not numbers:
        return None
    out: list[list] = []
    for n in sorted(numbers):
        if out and n == out[-1][1] + 1:
            out[-1][1] = n
        else:
            out.append([n, n])
    return out


def output_name(value) -> str | None:
    if value in (None, ""):
        return None
    if not isinstance(value, str) or not _OUTPUT_NAME_RE.match(value) or value.strip(" .") != value or value in (".", ".."):
        raise ApiError(422, "invalid_input", "Nom de fichier invalide (sans / \\ : * ? \" < > |).", {"field": "output_name"})
    name = value if value.lower().endswith(".mp4") else f"{value}.mp4"
    if re.match(r"^E\d{3,4}\.mp4$", name):
        raise ApiError(422, "invalid_input", "Ce nom est réservé aux épisodes.", {"field": "output_name"})
    return name


def version_lang(summary: dict) -> str | None:
    """Language of a version as a job needs it: None for the original version."""
    return None if summary["is_original"] else summary["lang"] or None


def created(app: "App", job) -> Reply:
    return json_reply({"job": app.runner.describe(job)}, 201, {"Location": f"/api/jobs/{job.id}"})


# --- events -------------------------------------------------------------------------------


def events(app: "App", req: "Request"):
    raw = req.headers.get("Last-Event-ID") or req.query.get("last_id")
    last_id = int(raw) if raw and raw.isdigit() else None
    sub, missed = app.bus.subscribe(last_id)
    start_id = app.bus.last_id

    def stream(write) -> None:
        try:
            write(b"retry: 2000\n\n")
            if missed is None:
                write(Event(start_id, "snapshot", app.snapshot()).encode())
            else:
                for event in missed:
                    write(event.encode())
            while not app.closing:
                event = sub.get(PING_INTERVAL)
                if event is None:
                    if sub.closed:
                        return
                    write(b": ping\n\n")
                    continue
                write(event.encode())
        except OSError:  # the tab was closed
            pass
        finally:
            sub.close()

    headers = {"Content-Type": "text/event-stream; charset=utf-8", "Cache-Control": "no-store", "X-Accel-Buffering": "no"}
    return StreamReply(200, headers, stream)


# --- jobs ------------------------------------------------------------------------------------


def list_jobs(app: "App", req: "Request"):
    return json_reply(app.runner.list())


def get_job(app: "App", req: "Request", job_id: str):
    return json_reply({"job": app.runner.describe(app.runner.get(job_id), with_log=True)})


def remove_job(app: "App", req: "Request", job_id: str):
    app.runner.remove(job_id)
    return Reply(204)


def job_command(app: "App", req: "Request", job_id: str, command: str):
    data = body(req)
    if command == "pause":
        job = app.runner.pause(job_id)
    elif command == "resume":
        job = app.runner.resume(job_id)
    else:
        job = app.runner.cancel(job_id, delete_parts=flag(data, "delete_parts", True))
    return json_reply({"job": app.runner.describe(job)}, 202)


def create_job(app: "App", req: "Request"):
    data = body(req)
    kind = data.get("kind")
    if kind == "film":
        key = data.get("series_key")
        if not isinstance(key, str):
            raise ApiError(422, "invalid_input", "« series_key » attendu.", {"field": "series_key"})
        return film_job(app, key, data)
    if kind != "fetch":
        raise ApiError(422, "invalid_input", "« kind » attendu : fetch ou film.", {"field": "kind"})
    text = text_input(data)
    try:
        ref = inputs.parse_input(text)
    except inputs.InputError as e:
        raise ApiError(422, "invalid_input", str(e).split("\n")[0], {"field": "input"}) from None
    lang = lang_value(data.get("lang")) or ref.lang
    force = episode_numbers(data.get("force"), "force") or []
    params = {
        "input": text,
        "quality": quality_value(data.get("quality"), app.settings["default_quality"]),
        "episodes": episode_ranges(data.get("episodes")),
        "force": force,
        "strict_quality": flag(data, "strict_quality"),
        "film_after": flag(data, "film_after", app.settings["film_after_download"]),
        "record_request": True,
    }
    cached = app.preview_cache.get((ref.book_id, lang or "vo"))
    title = cached[1].get("title") if cached else None
    cover = cached[1].get("cover_url") if cached else None
    return created(app, app.runner.create_fetch(ref.book_id, lang, params, title=title, cover_url=cover))


# --- repairs ---------------------------------------------------------------------------------

REPAIRABLE = ("failed", "unavailable", "missing", "partial")
# Requested but never downloaded (a cancelled job leaves its queue this way): « Réparer » takes them too.
RETRYABLE = REPAIRABLE + ("pending",)


def _fetch_for_version(app: "App", key: str, numbers: list[int] | None, *, quality: str | None = None,
                       force: list[int] = (), strict: bool = False, film_after: bool = False,
                       complete: bool = False):  # fmt: skip
    app.library.refresh_keys([key])  # a file may have been deleted in the file manager just now
    detail = app.library.series(key)
    requested = detail.get("requested") or {}
    params = {
        "input": detail["book_id"],
        "quality": quality or requested.get("quality") or "best",
        "episodes": None if complete else compress(numbers),
        "force": sorted(force),
        "strict_quality": strict,
        "film_after": film_after,
        # a repair keeps what was first asked; "complete" asks for every episode from now on
        "record_request": complete,
    }
    return app.runner.create_fetch(detail["book_id"], version_lang(detail), params, series_key=key,
                                   title=detail["title"], cover_url=detail["cover_url"])  # fmt: skip


def retry(app: "App", req: "Request", key: str):
    """Réparer / Compléter: failed, unavailable, missing, interrupted and still pending episodes (+ the unrequested ones with include_pending)."""
    data = body(req)
    app.library.refresh_keys([key])
    detail = app.library.series(key)
    include_pending = flag(data, "include_pending")
    wanted = episode_numbers(data.get("episodes"))
    redownload = episode_numbers(data.get("redownload"), "redownload") or []
    statuses = RETRYABLE + (("not_requested",) if include_pending else ())
    if wanted is None:
        wanted = [e["n"] for e in detail["episodes"] if e["status"] in statuses]
    numbers = sorted(set(wanted) | set(redownload))
    if not numbers:
        raise ApiError(422, "nothing_to_do", "Rien à réessayer : tous les épisodes demandés sont présents.")
    quality = data.get("quality")
    job = _fetch_for_version(
        app, key, numbers,
        quality=quality_value(quality) if quality is not None else None,
        force=redownload,
        strict=bool(redownload) and quality not in (None, "best"),
        film_after=flag(data, "film_after"),
        complete=include_pending and data.get("episodes") is None and not redownload,
    )  # fmt: skip
    return created(app, job)


def redownload(app: "App", req: "Request", key: str):
    """Download these episodes again (the old file stays until the new one is verified)."""
    data = body(req)
    numbers = episode_numbers(data.get("episodes"))
    if not numbers:
        raise ApiError(422, "invalid_episodes", "Indique les épisodes à retélécharger.", {"field": "episodes"})
    quality = quality_value(data.get("quality"))
    job = _fetch_for_version(app, key, numbers, quality=quality, force=numbers, strict=quality != "best",
                             film_after=flag(data, "film_after"))  # fmt: skip
    return created(app, job)


def repair(app: "App", req: "Request"):
    """« Tout réparer »: only safe actions (retry failures, resume, re-download deleted files)."""
    data = body(req)
    keys = data.get("series_keys")
    if keys is not None and (not isinstance(keys, list) or not all(isinstance(k, str) for k in keys)):
        raise ApiError(422, "invalid_input", "« series_keys » : null ou liste de clés.", {"field": "series_keys"})
    dry_run = flag(data, "dry_run", True)
    app.library.refresh(force=True)  # deletions made outside the app count
    ignored = app.ignored.get()
    actions = []
    for key in keys if keys is not None else app.library.keys():
        detail = app.library.series(key)
        if detail.get("job"):
            continue
        skip = set(ignored.get(key, []))
        numbers = [
            e["n"] for e in detail["episodes"]
            if e["status"] in RETRYABLE and not ("failed" in skip and e["status"] in ("failed", "unavailable", "missing"))
            and not ("interrupted" in skip and e["status"] == "partial")
            and not ("incomplete" in skip and e["status"] == "pending")
        ]  # fmt: skip
        if not numbers:
            continue
        estimate = sum(int((e.get("duration_s") or 90) * 1000 * 124) for e in detail["episodes"] if e["n"] in numbers)
        actions.append({"series_key": key, "title": detail["title"], "retry": numbers, "bytes_estimate": estimate})
    total = sum(a["bytes_estimate"] for a in actions)
    if dry_run:
        return json_reply({"actions": actions, "bytes_estimate": total})
    jobs, refused = [], []
    for action in actions:
        try:
            jobs.append(app.runner.describe(_fetch_for_version(app, action["series_key"], action["retry"])))
        except Exception as e:  # a duplicate: already queued meanwhile
            refused.append({"series_key": action["series_key"], "code": getattr(e, "code", "internal"), "message": str(e)})
    return json_reply({"jobs": jobs, "refused": refused, "bytes_estimate": total}, 201)


# --- film ---------------------------------------------------------------------------------------


def _folder(app: "App", key: str) -> Path:
    app.library.summary(key)  # LibraryError if unknown
    return Path(app.library.series(key)["path"])


def film_plan(app: "App", req: "Request", key: str):
    folder = _folder(app, key)
    reencode = req.query.get("reencode") in ("1", "true")
    allow_missing = req.query.get("allow_missing") in ("1", "true")
    plan = film.plan_summary(folder, reencode, allow_missing, None, app.settings["ffmpeg_path"])
    busy = app.runner.busy(key)
    plan["busy_job_id"] = busy.id if busy else None
    return json_reply(plan)


def create_film(app: "App", req: "Request", key: str):
    return film_job(app, key, body(req))


def film_job(app: "App", key: str, data: dict):
    summary = app.library.summary(key)
    folder = _folder(app, key)
    busy = app.runner.busy(key)
    if busy and busy.kind == "fetch":
        raise ApiError(409, "series_busy", "Attends la fin du téléchargement de cette série : le film se crée ensuite.", {"job_id": busy.id})
    params = {
        "reencode": flag(data, "reencode"),
        "allow_missing": flag(data, "allow_missing"),
        "chapters": flag(data, "chapters", True),
        "output_name": output_name(data.get("output_name")),
        "replace": flag(data, "replace"),
    }
    try:  # the same checks as the job, at once: the interface shows the right fix immediately
        app.runner.find_ffmpeg(app.settings["ffmpeg_path"])
        plan = film.plan_film(folder, params["allow_missing"])
        film.ensure_joinable(plan, params["reencode"])
        output = folder / params["output_name"] if params["output_name"] else film.default_output(plan)
        if output.exists() and not params["replace"]:
            existing = film.up_to_date_film(plan, output)
            if existing:
                return json_reply({"reused": True, "film": {"file": output.name, "bytes": existing.size, "duration_s": existing.duration}})
            raise film.FilmError(f"Un fichier porte déjà ce nom : {output.name}. Coche « Remplacer » ou change le nom.", errors.FILM_EXISTS)
    except film.FilmError as e:
        raise ApiError(_FILM_STATUS.get(e.code, 422), e.code, str(e)) from None
    job = app.runner.create_film(key, summary["book_id"], version_lang(summary), params,
                                 title=summary["title"], cover_url=summary["cover_url"])  # fmt: skip
    return created(app, job)


# --- files: open, ignore, delete, restore -------------------------------------------------------


def open_target(app: "App", req: "Request", key: str):
    data = body(req)
    target = data.get("target", "folder")
    play = flag(data, "play")
    if target == "folder":
        path, select = _folder(app, key), False
    elif target == "film":
        path, select = app.library.film_file(key), True
    elif target == "episode":
        n = data.get("episode")
        if not isinstance(n, int) or isinstance(n, bool):
            raise ApiError(422, "invalid_input", "« episode » attendu (numéro).", {"field": "episode"})
        path, select = app.library.episode_file(key, n), True
    else:
        raise ApiError(422, "invalid_input", "« target » attendu : folder, film ou episode.", {"field": "target"})
    try:
        desktop.play(path) if play and select else desktop.reveal(path, select)
    except (OSError, ValueError) as e:
        raise ApiError(422, "open_failed", f"Impossible d'ouvrir : {e}") from None
    return Reply(204)


def ignore(app: "App", req: "Request", key: str):
    data = body(req)
    app.library.summary(key)
    problem = data.get("problem")
    if problem not in IGNORABLE:
        raise ApiError(422, "invalid_input", f"« problem » attendu : {', '.join(IGNORABLE)}.", {"field": "problem"})
    current = app.ignored.set(key, problem, flag(data, "ignored", True))
    app.bus.publish("library", {"op": "upserted", "series_key": key, "version": app.library.version})
    return json_reply({"series_key": key, "ignored": current})


def delete_series(app: "App", req: "Request", key: str):
    scope = req.query.get("scope")
    if not scope:
        raise ApiError(422, "invalid_input", "Précise ce qu'il faut supprimer : ?scope=all, episodes, film ou parts.", {"field": "scope"})
    folder = _folder(app, key)
    busy = app.runner.busy(key)
    if busy:
        raise ApiError(409, "series_busy", "Mets d'abord le téléchargement en pause.", {"job_id": busy.id})
    try:
        reply = app.trash.delete(folder, key, scope)
    finally:
        changed = app.library.refresh(force=True)
    op = "deleted" if scope == "all" else "upserted"
    if changed or scope == "all":
        app.bus.publish("library", {"op": op, "series_key": key, "version": app.library.version})
    return json_reply(reply)


def restore(app: "App", req: "Request", trash_id: str):
    result = app.trash.restore(trash_id)
    app.library.refresh(force=True)
    app.bus.publish("library", {"op": "upserted", "series_key": result["series_key"], "version": app.library.version})
    return json_reply(result)


def open_library(app: "App", req: "Request"):
    """The downloads folder itself in the file manager."""
    root = app.library.root
    if not root.is_dir():
        raise ApiError(404, "not_found", "Le dossier de la bibliothèque est introuvable.")
    try:
        desktop.reveal(root)
    except OSError as e:
        raise ApiError(422, "open_failed", f"Impossible d'ouvrir : {e}") from None
    return Reply(204)


def rescan(app: "App", req: "Request"):
    changed = app.library.refresh(force=True)
    if changed:
        app.bus.publish("library", {"op": "rescan", "series_key": None, "version": app.library.version})
    return json_reply({"version": app.library.version, "changed": changed})


# --- preview -----------------------------------------------------------------------------------


def preview(app: "App", req: "Request"):
    """What a link points at, before downloading: official metadata + one source check, never a probe."""
    data = body(req)
    text = text_input(data)
    try:
        ref = inputs.parse_input(text)
    except inputs.InputError as e:
        raise ApiError(422, "invalid_input", str(e).split("\n")[0], {"field": "input"}) from None
    requested = lang_value(data.get("lang"))
    lang = requested or ref.lang
    key = (ref.book_id, lang or "vo")
    cached = app.preview_cache.get(key)
    if cached and time.monotonic() - cached[0] < PREVIEW_TTL:
        result = dict(cached[1])
    else:
        result = _fetch_preview(app, ref, lang, "request" if requested else "url" if ref.lang else "default")
        app.preview_cache[key] = (time.monotonic(), result)
    result["episode_ref"] = ref.episode
    return json_reply(_with_local_state(app, result))


def _fetch_preview(app: "App", ref, lang: str | None, lang_source: str) -> dict:
    seen = []
    control = pipeline.FetchControl(limiter=app.runner.limiter, on_event=lambda name, d: seen.append((name, d)))
    warnings = []
    try:
        found = pipeline.preview_series(app.http, ref, lang, control)
    except official.SeriesNotFound:
        return _probe_preview(app, ref)
    except (HttpStatusError, *TRANSIENT_ERRORS):
        raise ApiError(502, "network", "Impossible de joindre DramaBox. Vérifie ta connexion.") from None
    result = found.to_dict()
    for name, d in seen:
        if name == "lang_fallback":
            lang_source = "fallback"
            warnings.append({"code": "lang_unavailable", "requested": d["requested"], "used": d["used"],
                             "message": f"Langue « {d['requested']} » indisponible pour cette série : version originale utilisée."})  # fmt: skip
    slug = "vo" if result["is_original"] else result["lang"]
    if found.series.cover and found.series.cover.startswith("https://"):
        app.preview_covers[(ref.book_id, slug)] = found.series.cover
        result["cover_url"] = f"/media/preview/{ref.book_id}/{slug}/cover"
    else:
        result["cover_url"] = None
    result.update(lang_source=lang_source, warnings=warnings)
    return result


def _probe_preview(app: "App", ref) -> dict:
    """A series missing from the official site: usable if the source knows episode 1."""
    try:
        sources = dramafren.get_video(app.http, ref.book_id, 1)
    except dramafren.ResolveError:
        raise ApiError(404, "series_not_found", "On n'a trouvé cette série ni sur le site officiel ni à la source. "
                       "Vérifie le lien ou essaie avec le n° de série (11 chiffres).") from None  # fmt: skip
    except (HttpStatusError, *TRANSIENT_ERRORS):
        raise ApiError(502, "network", "Impossible de joindre DramaBox. Vérifie ta connexion.") from None
    return {
        "book_id": ref.book_id, "source_book_id": ref.book_id, "lang": None, "is_original": True, "lang_source": "default",
        "title": f"Série {ref.book_id}", "title_vo": None, "introduction": None, "cover_url": None,
        "from_official": False, "episode_count": None, "duration_s": None, "episode_duration_s": None,
        "free_episodes": [], "languages": [],
        "availability": {"source": "ok", "checked_episode": 1, "qualities": [s.quality for s in sources], "error": None, "error_code": None},
        "estimate": {},
        "warnings": [{"code": "probe_mode", "message": "Série absente du site officiel : les épisodes seront détectés "
                      "pendant le téléchargement, sans contrôle de durée."}],
    }  # fmt: skip


def _with_local_state(app: "App", result: dict) -> dict:
    """What is already on disk or in the queue for this series (computed at each call)."""
    app.library.refresh()
    local = []
    for group in app.library.library()["groups"]:
        if group["book_id"] != result["book_id"]:
            continue
        for v in group["versions"]:
            local.append({
                "series_key": v["series_key"], "lang": v["lang"], "is_original": v["is_original"], "state": v["state"],
                "done": v["counts"]["done"] + v["counts"]["done_unverified"], "total": v["counts"]["total"],
                "film": (v["film"] or {}).get("state"),
            })  # fmt: skip
    try:
        free = shutil.disk_usage(app.library.root).free
    except OSError:
        free = None
    need = max((e.get("bytes") or 0 for e in (result.get("estimate") or {}).values()), default=0)
    job = app.runner.open_job_for(result["book_id"], None if result["is_original"] else result["lang"])
    return {**result, "local": local, "queued_job_id": job.id if job else None,
            "disk": {"free_bytes": free, "enough": free is None or free > need * 1.1}}  # fmt: skip


def preview_cover(app: "App", book_id: str, lang: str) -> Path:
    url = app.preview_covers.get((book_id, lang))
    if not url:
        raise LibraryError("Aperçu inconnu : relance l'aperçu de cette série.")
    path = app.state / "cache" / "covers" / f"{book_id}-{lang}.jpg"
    if not path.is_file():
        path.parent.mkdir(parents=True, exist_ok=True)
        try:
            official.download_cover(app.http, url, path)
        except (HttpStatusError, ValueError, *TRANSIENT_ERRORS):
            raise ApiError(502, "network", "Affiche indisponible pour le moment.") from None
    return path


# --- settings and life cycle --------------------------------------------------------------------


def patch_settings(app: "App", req: "Request"):
    data = body(req)
    clean = validate(data, create_dirs=True)
    new_root = clean.get("downloads_dir")
    if new_root and Path(new_root) != app.library.root.resolve():
        if app.runner.has_work() or app.runner.counts()["paused"]:
            raise ApiError(409, "series_busy", "Tu pourras changer de dossier quand les téléchargements seront finis.")
        changed = app.settings.update(clean)
        app.switch_root(Path(new_root))
        app.bus.publish("library", {"op": "rescan", "series_key": None, "version": app.library.version})
    else:
        clean.pop("downloads_dir", None)
        changed = app.settings.update(clean)
    if changed:
        app.bus.publish("settings", {"settings": app.settings.as_dict(), "version": app.settings.version})
    return json_reply(app.settings.as_dict())


def shutdown(app: "App", req: "Request"):
    """Stop the server: running downloads become "interrupted" and resume at the next launch."""
    if app.on_shutdown is None:
        raise ApiError(409, "invalid_state", "Arrêt impossible depuis l'interface dans ce mode.")
    threading.Thread(target=app.on_shutdown, name="sdg-shutdown", daemon=True).start()
    return json_reply({"ok": True}, 202)
