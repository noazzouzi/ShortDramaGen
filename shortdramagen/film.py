"""Join the downloaded episodes of a series into a single film, with chapters.

Episodes of one quality share the exact same codec parameters (checked with
mp4.probe), so ffmpeg can join them without re-encoding: a 62-episode series
takes seconds. Mixed formats (e.g. one 720p fallback in a 1080p series) need
``reencode=True``, which normalises everything with libx264/AAC.
"""

from __future__ import annotations

import re
import shutil
import struct
import subprocess
import tempfile
import threading
from collections import Counter
from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable

from . import errors, fsutil, mp4
from .manifest import FILENAME as MANIFEST_FILENAME
from .manifest import Manifest, now_iso, read_json
from .models import BookRef

Progress = Callable[[float, float], None]  # (seconds done, total seconds)
Log = Callable[[str], None]

_FORBIDDEN_CHARS_RE = re.compile(r'[<>:"/\\|?*\x00-\x1f]')
_EPISODE_FILE_RE = re.compile(r"^E(\d{3,})\.mp4$")


class FilmError(Exception):
    """A film that cannot be made. ``code`` is one of the film codes of errors.py."""

    def __init__(self, message: str, code: str = errors.FILM_FAILED):
        super().__init__(message)
        self.code = code


@dataclass
class Part:
    number: int
    path: Path
    info: mp4.Mp4Info


@dataclass
class FilmPlan:
    series_dir: Path
    title: str
    episode_count: int
    parts: list[Part]
    missing: list[int] = field(default_factory=list)

    @property
    def groups(self) -> dict[tuple, list[Part]]:
        groups: dict[tuple, list[Part]] = {}
        for part in self.parts:
            groups.setdefault(part.info.format_key, []).append(part)
        return groups

    @property
    def compatible(self) -> bool:
        return len(self.groups) == 1

    @property
    def duration(self) -> float:
        return sum(p.info.duration for p in self.parts)

    def segment(self, part: Part, reencode: bool) -> float:
        """Length an episode takes in the film.

        Copy: the whole file (mvhd), because the AAC priming packets that the
        edit list hides are copied too; giving that length to the concat
        demuxer keeps them from overlapping the previous episode.
        Re-encode: ffmpeg decodes with edit lists applied, so the presented length.
        """
        return part.info.presentation if reencode else part.info.duration

    def length(self, reencode: bool) -> float:
        return sum(self.segment(p, reencode) for p in self.parts)

    def main_format(self) -> mp4.Mp4Info:
        """Format covering the longest total duration (target of a re-encode)."""
        totals = Counter()
        for part in self.parts:
            totals[part.info.format_key] += part.info.duration
        key = totals.most_common(1)[0][0]
        return next(p.info for p in self.parts if p.info.format_key == key)


@dataclass
class FilmResult:
    path: Path
    duration: float
    size: int
    mode: str  # "copy" or "reencode"
    chapters: int = 0
    reused: bool = False  # the existing film was already up to date: nothing was rebuilt


# --- locating the downloads -----------------------------------------------------


def find_series_dir(out_dir: Path, ref: BookRef, lang: str | None = None) -> Path:
    """Folder created by ``sdg fetch`` for this series (no network needed)."""
    candidates = []
    for d in sorted(out_dir.glob(f"{ref.book_id}-*")):
        manifest = d / MANIFEST_FILENAME
        if d.is_dir() and manifest.exists():
            candidates.append((d, read_json(manifest)))
    if not candidates:
        raise FilmError(
            f"Aucun téléchargement trouvé pour {ref.book_id} dans {out_dir}. "
            f"Lance d'abord : sdg fetch {ref.book_id}",
            errors.SERIES_DIR_NOT_FOUND,
        )
    lang = lang or ref.lang
    if lang:
        matching = [d for d, m in candidates if m.get("lang") == lang]
    else:  # original version: videos come from the requested book itself
        matching = [d for d, m in candidates if m.get("source_book_id") == ref.book_id]
    if len(matching) == 1:
        return matching[0]
    if len(candidates) == 1 and not lang:
        return candidates[0][0]
    names = ", ".join(f"{d.name} (langue {m.get('lang')})" for d, m in candidates)
    raise FilmError(
        f"Précise la langue avec --lang ou donne le dossier directement. Trouvés : {names}", errors.AMBIGUOUS_VERSION
    )


