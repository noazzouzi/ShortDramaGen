"""HTTP server of ``sdg ui``: standard library only, listening on 127.0.0.1.

``App`` holds the state (settings, library index, jobs, events, page token,
static files) and turns a request into a reply; ``Handler`` only reads and
writes HTTP.
"""

from __future__ import annotations

import hashlib
import logging
import mimetypes
import os
import re
import shutil
import socket
import sys
import threading
import time
from dataclasses import dataclass, field
from datetime import datetime, timezone
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from importlib import resources
from pathlib import Path
from urllib.parse import parse_qs, urlsplit

from .. import __version__
from ..connectivity import Connectivity
from ..events import EventBus
from ..http import Http
from ..jobs import JobRunner
from ..library import IgnoredStore, LibraryIndex
from ..settings import Settings, state_dir
from ..trash import Trash
from . import api, security
from .media import FileReply, copy_span
from .replies import Reply, StreamReply, error_reply

log = logging.getLogger("shortdramagen.server")

MAX_BODY = 64 * 1024
MAX_CONNECTIONS = 64

_TYPES = {
    ".html": "text/html; charset=utf-8",
    ".css": "text/css; charset=utf-8",
    ".js": "text/javascript; charset=utf-8",
    ".svg": "image/svg+xml",
    ".woff2": "font/woff2",
    ".json": "application/json",
    ".png": "image/png",
    ".ico": "image/x-icon",
    ".webmanifest": "application/manifest+json",
}
_STATIC_NAME_RE = re.compile(r"^[A-Za-z0-9_-][A-Za-z0-9._/-]*$")


@dataclass
class Request:
    method: str
    target: str
    headers: object  # http.client.HTTPMessage (case-insensitive get)
    body: bytes = b""
    path: str = ""
    query: dict = field(default_factory=dict)

    def __post_init__(self):
        split = urlsplit(self.target)
        self.path = split.path
        self.query = {k: v[-1] for k, v in parse_qs(split.query).items()}


def load_static() -> dict[str, tuple[bytes, str]]:
    """Every file of shortdramagen/web, read once: requests never touch the disk."""
    files: dict[str, tuple[bytes, str]] = {}
    root = resources.files("shortdramagen").joinpath("web")

    def walk(node, prefix: str) -> None:
        for child in node.iterdir():
            name = f"{prefix}{child.name}"
            if child.name.startswith("."):
                continue
            if child.is_dir():
                walk(child, f"{name}/")
            elif _STATIC_NAME_RE.match(name):
                suffix = Path(child.name).suffix.lower()
                kind = _TYPES.get(suffix) or mimetypes.guess_type(child.name)[0] or "application/octet-stream"
                files[name] = (child.read_bytes(), kind)

    if root.is_dir():
        walk(root, "")
    return files


