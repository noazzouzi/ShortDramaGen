"""Local state of the interface: settings, secret, running server.

Everything lives in one folder per user, outside the downloads (the settings
say where the downloads are):
- Windows: %LOCALAPPDATA%\\ShortDramaGen
- elsewhere: $XDG_CONFIG_HOME/shortdramagen (~/.config/shortdramagen)
- SDG_HOME overrides both (tests, portable use).
"""

from __future__ import annotations

import json
import os
import re
import secrets
import sys
import threading
from pathlib import Path

from . import fsutil

SETTINGS_FILE = "settings.json"
SECRET_FILE = "secret"
SERVER_FILE = "server.json"

QUALITIES = ("best", "1080p", "720p", "540p")
LANG_RE = re.compile(r"^[a-z]{2,3}(-[a-z0-9]{2,8})?$")

DEFAULTS: dict = {
    "downloads_dir": None,  # absolute path, chosen at the first launch
    "default_quality": "best",
    "preferred_langs": [],
    "title_lang": "preferred",  # show the title in the preferred language when a version has it
    "parallel_downloads": 3,
    "concurrent_series": 1,
    "film_after_download": False,
    "resume_on_start": True,
    "ffmpeg_path": None,
    "theme": "dark",
    "nav_shortcuts": True,
    "action_shortcuts": False,
    "sr_announcements": "milestones",
    "notifications": True,
    "auto_shutdown_minutes": 10,
    "trash_minutes": 5,
}


class SettingsError(ValueError):
    """An invalid value; ``field`` names the setting."""

    def __init__(self, field: str, message: str):
        super().__init__(message)
        self.field = field


def state_dir() -> Path:
    if os.environ.get("SDG_HOME"):
        return Path(os.environ["SDG_HOME"])
    if sys.platform == "win32" and os.environ.get("LOCALAPPDATA"):
        return Path(os.environ["LOCALAPPDATA"]) / "ShortDramaGen"
    base = os.environ.get("XDG_CONFIG_HOME") or Path.home() / ".config"
    return Path(base) / "shortdramagen"


def _write_json(path: Path, data: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fsutil.write_text(path, json.dumps(data, ensure_ascii=False, indent=2))


def _read_json(path: Path) -> dict:
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}
    return data if isinstance(data, dict) else {}


# --- validation -----------------------------------------------------------------


def _bool(field: str, value) -> bool:
    if not isinstance(value, bool):
        raise SettingsError(field, "Valeur attendue : vrai ou faux.")
    return value


def _choice(field: str, value, choices: tuple) -> str:
    if value not in choices:
        raise SettingsError(field, f"Valeur attendue : {', '.join(choices)}.")
    return value


def _int(field: str, value, low: int, high: int) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or not low <= value <= high:
        raise SettingsError(field, f"Nombre entier attendu, de {low} à {high}.")
    return value


def _forbidden_roots() -> list[Path]:
    roots = []
    for var in ("WINDIR", "SYSTEMROOT", "PROGRAMFILES", "PROGRAMFILES(X86)", "PROGRAMDATA"):
        if os.environ.get(var):
            roots.append(Path(os.environ[var]).resolve())
    if sys.platform != "win32":
        roots += [Path(p) for p in ("/bin", "/boot", "/dev", "/etc", "/lib", "/proc", "/sbin", "/sys", "/usr")]
    return roots


def validate_downloads_dir(value, create: bool = True) -> str:
    """An absolute, writable folder that is neither a drive root nor a system folder."""
    field = "downloads_dir"
    if not isinstance(value, str) or not value.strip() or "\0" in value:
        raise SettingsError(field, "Chemin de dossier attendu.")
    path = Path(value.strip()).expanduser()
    if not path.is_absolute():
        raise SettingsError(field, "Indique un chemin complet (ex. C:\\Users\\toi\\Videos\\ShortDramaGen).")
    path = path.resolve()
    if path == Path(path.anchor):
        raise SettingsError(field, "Choisis un dossier, pas la racine d'un disque.")
    for root in _forbidden_roots():
        if path == root or root in path.parents:
            raise SettingsError(field, f"Dossier système refusé : {root}.")
    if path.exists() and not path.is_dir():
        raise SettingsError(field, "Ce chemin désigne un fichier, pas un dossier.")
    if create:
        try:
            path.mkdir(parents=True, exist_ok=True)
            probe = path / f".sdg-write-test-{secrets.token_hex(4)}"
            probe.write_bytes(b"")
            probe.unlink()
        except OSError as e:
            raise SettingsError(field, f"Dossier inaccessible en écriture : {e}.") from None
    return str(path)