# --- planning -------------------------------------------------------------------


def plan_film(series_dir: Path, allow_missing: bool = False, only: set[int] | None = None) -> FilmPlan:
    """What would go into the film. ``only`` restricts it to some episode numbers."""
    if not series_dir.is_dir():
        raise FilmError(f"Dossier introuvable : {series_dir}", errors.SERIES_DIR_NOT_FOUND)
    manifest_path = series_dir / MANIFEST_FILENAME
    if manifest_path.exists():
        data = read_json(manifest_path)
        title = data.get("title") or series_dir.name
        numbers = [e["number"] for e in data.get("episodes", [])]
    else:  # a folder of E001.mp4 files without manifest
        title = series_dir.name
        numbers = sorted(int(m.group(1)) for p in series_dir.iterdir() if (m := _EPISODE_FILE_RE.match(p.name)))
    if not numbers:
        raise FilmError(f"Aucun épisode dans {series_dir}", errors.NO_EPISODES)
    total = len(numbers)
    if only is not None:
        numbers = [n for n in numbers if n in only]

    parts, missing = [], []
    for number in sorted(numbers):
        path = series_dir / f"E{number:03d}.mp4"
        try:
            info = mp4.probe(path) if path.exists() else None
        except (OSError, IndexError, ValueError, struct.error):  # truncated or corrupt file
            info = None
        if info is None or info.video is None:
            missing.append(number)
        else:
            parts.append(Part(number, path, info))

    if missing and not allow_missing:
        raise FilmError(
            f"Épisodes absents ou illisibles : {format_ranges(missing)}. Relance « sdg fetch » pour les "
            "récupérer, ou utilise --allow-missing pour fusionner sans eux.",
            errors.FILM_MISSING_EPISODES,
        )
    if not parts:
        raise FilmError(f"Aucun épisode lisible dans {series_dir}", errors.NO_EPISODES)
    return FilmPlan(series_dir, title, total, parts, missing)


def describe_groups(plan: FilmPlan) -> str:
    return "; ".join(
        f"{parts[0].info.describe()} : épisodes {format_ranges([p.number for p in parts])}"
        for parts in plan.groups.values()
    )


# --- building -------------------------------------------------------------------


def ensure_joinable(plan: FilmPlan, reencode: bool) -> None:
    if not plan.compatible and not reencode:
        raise FilmError(
            "Les épisodes n'ont pas tous le même format, la fusion sans ré-encodage est "
            f"impossible ({describe_groups(plan)}). Retélécharge les épisodes à part dans la même "
            "qualité, ou ajoute --reencode (plus lent).",
            errors.FILM_MIXED_FORMATS,
        )


def default_output(plan: FilmPlan) -> Path:
    """<title>.mp4, or <title> (épisodes 1-10).mp4 for a partial film."""
    name = safe_filename(plan.title)
    numbers = [p.number for p in plan.parts]
    if len(numbers) < plan.episode_count:
        name += f" (épisodes {format_ranges(numbers)})"
    return plan.series_dir / f"{name}.mp4"