class App:
    def __init__(
        self,
        settings: Settings,
        library: LibraryIndex,
        secret: str,
        http=None,
        connectivity: Connectivity | None = None,
        state: Path | None = None,
        **runner_options,
    ):
        self.settings = settings
        self.library = library
        self.token = security.page_token(secret)
        self.static = load_static()
        self.port = 0  # set once bound
        self.started_at = datetime.now(timezone.utc).isoformat(timespec="seconds")
        self.state = state or state_dir()
        self.http = http or Http()
        self.bus = EventBus()
        self.connectivity = connectivity or Connectivity()
        root = library.root
        self.runner = JobRunner(root, settings, self.bus, self.http, library, self.connectivity, **runner_options)
        self.trash = Trash(root, lambda: self.settings["trash_minutes"])
        self.ignored = IgnoredStore(root)
        library.job_overlay = self.runner.overlay
        library.ignored = self.ignored.get
        self.preview_cache: dict[tuple, tuple[float, dict]] = {}
        self.preview_covers: dict[tuple, str] = {}
        self.closing = False
        self.last_activity = time.monotonic()
        self.on_shutdown = None  # set by launch: stops the HTTP server
        self._ffmpeg: tuple[float, dict] | None = None
        self._ffmpeg_lock = threading.Lock()
        self._last_purge = 0.0
        self.runner.tick_hooks.append(self._purge_trash)

    def start(self) -> list[str]:
        """Start the job runner (resumes interrupted jobs) and measure the network once."""
        self.trash.purge()
        requeued = self.runner.start()
        threading.Thread(target=self._check_network, name="sdg-network", daemon=True).start()
        return requeued

    def close(self) -> None:
        self.closing = True
        self.bus.publish("server", {"op": "shutdown"})
        self.runner.close()
        self.trash.purge(everything=True)

    def _check_network(self) -> None:
        try:
            self.connectivity.check()
        except Exception:  # the check is informative only
            log.exception("Mesure de la connexion")
        self.bus.publish("health", self.connectivity.snapshot())

    def recheck(self) -> None:
        """Measure the network and look for ffmpeg again, now."""
        with self._ffmpeg_lock:
            self._ffmpeg = None
        if self.connectivity.check():
            self.runner.connectivity_changed()
        self.bus.publish("health", self.connectivity.snapshot())

    def _purge_trash(self) -> None:
        now = time.monotonic()
        if now - self._last_purge >= 30:
            self._last_purge = now
            self.trash.purge()

    def switch_root(self, root: Path) -> None:
        """New downloads folder (settings): library, queue, trash and ignored problems follow."""
        self.runner.set_root(root)
        self.library.set_root(root)
        self.trash.root = Path(root)
        self.ignored = IgnoredStore(root)
        self.library.ignored = self.ignored.get

    def health(self) -> dict:
        from .api import API_VERSION

        root = self.library.root
        try:
            free = shutil.disk_usage(root).free
        except OSError:
            free = None
        return {
            "version": __version__,
            "api": API_VERSION,
            "platform": sys.platform,
            "python": sys.version.split()[0],
            "pid": os.getpid(),
            "started_at": self.started_at,
            "downloads_dir": str(root),
            "downloads_dir_ok": root.is_dir(),
            "free_bytes": free,
            "ffmpeg": self.ffmpeg_status(),
            **self.connectivity.snapshot(),
            "read_only": False,
            "jobs": self.runner.counts(),
            "library_version": self.library.version,
            "settings_version": self.settings.version,
        }

    def snapshot(self) -> dict:
        """First SSE message: everything a client needs to be in sync."""
        return {
            "jobs": self.runner.list(),
            "library_version": self.library.version,
            "settings_version": self.settings.version,
            "health": self.health(),
        }

    def idle_seconds(self) -> float:
        if self.bus.client_count or self.runner.has_work():
            return 0.0
        return time.monotonic() - self.last_activity

    def ffmpeg_status(self, max_age: float = 30.0) -> dict:
        from .. import film

        with self._ffmpeg_lock:
            if self._ffmpeg is None or time.monotonic() - self._ffmpeg[0] > max_age:
                self._ffmpeg = (time.monotonic(), film.ffmpeg_info(self.settings["ffmpeg_path"]))
            return self._ffmpeg[1]

    # request -> reply

    def dispatch(self, req: Request) -> Reply | FileReply | StreamReply:
        if not security.host_ok(req.headers.get("Host"), self.port):
            return error_reply(421, "forbidden", "Hôte non autorisé.")
        if not security.fetch_site_ok(req.headers.get("Sec-Fetch-Site")):
            return error_reply(403, "forbidden", "Requête venue d'un autre site : refusée.")
        path = req.path
        mutation = req.method not in ("GET", "HEAD")
        if path.startswith("/api/"):
            # EventSource cannot send a header: the read-only event stream is protected by the
            # Host and Sec-Fetch-Site checks, and no other site can read it (no CORS header).
            if path != "/api/events" and not security.token_ok(req.headers.get(security.TOKEN_HEADER), self.token):
                return error_reply(403, "forbidden", "Jeton de page manquant ou invalide : recharge la page.")
            if mutation and not security.origin_ok(req.headers.get("Origin"), self.port):
                return error_reply(403, "forbidden", "Origine refusée.")
            if mutation and req.body and not security.json_type_ok(req.headers.get("Content-Type")):
                return error_reply(415, "invalid_input", "Corps attendu en JSON (Content-Type: application/json).")
        if path != "/api/events":
            self.last_activity = time.monotonic()
        if path.startswith(("/api/", "/media/")):
            return api.dispatch(self, req)
        return self.static_reply(req)

    def static_reply(self, req: Request) -> Reply:
        if req.method not in ("GET", "HEAD"):
            return error_reply(405, "not_found", "Méthode non autorisée.")
        name = "index.html" if req.path in ("/", "/index.html") else req.path.lstrip("/")
        entry = self.static.get(name)
        if entry is None:
            return error_reply(404, "not_found", "Page introuvable.")
        body, kind = entry
        headers = {"Content-Type": kind, "Cache-Control": "no-cache"}
        if name == "index.html":
            body = body.replace(b"{{SDG_TOKEN}}", self.token.encode()).replace(b"{{SDG_VERSION}}", __version__.encode())
            headers["Cache-Control"] = "no-store"
        else:
            etag = '"' + hashlib.sha256(body).hexdigest()[:20] + '"'
            headers["ETag"] = etag
            if etag in (req.headers.get("If-None-Match") or ""):
                return Reply(304, b"", headers)
        return Reply(200, body, headers)


