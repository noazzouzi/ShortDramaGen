"""HTTP server of ``sdg ui``: standard library only, listening on 127.0.0.1.

``App`` holds the state (settings, library index, page token, static files)
and turns a request into a reply; ``Handler`` only reads and writes HTTP.
"""

from __future__ import annotations

import hashlib
import logging
import mimetypes
import re
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
from ..library import LibraryIndex
from ..settings import Settings
from . import api, security
from .media import FileReply, copy_span
from .replies import Reply, error_reply

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
    def __init__(self, settings: Settings, library: LibraryIndex, secret: str):
        self.settings = settings
        self.library = library
        self.token = security.page_token(secret)
        self.static = load_static()
        self.port = 0  # set once bound
        self.started_at = datetime.now(timezone.utc).isoformat(timespec="seconds")
        self._ffmpeg: tuple[float, dict] | None = None
        self._ffmpeg_lock = threading.Lock()

    def ffmpeg_status(self, max_age: float = 30.0) -> dict:
        from .. import film

        with self._ffmpeg_lock:
            if self._ffmpeg is None or time.monotonic() - self._ffmpeg[0] > max_age:
                self._ffmpeg = (time.monotonic(), film.ffmpeg_info(self.settings["ffmpeg_path"]))
            return self._ffmpeg[1]

    # request -> reply

    def dispatch(self, req: Request) -> Reply | FileReply:
        if not security.host_ok(req.headers.get("Host"), self.port):
            return error_reply(421, "forbidden", "Hôte non autorisé.")
        if not security.fetch_site_ok(req.headers.get("Sec-Fetch-Site")):
            return error_reply(403, "forbidden", "Requête venue d'un autre site : refusée.")
        path = req.path
        if path.startswith("/api/"):
            if not security.token_ok(req.headers.get(security.TOKEN_HEADER), self.token):
                return error_reply(403, "forbidden", "Jeton de page manquant ou invalide : recharge la page.")
            if req.method not in ("GET", "HEAD") and not security.origin_ok(req.headers.get("Origin"), self.port):
                return error_reply(403, "forbidden", "Origine refusée.")
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
        if self.command not in ("GET", "HEAD"):
            self._drain_body()
        try:
            reply = app.dispatch(Request(self.command, self.path, self.headers))
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

    def _drain_body(self) -> None:
        try:
            length = int(self.headers.get("Content-Length") or 0)
        except ValueError:
            length = -1
        if 0 <= length <= MAX_BODY:
            self.rfile.read(length)
        else:
            self.close_connection = True

    def _send(self, reply: Reply | FileReply) -> None:
        head = self.command == "HEAD"
        self.send_response(reply.status)
        headers = {**security.COMMON_HEADERS, "Content-Security-Policy": security.CSP, **reply.headers}
        if isinstance(reply, Reply):
            headers.setdefault("Content-Length", str(len(reply.body)))
        for name, value in headers.items():
            self.send_header(name, value)
        self.end_headers()
        if head or reply.status in (204, 304):
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