def make_film(
    series_dir: Path,
    ffmpeg: str,
    log: Log = print,
    output: Path | None = None,
    reencode: bool = False,
    allow_missing: bool = False,
    chapters: bool = True,
    only: set[int] | None = None,
    replace: bool = False,
    stop: threading.Event | None = None,
    on_progress: Progress | None = None,
) -> FilmResult:
    """Plan, check and build the film of a downloaded series.

    An existing film is never overwritten silently: if it is already up to date
    (same episodes, none modified since) it is reused, otherwise FilmError
    film_exists is raised unless ``replace`` is set.
    """
    plan = plan_film(series_dir, allow_missing, only)
    ensure_joinable(plan, reencode)
    if plan.missing:
        log(f"Attention : épisodes absents, film incomplet (manquent : {format_ranges(plan.missing)})")
    output = output or default_output(plan)
    if output.exists() and not replace:
        existing = up_to_date_film(plan, output)
        if existing:
            log(f"Film déjà à jour : {output} ({format_duration(existing.duration)}, {existing.size / 1e6:.0f} Mo)")
            return existing
        manifest = Manifest.load(plan.series_dir)
        record = (manifest.data.get("film") if manifest else None) or {}
        why = (
            "Le film existant n'est plus à jour (épisodes modifiés ou différents)"
            if record.get("file") in (output.name, str(output))
            else "Un fichier porte déjà ce nom"
        )
        raise FilmError(
            f"{why} : {output}. Ajoute --replace pour le remplacer, ou choisis un autre nom avec -f.",
            errors.FILM_EXISTS,
        )
    how = "avec ré-encodage, c'est long" if reencode else "sans ré-encodage"
    log(f"Fusion de {len(plan.parts)} épisodes ({format_duration(plan.length(reencode))}, {how}) -> {output}")
    result = build_film(plan, output, ffmpeg, reencode, chapters, on_progress, stop)
    log(f"Film créé : {result.path} ({format_duration(result.duration)}, {result.size / 1e6:.0f} Mo)")
    return result


def up_to_date_film(plan: FilmPlan, output: Path) -> FilmResult | None:
    """The existing film, if the manifest says it holds exactly these episodes, unchanged since."""
    manifest = Manifest.load(plan.series_dir)
    record = (manifest.data.get("film") if manifest else None) or {}
    name = output.name if output.parent == plan.series_dir else str(output)
    if record.get("file") != name or record.get("episodes") != [p.number for p in plan.parts]:
        return None
    stat = output.stat()
    if record.get("bytes") != stat.st_size or any(p.path.stat().st_mtime > stat.st_mtime for p in plan.parts):
        return None
    return FilmResult(
        output, record.get("duration_s") or 0.0, stat.st_size, record.get("mode", "copy"),
        record.get("chapters", 0), reused=True,
    )  # fmt: skip


def plan_summary(
    series_dir: Path,
    reencode: bool = False,
    allow_missing: bool = False,
    only: set[int] | None = None,
    ffmpeg: str | None = None,
    output: Path | None = None,
) -> dict:
    """Pre-flight report of a film, as data: what blocks it and how to fix it. Never raises for
    a film problem (missing episodes, mixed formats…): that is what the report describes."""
    try:
        plan = plan_film(series_dir, allow_missing=True, only=only)
    except FilmError as e:
        return {"can_build": False, "error": {"code": e.code, "message": str(e)}, "checks": {}, "fixes": []}
    main = plan.main_format()
    main_quality = quality_label(main)
    minority = sorted(p.number for p in plan.parts if p.info.format_key != main.format_key)
    groups = [
        {
            "format": parts[0].info.describe(),
            "quality": quality_label(parts[0].info),
            "episodes": format_ranges([p.number for p in parts]),
            "count": len(parts),
        }
        for parts in plan.groups.values()
    ]
    out = output or default_output(plan)
    needed = sum(p.path.stat().st_size for p in plan.parts)
    free = shutil.disk_usage(series_dir).free
    tool = ffmpeg_info(ffmpeg)
    checks = {
        "episodes": {"ok": not plan.missing, "missing": plan.missing, "present": len(plan.parts)},
        "format": {"ok": plan.compatible, "groups": groups},
        "ffmpeg": {"ok": tool["found"], **tool},
        "disk": {"ok": free > needed, "needed_bytes": needed, "free_bytes": free},
        "output": {"name": out.name, "exists": out.exists()},
        "chapters": len(plan.parts),
    }
    can_build = (
        (checks["episodes"]["ok"] or allow_missing)
        and (checks["format"]["ok"] or reencode)
        and checks["ffmpeg"]["ok"]
        and checks["disk"]["ok"]
    )
    fixes = []
    if plan.missing or minority:
        fixes.append({
            "action": "repair_then_film", "download": plan.missing, "redownload": minority,
            "quality": main_quality, "label": "Réparer puis créer le film",
        })  # fmt: skip
    if plan.missing:
        fixes.append({"action": "allow_missing", "output_name": out.name, "label": "Créer un film partiel"})
    if minority:
        fixes.append({
            "action": "reencode", "enabled": not plan.missing,
            "reason": "Des épisodes manquent aussi" if plan.missing else None,
            "label": "Créer quand même (ré-encodage, plusieurs minutes)",
        })  # fmt: skip
    return {
        "can_build": can_build,
        "checks": checks,
        "fixes": fixes,
        "duration_s": round(plan.length(reencode), 3),
        "estimated_bytes": needed,
    }


