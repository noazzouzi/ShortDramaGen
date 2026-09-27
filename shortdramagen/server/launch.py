"""``sdg ui``: start the local server (or reuse the running one) and open the interface."""

from __future__ import annotations

import http.client
import json
import logging
import os
import shutil
import signal
import subprocess
import sys
import threading
import time
import webbrowser
from datetime import datetime, timezone
from logging.handlers import RotatingFileHandler
from pathlib import Path
from typing import Callable

from .. import __version__
from ..library import LibraryIndex
from ..settings import (
    Settings,
    SettingsError,
    clear_server_info,
    load_secret,
    read_server_info,
    state_dir,
    write_server_info,
)
from . import security
from .api import API_VERSION
from .app import App, Server, create_server

DEFAULT_PORT = 8765
PORTS = range(DEFAULT_PORT, 8776)


def running_instance(state: Path) -> dict | None:
    """The server described by server.json, if it answers as ShortDramaGen."""
    info = read_server_info(state)
    port = info.get("port")
    if not isinstance(port, int):
        return None
    token = security.page_token(load_secret(state))
    try:
        conn = http.client.HTTPConnection("127.0.0.1", port, timeout=2)
        conn.request("GET", "/api/health", headers={"Host": f"127.0.0.1:{port}", security.TOKEN_HEADER: token})
        resp = conn.getresponse()
        data = json.loads(resp.read()) if resp.status == 200 else None
        conn.close()
    except (OSError, ValueError, http.client.HTTPException):
        return None
    if not isinstance(data, dict) or data.get("api") != API_VERSION:
        return None
    return {**info, **data}


def bind(app: App, port: int | None) -> Server:
    ports = [port] if port else list(PORTS)
    error: OSError | None = None
    for candidate in ports:
        try:
            return create_server(app, candidate)
        except OSError as e:
            error = e
    span = str(ports[0]) if len(ports) == 1 else f"{ports[0]} à {ports[-1]}"
    raise OSError(f"port {span} déjà utilisé ({error})")


def app_browser() -> str | None:
    """Edge (present on every Windows 10/11) or Chrome, for a window without address bar."""
    if sys.platform == "win32":
        for var in ("PROGRAMFILES(X86)", "PROGRAMFILES", "LOCALAPPDATA"):
            base = os.environ.get(var)
            if not base:
                continue
            for rel in ("Microsoft/Edge/Application/msedge.exe", "Google/Chrome/Application/chrome.exe"):
                candidate = Path(base) / rel
                if candidate.is_file():
                    return str(candidate)
    for name in ("msedge", "microsoft-edge", "google-chrome", "chromium", "chromium-browser", "chrome"):
        found = shutil.which(name)
        if found:
            return found
    return None


def open_interface(url: str, window: bool) -> None:
    if window:
        exe = app_browser()
        if exe:
            try:
                subprocess.Popen(
                    [exe, f"--app={url}", "--window-size=1440,900"],
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL,
                )
                return
            except OSError:
                pass
    webbrowser.open(url)


def setup_logging(state: Path) -> None:
    logger = logging.getLogger("shortdramagen.server")
    if any(isinstance(h, RotatingFileHandler) for h in logger.handlers):
        return
    state.mkdir(parents=True, exist_ok=True)
    handler = RotatingFileHandler(state / "server.log", maxBytes=1_000_000, backupCount=2, encoding="utf-8")
    handler.setFormatter(logging.Formatter("%(asctime)s %(levelname)s %(message)s"))
    logger.addHandler(handler)
    logger.setLevel(logging.INFO)


def _stop_on_sigterm() -> None:
    """A terminated server (kill, service stop) cleans up like Ctrl+C: server.json is removed."""

    def handler(signum, frame):
        raise KeyboardInterrupt

    try:
        signal.signal(signal.SIGTERM, handler)
    except (ValueError, OSError):  # not the main thread
        pass


def run_ui(
    out: Path | None = None,
    port: int | None = None,
    open_browser: bool = True,
    window: bool = False,
    log: Callable[[str], None] = print,
) -> int:
    state = state_dir()
    existing = running_instance(state)
    if existing:
        url = f"http://127.0.0.1:{existing['port']}/"
        log(f"ShortDramaGen est déjà lancé : {url}")
        if out and Path(existing.get("downloads_dir") or "") != out.expanduser().resolve():
            log(
                f"Attention : -o ignoré, l'interface ouverte utilise {existing.get('downloads_dir')}. "
                "Arrête-la d'abord (Ctrl+C dans sa fenêtre) pour changer de dossier."
            )
        if open_browser:
            open_interface(url, window)
        return 0

    settings = Settings(state)
    try:
        if out:
            settings.update({"downloads_dir": str(out.expanduser().resolve())})
        elif not settings["downloads_dir"]:
            settings.update({"downloads_dir": str(Path("downloads").resolve())})  # same default as sdg fetch
    except SettingsError as e:
        log(f"Dossier des téléchargements refusé : {e}")
        return 2
    library = LibraryIndex(settings.downloads_dir())
    library.refresh(force=True)
    app = App(settings, library, load_secret(state), state=state)
    try:
        server = bind(app, port)
    except OSError as e:
        log(f"Impossible de démarrer le serveur : {e}")
        return 1
    url = f"http://127.0.0.1:{app.port}/"
    setup_logging(state)
    requeued = app.start()
    app.on_shutdown = server.shutdown
    write_server_info(
        {
            "pid": os.getpid(),
            "port": app.port,
            "url": url,
            "version": __version__,
            "started_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        },
        state,
    )
    log(f"ShortDramaGen {__version__} : {url}")
    log(f"Bibliothèque : {settings.downloads_dir()} ({len(library.keys())} dossier(s) de série)")
    if requeued:
        log(f"Reprise de {len(requeued)} téléchargement(s) interrompu(s).")
    log("Laisse cette fenêtre ouverte pendant que tu utilises l'interface ; Ctrl+C pour arrêter.")
    if open_browser:
        open_interface(url, window)
    _stop_on_sigterm()
    threading.Thread(target=_auto_shutdown, args=(app, server, log), name="sdg-idle", daemon=True).start()
    try:
        server.serve_forever(poll_interval=0.5)
    except KeyboardInterrupt:
        pass
    finally:
        log("Arrêt : les téléchargements en cours reprendront au prochain lancement.")
        app.close()
        server.server_close()
        clear_server_info(os.getpid(), state)
    return 0


def _auto_shutdown(app: App, server: Server, log: Callable[[str], None], interval: float = 30.0) -> None:
    """Stop after N minutes with no open tab and nothing to download (settings: auto_shutdown_minutes)."""
    while not app.closing:
        time.sleep(interval)
        minutes = app.settings["auto_shutdown_minutes"]
        if minutes and app.idle_seconds() >= minutes * 60:
            log(f"Aucun onglet ouvert ni téléchargement depuis {minutes} min : arrêt automatique.")
            server.shutdown()
            return
