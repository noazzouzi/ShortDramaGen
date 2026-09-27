"""Routes of the JSON API and of the media files.

The contract is docs/frontend/spec-v1.md §11. Paths of served files are
always rebuilt by the library index from a series key and an episode number.
Commands (jobs, deletion, settings…) live in ``actions.py``.
"""

from __future__ import annotations

import logging
import re
from typing import TYPE_CHECKING, Callable

from ..film import safe_filename
from ..jobs import JobError
from ..library import LibraryError
from ..settings import SettingsError
from ..trash import TrashError
from . import actions, media
from .replies import ApiError, Reply, error_reply, json_reply

if TYPE_CHECKING:
    from .app import App, Request

log = logging.getLogger("shortdramagen.server")

API_VERSION = 1
_KEY = r"(?P<key>[^/]+)"
_LIBRARY_STATUS = {"not_found": 404, "outside_library": 403}


def _file(path, content_type: str, req: "Request", **options):
    try:
        return media.prepare(path, content_type, req.headers, req.method == "HEAD", **options)
    except FileNotFoundError:  # deleted between the lookup and now
        return error_reply(404, "not_found", "Fichier introuvable.")


def library_etag(app: "App") -> str:
    return f'"lib-{app.library.version}-{app.settings.version}-{app.runner.version}-{app.ignored.version}"'


# --- reading ---------------------------------------------------------------------------


def health(app: "App", req: "Request"):
    if req.query.get("check") == "1":  # « Tout revérifier » : réseau et ffmpeg mesurés maintenant
        app.recheck()
    return json_reply(app.health())


def library(app: "App", req: "Request"):
    app.library.refresh()
    etag = library_etag(app)
    if etag in [t.strip() for t in (req.headers.get("If-None-Match") or "").split(",")]:
        return Reply(304, b"", {"ETag": etag, "Cache-Control": "no-store"})
    data = app.library.library(app.settings["preferred_langs"], app.settings["title_lang"])
    return json_reply(data, headers={"ETag": etag})


def series(app: "App", req: "Request", key: str):
    app.library.refresh()
    return json_reply(app.library.series(key))


def settings(app: "App", req: "Request"):
    return json_reply(app.settings.as_dict())


# --- media ------------------------------------------------------------------------------


def media_episode(app: "App", req: "Request", key: str, n: str):
    path = app.library.episode_file(key, int(n))
    title = app.library.summary(key)["title"]
    name = f"{safe_filename(title)} - Épisode {int(n)}.mp4" if req.query.get("download") == "1" else None
    return _file(path, "video/mp4", req, download_name=name)


def media_film(app: "App", req: "Request", key: str):
    path = app.library.film_file(key)
    name = path.name if req.query.get("download") == "1" else None
    return _file(path, "video/mp4", req, download_name=name)


def media_chapters(app: "App", req: "Request", key: str):
    text = app.library.chapters_vtt(key)
    return Reply(200, text.encode("utf-8"), {"Content-Type": "text/vtt; charset=utf-8", "Cache-Control": "no-cache"})


def media_cover(app: "App", req: "Request", key: str):
    return _file(app.library.cover_file(key), "image/jpeg", req, cache="private, max-age=86400")


def media_preview_cover(app: "App", req: "Request", book_id: str, lang: str):
    return _file(actions.preview_cover(app, book_id, lang), "image/jpeg", req, cache="private, max-age=86400")


# --- routing -----------------------------------------------------------------------------

Handler = Callable[..., object]

ROUTES: list[tuple[re.Pattern, dict[str, Handler]]] = [
    (re.compile(r"^/api/health$"), {"GET": health}),
    (re.compile(r"^/api/events$"), {"GET": actions.events}),
    (re.compile(r"^/api/library$"), {"GET": library}),
    (re.compile(r"^/api/library/rescan$"), {"POST": actions.rescan}),
    (re.compile(r"^/api/library/open$"), {"POST": actions.open_library}),
    (re.compile(rf"^/api/series/{_KEY}$"), {"GET": series, "DELETE": actions.delete_series}),
    (re.compile(rf"^/api/series/{_KEY}/retry$"), {"POST": actions.retry}),
    (re.compile(rf"^/api/series/{_KEY}/redownload$"), {"POST": actions.redownload}),
    (re.compile(rf"^/api/series/{_KEY}/film/plan$"), {"GET": actions.film_plan}),
    (re.compile(rf"^/api/series/{_KEY}/film$"), {"POST": actions.create_film}),
    (re.compile(rf"^/api/series/{_KEY}/open$"), {"POST": actions.open_target}),
    (re.compile(rf"^/api/series/{_KEY}/ignore$"), {"POST": actions.ignore}),
    (re.compile(r"^/api/trash/(?P<trash_id>[^/]+)/restore$"), {"POST": actions.restore}),
    (re.compile(r"^/api/jobs$"), {"GET": actions.list_jobs, "POST": actions.create_job}),
    (re.compile(r"^/api/jobs/(?P<job_id>[^/]+)$"), {"GET": actions.get_job, "DELETE": actions.remove_job}),
    (re.compile(r"^/api/jobs/(?P<job_id>[^/]+)/(?P<command>pause|resume|cancel)$"), {"POST": actions.job_command}),
    (re.compile(r"^/api/repair$"), {"POST": actions.repair}),
    (re.compile(r"^/api/preview$"), {"POST": actions.preview}),
    (re.compile(r"^/api/settings$"), {"GET": settings, "PATCH": actions.patch_settings}),
    (re.compile(r"^/api/shutdown$"), {"POST": actions.shutdown}),
    (re.compile(rf"^/media/series/{_KEY}/episodes/(?P<n>\d{{1,4}})$"), {"GET": media_episode}),
    (re.compile(rf"^/media/series/{_KEY}/film$"), {"GET": media_film}),
    (re.compile(rf"^/media/series/{_KEY}/film/chapters\.vtt$"), {"GET": media_chapters}),
    (re.compile(rf"^/media/series/{_KEY}/cover$"), {"GET": media_cover}),
    (re.compile(r"^/media/preview/(?P<book_id>\d{6,20})/(?P<lang>[a-z]{2,3}|vo)/cover$"), {"GET": media_preview_cover}),
]


def dispatch(app: "App", req: "Request"):
    for pattern, methods in ROUTES:
        m = pattern.match(req.path)
        if not m:
            continue
        method = "GET" if req.method == "HEAD" else req.method
        handler = methods.get(method)
        if handler is None:
            reply = error_reply(405, "not_found", "Méthode non autorisée pour cette adresse.")
            reply.headers["Allow"] = ", ".join(sorted({*methods, "HEAD"} if "GET" in methods else methods))
            return reply
        try:
            return handler(app, req, **m.groupdict())
        except ApiError as e:
            return error_reply(e.status, e.code, str(e), e.details)
        except (JobError, TrashError) as e:
            return error_reply(e.status, e.code, str(e), e.details)
        except LibraryError as e:
            return error_reply(_LIBRARY_STATUS.get(e.code, 404), e.code, str(e))
        except SettingsError as e:
            return error_reply(422, "invalid_input", str(e), {"field": e.field})
    return error_reply(404, "not_found", "Adresse inconnue.")
