"""Routes of the JSON API and of the media files (read-only part, step 1).

The contract is docs/frontend/spec-v1.md §11. Paths of served files are
always rebuilt by the library index from a series key and an episode number.
"""

from __future__ import annotations

import os
import platform
import re
import shutil
import sys
from typing import TYPE_CHECKING, Callable

from .. import __version__
from ..film import safe_filename
from ..library import LibraryError
from . import media
from .replies import Reply, error_reply, json_reply

if TYPE_CHECKING:
    from .app import App, Request

API_VERSION = 1
_KEY = r"(?P<key>[^/]+)"

_LIBRARY_STATUS = {"not_found": 404, "outside_library": 403}


def _library_error(e: LibraryError) -> Reply:
    return error_reply(_LIBRARY_STATUS.get(e.code, 404), e.code, str(e))


def _file(path, content_type: str, req: "Request", **options):
    try:
        return media.prepare(path, content_type, req.headers, req.method == "HEAD", **options)
    except FileNotFoundError:  # deleted between the lookup and now
        return error_reply(404, "not_found", "Fichier introuvable.")


# --- API ------------------------------------------------------------------------------


def health(app: "App", req: "Request", key=None, n=None):
    root = app.library.root
    try:
        free = shutil.disk_usage(root).free
    except OSError:
        free = None
    return json_reply({
        "version": __version__,
        "api": API_VERSION,
        "platform": sys.platform,
        "python": platform.python_version(),
        "pid": os.getpid(),
        "started_at": app.started_at,
        "downloads_dir": str(root),
        "downloads_dir_ok": root.is_dir(),
        "free_bytes": free,
        "ffmpeg": app.ffmpeg_status(),
        "online": None,  # measured by the job runner (step 2)
        "read_only": True,  # downloads, films and deletions arrive with the jobs (step 2)
        "jobs": {"running": 0, "queued": 0},
        "library_version": app.library.version,
        "settings_version": app.settings.version,
    })  # fmt: skip


def library(app: "App", req: "Request", key=None, n=None):
    app.library.refresh()
    etag = f'"lib-{app.library.version}-{app.settings.version}"'
    if etag in [t.strip() for t in (req.headers.get("If-None-Match") or "").split(",")]:
        return Reply(304, b"", {"ETag": etag, "Cache-Control": "no-store"})
    data = app.library.library(app.settings["preferred_langs"], app.settings["title_lang"])
    return json_reply(data, headers={"ETag": etag})


def series(app: "App", req: "Request", key=None, n=None):
    app.library.refresh()
    try:
        return json_reply(app.library.series(key))
    except LibraryError as e:
        return _library_error(e)


def settings(app: "App", req: "Request", key=None, n=None):
    return json_reply(app.settings.as_dict())


# --- media ----------------------------------------------------------------------------


def media_episode(app: "App", req: "Request", key=None, n=None):
    try:
        path = app.library.episode_file(key, int(n))
        title = app.library.summary(key)["title"]
    except LibraryError as e:
        return _library_error(e)
    name = f"{safe_filename(title)} - Épisode {int(n)}.mp4" if req.query.get("download") == "1" else None
    return _file(path, "video/mp4", req, download_name=name)


def media_film(app: "App", req: "Request", key=None, n=None):
    try:
        path = app.library.film_file(key)
    except LibraryError as e:
        return _library_error(e)
    name = path.name if req.query.get("download") == "1" else None
    return _file(path, "video/mp4", req, download_name=name)


def media_chapters(app: "App", req: "Request", key=None, n=None):
    try:
        text = app.library.chapters_vtt(key)
    except LibraryError as e:
        return _library_error(e)
    return Reply(200, text.encode("utf-8"), {"Content-Type": "text/vtt; charset=utf-8", "Cache-Control": "no-cache"})


def media_cover(app: "App", req: "Request", key=None, n=None):
    try:
        path = app.library.cover_file(key)
    except LibraryError as e:
        return _library_error(e)
    return _file(path, "image/jpeg", req, cache="private, max-age=86400")


Handler = Callable[..., object]

ROUTES: list[tuple[re.Pattern, dict[str, Handler]]] = [
    (re.compile(r"^/api/health$"), {"GET": health}),
    (re.compile(r"^/api/library$"), {"GET": library}),
    (re.compile(rf"^/api/series/{_KEY}$"), {"GET": series}),
    (re.compile(r"^/api/settings$"), {"GET": settings}),
    (re.compile(rf"^/media/series/{_KEY}/episodes/(?P<n>\d{{1,4}})$"), {"GET": media_episode}),
    (re.compile(rf"^/media/series/{_KEY}/film$"), {"GET": media_film}),
    (re.compile(rf"^/media/series/{_KEY}/film/chapters\.vtt$"), {"GET": media_chapters}),
    (re.compile(rf"^/media/series/{_KEY}/cover$"), {"GET": media_cover}),
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
        return handler(app, req, **m.groupdict())
    return error_reply(404, "not_found", "Adresse inconnue.")
