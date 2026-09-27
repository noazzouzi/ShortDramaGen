"""Deletion with undo: files go to ``<downloads>/.sdg/trash/<id>/`` for a few minutes.

On the same volume a move is a rename: deleting and restoring are instant,
even for a 700 MB film. Windows refuses to move a file that another program
has open (a video player): each move is retried a few times, then reported as
``file_locked`` with the file name.
"""

from __future__ import annotations

import json
import os
import re
import secrets
import shutil
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Callable

from .library import film_name_ok
from .manifest import FILENAME, Manifest

TRASH_DIR = Path(".sdg") / "trash"
SCOPES = ("all", "episodes", "film", "parts")
RETRIES = 5
RETRY_DELAY = 0.2
_ID_RE = re.compile(r"^t-[0-9a-f]{6}$")
_EPISODE_RE = re.compile(r"^E(\d{3,4})\.mp4$")


class TrashError(Exception):
    def __init__(self, status: int, code: str, message: str, details: dict | None = None):
        super().__init__(message)
        self.status = status
        self.code = code
        self.details = details or {}


def _move(src: Path, dst: Path) -> None:
    """os.replace with a few retries: Windows keeps a file locked while a player reads it."""
    for attempt in range(RETRIES):
        try:
            os.replace(src, dst)
            return
        except PermissionError:
            if attempt == RETRIES - 1:
                raise
            time.sleep(RETRY_DELAY)


def _unlink(path: Path) -> None:
    for attempt in range(RETRIES):
        try:
            path.unlink()
            return
        except FileNotFoundError:
            return
        except PermissionError:
            if attempt == RETRIES - 1:
                raise
            time.sleep(RETRY_DELAY)


def _size(path: Path) -> int:
    if path.is_file():
        return path.stat().st_size
    return sum(p.stat().st_size for p in path.rglob("*") if p.is_file())


def _now() -> datetime:
    return datetime.now(timezone.utc)