def quality_label(info: mp4.Mp4Info) -> str:
    """"1080p" for a 1080x1920 video (the short side, as the source names its qualities)."""
    return f"{min(info.video.width, info.video.height)}p" if info.video else "?"


def build_film(
    plan: FilmPlan,
    output: Path,
    ffmpeg: str,
    reencode: bool = False,
    chapters: bool = True,
    on_progress: Progress | None = None,
    stop: threading.Event | None = None,
) -> FilmResult:
    ensure_joinable(plan, reencode)
    mode = "reencode" if reencode else "copy"
    output.parent.mkdir(parents=True, exist_ok=True)
    tmp_output = output.with_name(output.name + ".part")

    with tempfile.TemporaryDirectory(prefix="sdg-film-") as tmp:
        tmp_dir = Path(tmp)
        metadata = tmp_dir / "chapters.txt"
        metadata.write_text(ffmetadata(plan, chapters, reencode), encoding="utf-8")
        if reencode:
            args = reencode_args(ffmpeg, plan, metadata, reencode_filter(plan), tmp_output, tmp_dir)
        else:
            concat_list = tmp_dir / "episodes.txt"
            concat_list.write_text(concat_list_text(plan), encoding="utf-8")
            args = copy_args(ffmpeg, concat_list, metadata, tmp_output)
        expected = plan.length(reencode)
        try:
            _run_ffmpeg(args, expected, tmp_dir / "ffmpeg.log", on_progress, stop)
        except BaseException:  # failure or Ctrl+C: no half-written film left behind
            tmp_output.unlink(missing_ok=True)
            raise

    duration = mp4.duration_seconds(tmp_output) if tmp_output.exists() else None
    tolerance = 1.0 + 0.05 * len(plan.parts)
    if duration is None or abs(duration - expected) > tolerance:
        tmp_output.unlink(missing_ok=True)
        raise FilmError(
            f"Film incorrect : durée {duration or 0:.1f} s au lieu de {expected:.1f} s attendues", errors.FILM_DURATION
        )
    fsutil.replace(tmp_output, output)
    result = FilmResult(output, duration, output.stat().st_size, mode, len(plan.parts) if chapters else 0)
    _record_in_manifest(plan, result, chapter_marks(plan, reencode) if chapters else [])
    return result


def copy_args(ffmpeg: str, concat_list: Path, metadata: Path, output: Path) -> list[str]:
    return [
        ffmpeg, "-hide_banner", "-nostdin", "-y", "-loglevel", "error", "-progress", "pipe:1", "-nostats",
        "-f", "concat", "-safe", "0", "-i", str(concat_list),
        "-i", str(metadata),
        "-map", "0:v:0", "-map", "0:a:0?", "-map_metadata", "1", "-map_chapters", "1",
        "-c", "copy", "-movflags", "+faststart", "-f", "mp4", str(output),
    ]  # fmt: skip


# Windows refuses command lines longer than 32 767 characters.
MAX_COMMAND_LINE = 30_000