def validate_ffmpeg_path(value) -> str | None:
    if value is None:
        return None
    if not isinstance(value, str) or not value.strip():
        raise SettingsError("ffmpeg_path", "Chemin de ffmpeg attendu.")
    path = Path(value.strip())
    if path.name.lower() not in ("ffmpeg", "ffmpeg.exe") or not path.is_file():
        raise SettingsError("ffmpeg_path", "Indique le fichier ffmpeg (ffmpeg.exe sous Windows).")
    return str(path)


def validate(patch: dict, create_dirs: bool = True) -> dict:
    """The patch with checked values. Unknown keys and invalid values raise SettingsError."""
    if not isinstance(patch, dict):
        raise SettingsError("", "Objet JSON attendu.")
    clean = {}
    for field, value in patch.items():
        if field not in DEFAULTS:
            raise SettingsError(field, f"Réglage inconnu : {field}.")
        if field == "downloads_dir":
            clean[field] = validate_downloads_dir(value, create_dirs)
        elif field == "ffmpeg_path":
            clean[field] = validate_ffmpeg_path(value)
        elif field == "default_quality":
            clean[field] = _choice(field, value, QUALITIES)
        elif field == "title_lang":
            clean[field] = _choice(field, value, ("preferred", "original"))
        elif field == "theme":
            clean[field] = _choice(field, value, ("dark", "light", "system"))
        elif field == "sr_announcements":
            clean[field] = _choice(field, value, ("milestones", "all", "off"))
        elif field == "preferred_langs":
            if not isinstance(value, list) or len(value) > 10 or not all(
                isinstance(v, str) and LANG_RE.match(v) for v in value
            ):
                raise SettingsError(field, "Liste de codes de langue attendue (ex. [\"fr\", \"es\"]).")
            clean[field] = list(dict.fromkeys(value))
        elif field == "parallel_downloads":
            clean[field] = _int(field, value, 1, 6)
        elif field == "concurrent_series":
            clean[field] = _int(field, value, 1, 2)
        elif field == "auto_shutdown_minutes":
            clean[field] = _int(field, value, 0, 1440)  # 0 = never
        elif field == "trash_minutes":
            clean[field] = _int(field, value, 1, 1440)
        else:
            clean[field] = _bool(field, value)
    return clean


# --- store ------------------------------------------------------------------------


class Settings:
    """settings.json, with defaults for what is missing and a version bumped on each change."""

    def __init__(self, directory: Path | None = None):
        self.dir = directory or state_dir()
        self.path = self.dir / SETTINGS_FILE
        self._lock = threading.Lock()
        stored = _read_json(self.path)
        version = stored.pop("version", 0)
        self.version = version if isinstance(version, int) and not isinstance(version, bool) else 0
        self.values = dict(DEFAULTS)
        for field, value in stored.items():  # keep what is still valid, drop the rest
            try:
                self.values.update(validate({field: value}, create_dirs=False))
            except SettingsError:
                pass

    def __getitem__(self, field: str):
        return self.values[field]

    def as_dict(self) -> dict:
        with self._lock:
            return {**self.values, "version": self.version}

    def update(self, patch: dict, create_dirs: bool = True) -> dict:
        clean = validate(patch, create_dirs)
        with self._lock:
            changed = {k: v for k, v in clean.items() if self.values.get(k) != v}
            if changed:
                self.values.update(changed)
                self.version += 1
                _write_json(self.path, {**self.values, "version": self.version})
        return changed

    def downloads_dir(self) -> Path:
        return Path(self.values["downloads_dir"]) if self.values["downloads_dir"] else Path("downloads").resolve()


def load_secret(directory: Path | None = None) -> str:
    """Random secret kept across launches (the page token is derived from it)."""
    path = (directory or state_dir()) / SECRET_FILE
    try:
        value = path.read_text(encoding="ascii").strip()
        if len(value) >= 32:
            return value
    except (OSError, UnicodeDecodeError):
        pass
    value = secrets.token_urlsafe(32)
    path.parent.mkdir(parents=True, exist_ok=True)
    fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
    with os.fdopen(fd, "w", encoding="ascii") as f:
        f.write(value)
    return value


def read_server_info(directory: Path | None = None) -> dict:
    return _read_json((directory or state_dir()) / SERVER_FILE)


def write_server_info(info: dict, directory: Path | None = None) -> None:
    _write_json((directory or state_dir()) / SERVER_FILE, info)


def clear_server_info(pid: int, directory: Path | None = None) -> None:
    """Remove server.json if it still describes this process."""
    path = (directory or state_dir()) / SERVER_FILE
    if _read_json(path).get("pid") == pid:
        path.unlink(missing_ok=True)