# --- HTTP plumbing --------------------------------------------------------------------


class Handler(BaseHTTPRequestHandler):
    protocol_version = "HTTP/1.1"
    server_version = "ShortDramaGen"
    sys_version = ""
    timeout = 120  # idle keep-alive connections do not hold a thread forever

    def version_string(self) -> str:
        return self.server_version

    def do_GET(self):
        self._handle()

    do_HEAD = do_POST = do_PUT = do_PATCH = do_DELETE = do_OPTIONS = do_GET

    def _handle(self) -> None:
        app: App = self.server.app
        started = time.monotonic()
        body = b""
        if self.command not in ("GET", "HEAD"):
            body = self._read_body()
            if body is None:
                self._send(error_reply(413, "invalid_input", f"Corps trop gros (limite : {MAX_BODY // 1024} Kio)."))
                return
        try:
            reply = app.dispatch(Request(self.command, self.path, self.headers, body))
        except Exception:
            log.exception("Erreur sur %s %s", self.command, self.path)
            reply = error_reply(500, "internal", "Erreur interne du serveur (détails dans server.log).")
        try:
            self._send(reply)
        except (BrokenPipeError, ConnectionResetError, ConnectionAbortedError, TimeoutError):
            self.close_connection = True  # the player moved on (seek, new episode): normal
        except OSError as e:  # the file vanished or became unreadable while being sent
            log.warning("Envoi interrompu pour %s : %s", self.path, e)
            self.close_connection = True
        log.info("%s %s %s %.0f ms", self.command, self.path, reply.status, (time.monotonic() - started) * 1000)

    def _read_body(self) -> bytes | None:
        """The request body, or None if it is too large (the connection is then closed)."""
        try:
            length = int(self.headers.get("Content-Length") or 0)
        except ValueError:
            length = -1
        if 0 <= length <= MAX_BODY:
            return self.rfile.read(length) if length else b""
        self.close_connection = True
        return None

    def _send(self, reply: Reply | FileReply | StreamReply) -> None:
        head = self.command == "HEAD"
        self.send_response(reply.status)
        headers = {**security.COMMON_HEADERS, "Content-Security-Policy": security.CSP, **reply.headers}
        if isinstance(reply, Reply):
            headers.setdefault("Content-Length", str(len(reply.body)))
        if isinstance(reply, StreamReply):
            headers["Connection"] = "close"
            self.close_connection = True
        for name, value in headers.items():
            self.send_header(name, value)
        self.end_headers()
        if head or reply.status in (204, 304):
            return
        if isinstance(reply, StreamReply):
            def write(data: bytes) -> None:
                self.wfile.write(data)
                self.wfile.flush()

            reply.stream(write)
            return
        if isinstance(reply, FileReply):
            if reply.path is not None:
                copy_span(reply.path, reply.start, reply.length, self.wfile)
        else:
            self.wfile.write(reply.body)

    def log_message(self, format, *args):  # noqa: A002 (BaseHTTPRequestHandler's signature)
        log.debug("%s - %s", self.address_string(), format % args)


class Server(ThreadingHTTPServer):
    daemon_threads = True
    # On Windows SO_REUSEADDR would let another process bind the same port.
    allow_reuse_address = sys.platform != "win32"

    def __init__(self, address, app: App):
        self.app = app
        self._slots = threading.BoundedSemaphore(MAX_CONNECTIONS)
        super().__init__(address, Handler)
        app.port = self.server_address[1]

    def server_bind(self):
        if sys.platform == "win32" and hasattr(socket, "SO_EXCLUSIVEADDRUSE"):
            self.socket.setsockopt(socket.SOL_SOCKET, socket.SO_EXCLUSIVEADDRUSE, 1)
        super().server_bind()

    def process_request(self, request, client_address):
        if not self._slots.acquire(blocking=False):
            self.shutdown_request(request)  # too many connections at once
            return
        try:
            super().process_request(request, client_address)
        except BaseException:
            self._slots.release()
            raise

    def process_request_thread(self, request, client_address):
        try:
            super().process_request_thread(request, client_address)
        finally:
            self._slots.release()


def create_server(app: App, port: int = 0, host: str = "127.0.0.1") -> Server:
    if host not in ("127.0.0.1", "localhost"):
        raise ValueError("Le serveur n'écoute que sur 127.0.0.1.")
    return Server(("127.0.0.1", port), app)