def reencode_args(
    ffmpeg: str, plan: FilmPlan, metadata: Path, filter_graph: str, output: Path, tmp_dir: Path
) -> list[str]:
    args = [ffmpeg, "-hide_banner", "-nostdin", "-y", "-loglevel", "error", "-progress", "pipe:1", "-nostats"]
    for part in plan.parts:
        args += ["-i", str(part.path)]
    meta_index = len(plan.parts)
    args += ["-i", str(metadata)]
    inline = filter_graph.replace("\n", "")
    if sum(len(a) + 3 for a in args) + len(inline) < MAX_COMMAND_LINE:
        args += ["-filter_complex", inline]
    else:  # very long series: the graph goes in a file (option deprecated since ffmpeg 7, still accepted)
        script = tmp_dir / "filter.txt"
        script.write_text(filter_graph, encoding="utf-8")
        args += ["-filter_complex_script", str(script)]
    args += ["-map", "[v]", "-map", "[a]", "-map_metadata", str(meta_index), "-map_chapters", str(meta_index)]
    args += ["-c:v", "libx264", "-preset", "veryfast", "-crf", "20", "-pix_fmt", "yuv420p"]
    args += ["-c:a", "aac", "-b:a", "128k", "-movflags", "+faststart", "-f", "mp4", str(output)]
    return args


def reencode_filter(plan: FilmPlan) -> str:
    target = plan.main_format()
    w, h = target.video.width, target.video.height
    rate = target.audio.sample_rate if target.audio else 44100
    lines, inputs = [], []
    for i, part in enumerate(plan.parts):
        lines.append(
            f"[{i}:v:0]scale={w}:{h}:force_original_aspect_ratio=decrease,"
            f"pad={w}:{h}:-1:-1,setsar=1,format=yuv420p[v{i}];"
        )
        if part.info.audio:
            lines.append(f"[{i}:a:0]aformat=sample_rates={rate}:channel_layouts=stereo[a{i}];")
        else:  # silent episode: generate silence of the same length
            lines.append(
                f"anullsrc=r={rate}:cl=stereo,atrim=duration={part.info.duration:.3f}[a{i}];"
            )
        inputs.append(f"[v{i}][a{i}]")
    lines.append(f"{''.join(inputs)}concat=n={len(plan.parts)}:v=1:a=1[v][a]")
    return "\n".join(lines) + "\n"


def concat_list_text(plan: FilmPlan) -> str:
    """ffmpeg concat demuxer list. Inside single quotes everything is literal
    (Windows backslashes included); a quote itself is written '\\''.

    Each file gets an explicit duration so that its place in the film is exactly
    the one its chapter announces (see FilmPlan.segment).
    """
    lines = ["ffconcat version 1.0"]
    for part in plan.parts:
        path = str(part.path.resolve()).replace("'", "'\\''")
        lines.append(f"file '{path}'")
        lines.append(f"duration {plan.segment(part, reencode=False):.6f}")
    return "\n".join(lines) + "\n"


def chapter_marks(plan: FilmPlan, reencode: bool = False) -> list[tuple[int, float, float]]:
    """(episode, start, end) in seconds for each chapter, back to back."""
    marks, start = [], 0.0
    for part in plan.parts:
        end = start + plan.segment(part, reencode)
        marks.append((part.number, start, end))
        start = end
    return marks


def ffmetadata(plan: FilmPlan, chapters: bool = True, reencode: bool = False) -> str:
    lines = [";FFMETADATA1", f"title={_escape_meta(plan.title)}"]
    if chapters:
        for number, start, end in chapter_marks(plan, reencode):
            lines += [
                "[CHAPTER]",
                "TIMEBASE=1/1000",
                f"START={round(start * 1000)}",
                f"END={round(end * 1000)}",
                f"title={_escape_meta(f'Épisode {number}')}",
            ]
    return "\n".join(lines) + "\n"


def _escape_meta(text: str) -> str:
    return re.sub(r"([=;#\\\n])", r"\\\1", text)


def safe_filename(title: str) -> str:
    name = _FORBIDDEN_CHARS_RE.sub("", title)
    name = re.sub(r"\s+", " ", name).strip(" .")
    return name[:150] or "film"


FFMPEG_HELP = (
    "ffmpeg est nécessaire pour la fusion. Au choix :\n"
    "  - pip install imageio-ffmpeg   (le plus simple, fournit ffmpeg sans installation système)\n"
    "  - Windows : winget install Gyan.FFmpeg   |   macOS : brew install ffmpeg   |   Linux : apt install ffmpeg\n"
    "  - ou indique son chemin avec --ffmpeg"
)