class Trash:
    def __init__(self, root: Path, minutes: Callable[[], int]):
        self.root = Path(root)
        self.minutes = minutes

    @property
    def dir(self) -> Path:
        return self.root / TRASH_DIR

    def delete(self, folder: Path, key: str, scope: str) -> dict:
        """Move part of a series to the trash. ``folder`` comes from the library index."""
        if scope not in SCOPES:
            raise TrashError(422, "invalid_input", f"Portée inconnue : {scope} (attendu : {', '.join(SCOPES)}).")
        if scope == "parts":
            return self._delete_parts(folder)
        trash_id = "t-" + secrets.token_hex(3)
        box = self.dir / trash_id
        box.mkdir(parents=True)
        expires = _now() + timedelta(minutes=self.minutes())
        meta = {"id": trash_id, "series_key": key, "scope": scope, "created_at": _now().isoformat(timespec="seconds"),
                "expires_at": expires.isoformat(timespec="seconds"), "files": [], "bytes": 0, "manifest": {}}  # fmt: skip
        failed: list[str] = []
        try:
            if scope == "all":
                meta["bytes"] = _size(folder)
                try:
                    _move(folder, box / key)
                except PermissionError:
                    raise TrashError(423, "file_locked", "Un fichier de ce dossier est ouvert dans un autre programme (lecteur vidéo ?). Ferme-le, puis réessaie.", {"file": key}) from None
                meta["files"] = [key]
            elif scope == "episodes":
                files = sorted(p for p in folder.iterdir() if _EPISODE_RE.match(p.name) and p.is_file())
                if not files:
                    raise TrashError(404, "not_found", "Aucun épisode à supprimer.")
                manifest = Manifest.load(folder)
                previous = {}
                for path in files:
                    size = path.stat().st_size
                    try:
                        _move(path, box / path.name)
                    except PermissionError:
                        failed.append(path.name)
                        continue
                    meta["files"].append(path.name)
                    meta["bytes"] += size
                    n = int(_EPISODE_RE.match(path.name).group(1))
                    if manifest:
                        try:
                            previous[str(n)] = manifest.episode(n).get("status")
                            manifest.update(n, status="removed")
                        except KeyError:
                            pass
                meta["manifest"] = {"previous": previous}
            else:  # film
                manifest = Manifest.load(folder)
                record = (manifest.data.get("film") if manifest else None) or {}
                name = record.get("file")
                if not isinstance(name, str) or not film_name_ok(name) or not (folder / name).is_file():
                    raise TrashError(404, "not_found", "Aucun film à supprimer dans ce dossier.")
                meta["bytes"] = (folder / name).stat().st_size
                try:
                    _move(folder / name, box / name)
                except PermissionError:
                    raise TrashError(423, "file_locked", f"Impossible de supprimer {name} : il est ouvert dans un autre programme. Ferme-le, puis réessaie.", {"file": name}) from None
                meta["files"] = [name]
                meta["manifest"] = {"film": record}
                manifest.set("film", None)
        except TrashError:
            if not meta["files"]:
                shutil.rmtree(box, ignore_errors=True)
            raise
        (box / "meta.json").write_text(json.dumps(meta, ensure_ascii=False, indent=1), encoding="utf-8")
        reply = {"trash_id": trash_id, "scope": scope, "freed_bytes": meta["bytes"], "restorable_until": meta["expires_at"]}
        if failed:
            raise TrashError(
                423, "file_locked",
                f"{len(meta['files'])} fichier(s) supprimé(s) sur {len(meta['files']) + len(failed)} : "
                f"{len(failed)} sont ouverts dans un autre programme.",
                {**reply, "files": failed},
            )  # fmt: skip
        return reply

    def _delete_parts(self, folder: Path) -> dict:
        freed, failed = 0, []
        for part in folder.glob("*.part"):
            size = part.stat().st_size
            try:
                _unlink(part)
                freed += size
            except PermissionError:
                failed.append(part.name)
        reply = {"trash_id": None, "scope": "parts", "freed_bytes": freed, "restorable_until": None}
        if failed:
            raise TrashError(423, "file_locked", "Des fichiers partiels sont encore utilisés.", {**reply, "files": failed})
        return reply

    def _meta(self, trash_id: str) -> tuple[Path, dict]:
        box = self.dir / trash_id
        if not _ID_RE.match(trash_id or "") or not (box / "meta.json").is_file():
            raise TrashError(404, "not_found", "Cette suppression ne peut plus être annulée.")
        return box, json.loads((box / "meta.json").read_text(encoding="utf-8"))

    def restore(self, trash_id: str) -> dict:
        box, meta = self._meta(trash_id)
        key, scope = meta["series_key"], meta["scope"]
        folder = self.root / key
        if scope == "all":
            if folder.exists():
                raise TrashError(409, "conflict", "Un dossier du même nom existe déjà : restauration impossible.")
            _move(box / key, folder)
        else:
            if not (folder / FILENAME).is_file():
                raise TrashError(409, "conflict", "Le dossier de la série a disparu : restauration impossible.")
            manifest = Manifest.load(folder)
            for name in meta["files"]:
                if not (folder / name).exists():
                    _move(box / name, folder / name)
            if scope == "episodes":
                for n, status in (meta["manifest"].get("previous") or {}).items():
                    try:
                        manifest.update(int(n), status=status or "done")
                    except KeyError:
                        pass
            elif scope == "film" and meta["manifest"].get("film"):
                manifest.set("film", meta["manifest"]["film"])
        shutil.rmtree(box, ignore_errors=True)
        return {"series_key": key, "scope": scope}

    def purge(self, everything: bool = False) -> int:
        """Empty what is past its undo delay (or everything, at shutdown)."""
        if not self.dir.is_dir():
            return 0
        removed = 0
        now = _now()
        for box in self.dir.iterdir():
            if not box.is_dir() or not _ID_RE.match(box.name):
                continue
            try:
                meta = json.loads((box / "meta.json").read_text(encoding="utf-8"))
                expired = datetime.fromisoformat(meta["expires_at"]) <= now
            except (OSError, ValueError, KeyError):
                expired = True
            if everything or expired:
                shutil.rmtree(box, ignore_errors=True)
                removed += 1
        return removed