def ffmpeg_info(explicit: str | None = None) -> dict:
    """Where ffmpeg comes from: {"found", "path", "source": option | PATH | imageio-ffmpeg}."""
    if explicit:
        found = shutil.which(explicit) or (explicit if Path(explicit).is_file() else None)
        return {"found": bool(found), "path": found, "source": "option"}
    found = shutil.which("ffmpeg")
    if found:
        return {"found": True, "path": found, "source": "PATH"}
    try:
        import imageio_ffmpeg  # optional: pip install imageio-ffmpeg

        return {"found": True, "path": imageio_ffmpeg.get_ffmpeg_exe(), "source": "imageio-ffmpeg"}
    except Exception:
        return {"found": False, "path": None, "source": None}


def find_ffmpeg(explicit: str | None = None) -> str:
    """ffmpeg from --ffmpeg, the PATH, or the imageio-ffmpeg package."""
    info = ffmpeg_info(explicit)
    if info["found"]:
        return info["path"]
    if explicit:
        raise FilmError(f"ffmpeg introuvable à l'emplacement indiqué : {explicit}", errors.FFMPEG_MISSING)
    raise FilmError(FFMPEG_HELP, errors.FFMPEG_MISSING)


def _run_ffmpeg(
    args: list[str],
    total: float,
    log_path: Path,
    on_progress: Progress | None,
    stop: threading.Event | None = None,
) -> None:
    with log_path.open("w+", encoding="utf-8", errors="replace") as log:
        try:
            proc = subprocess.Popen(
                args, stdout=subprocess.PIPE, stderr=log, text=True, encoding="utf-8", errors="replace"
            )
        except OSError as e:
            raise FilmError(f"Impossible de lancer ffmpeg : {e}", errors.FFMPEG_MISSING) from None
        try:
            for line in proc.stdout:  # -progress writes a block about twice per second
                if stop is not None and stop.is_set():
                    raise FilmError("Création du film annulée.", errors.CANCELLED)
                key, _, value = line.strip().partition("=")
                if on_progress and key in ("out_time_us", "out_time_ms") and value.isdigit():
                    on_progress(min(int(value) / 1e6, total), total)  # both are microseconds
            code = proc.wait()
        except BaseException:
            proc.kill()
            proc.wait()
            raise
        if code != 0:
            log.seek(0)
            details = log.read().strip().splitlines()[-5:]
            raise FilmError("ffmpeg a échoué :\n  " + "\n  ".join(details or [f"code {code}"]), errors.FILM_FAILED)


def _record_in_manifest(plan: FilmPlan, result: FilmResult, marks: list[tuple[int, float, float]]) -> None:
    manifest = Manifest.load(plan.series_dir)
    if manifest is None:
        return
    manifest.set(
        "film",
        {
            "file": result.path.name if result.path.parent == plan.series_dir else str(result.path),
            "episodes": [p.number for p in plan.parts],
            "missing": plan.missing,
            "duration_s": round(result.duration, 3),
            "bytes": result.size,
            "mode": result.mode,
            "chapters": result.chapters,
            "chapter_times": [[n, round(start, 3), round(end, 3)] for n, start, end in marks],
            "created_at": now_iso(),
        },
    )


def format_duration(seconds: float) -> str:
    """5538.6 -> "1 h 32 min 19 s", 79.1 -> "1 min 19 s"."""
    seconds = round(seconds)
    h, m, s = seconds // 3600, seconds % 3600 // 60, seconds % 60
    return f"{h} h {m:02d} min {s:02d} s" if h else f"{m} min {s:02d} s"


def format_ranges(numbers: list[int]) -> str:
    """[1, 2, 3, 7, 9, 10] -> "1-3, 7, 9-10"."""
    out, numbers = [], sorted(numbers)
    start = prev = numbers[0]
    for n in numbers[1:] + [None]:
        if n is not None and n == prev + 1:
            prev = n
            continue
        out.append(str(start) if start == prev else f"{start}-{prev}")
        if n is not None:
            start = prev = n
    return ", ".join(out)
