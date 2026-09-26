"""Command line: ``sdg`` or ``python -m shortdramagen``."""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

from . import __version__, dramafren, film, official, pipeline
from .http import Http
from .inputs import InputError, parse_input

QUALITIES = ("best", "1080p", "720p", "540p")


def parse_episodes(spec: str | None) -> pipeline.EpisodeRanges | None:
    """"1-10,28,50-" -> [(1, 10), (28, 28), (50, None)] (None = up to the last episode)."""
    if not spec:
        return None
    ranges: pipeline.EpisodeRanges = []
    for part in spec.split(","):
        part = part.strip()
        m = re.fullmatch(r"(\d+)(?:-(\d*))?", part)
        if not m:
            raise argparse.ArgumentTypeError(f"plage d'épisodes invalide : {part!r}")
        start = int(m.group(1))
        if m.group(2) is None:
            ranges.append((start, start))
        else:
            end = int(m.group(2)) if m.group(2) else None
            if end is not None and end < start:
                raise argparse.ArgumentTypeError(f"plage d'épisodes à l'envers : {part!r}")
            ranges.append((start, end))
    return ranges


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="sdg",
        description="Récupère automatiquement tous les épisodes d'une série DramaBox.",
    )
    parser.add_argument("--version", action="version", version=f"%(prog)s {__version__}")
    sub = parser.add_subparsers(dest="command", required=True)

    def common(p: argparse.ArgumentParser) -> None:
        p.add_argument("url", help="URL dramaboxdb.com / dramabox.com / dramafren, lien de partage ou identifiant")
        p.add_argument("--lang", help="langue (en, fr, es, ...) : version doublée si elle existe")

    def selection(p: argparse.ArgumentParser) -> None:
        p.add_argument("-q", "--quality", choices=QUALITIES, default="best", help="qualité (défaut : best)")
        p.add_argument("-e", "--episodes", type=parse_episodes, help='épisodes à traiter, ex. "1-10,28,40-"')

    def downloads_dir(p: argparse.ArgumentParser) -> None:
        p.add_argument("-o", "--out", type=Path, default=Path("downloads"), help="dossier des téléchargements (défaut : downloads)")

    def ffmpeg_path(p: argparse.ArgumentParser) -> None:
        p.add_argument("--ffmpeg", help="chemin de ffmpeg (défaut : PATH, puis le paquet imageio-ffmpeg)")

    p_info = sub.add_parser("info", help="affiche les infos de la série, sans rien télécharger")
    common(p_info)
    p_info.set_defaults(handler=cmd_info)

    p_fetch = sub.add_parser("fetch", help="télécharge les épisodes")
    common(p_fetch)
    selection(p_fetch)
    downloads_dir(p_fetch)
    p_fetch.add_argument("-j", "--jobs", type=int, default=3, help="téléchargements en parallèle (défaut : 3)")
    p_fetch.add_argument("--film", action="store_true", help="fusionne ensuite les épisodes en un seul film")
    ffmpeg_path(p_fetch)
    p_fetch.set_defaults(handler=cmd_fetch)

    p_links = sub.add_parser("links", help="résout les URLs sans télécharger (pour aria2c, IDM...)")
    common(p_links)
    selection(p_links)
    p_links.add_argument("--json", action="store_true", help="sortie JSON au lieu d'une URL par ligne")
    p_links.set_defaults(handler=cmd_links)

    p_film = sub.add_parser(
        "film", aliases=["concat"], help="fusionne les épisodes téléchargés en un seul film (chapitres inclus)"
    )
    p_film.add_argument("target", help="dossier de la série, ou URL / identifiant déjà téléchargé avec fetch")
    p_film.add_argument("--lang", help="version à fusionner si plusieurs langues ont été téléchargées")
    downloads_dir(p_film)
    p_film.add_argument("-f", "--file", type=Path, help="film à créer (défaut : <dossier de la série>/<titre>.mp4)")
    p_film.add_argument("--reencode", action="store_true", help="ré-encode tout (lent) : nécessaire si les qualités sont mélangées")
    p_film.add_argument("--allow-missing", action="store_true", help="fusionne même s'il manque des épisodes")
    p_film.add_argument("--no-chapters", action="store_true", help="n'ajoute pas un chapitre par épisode")
    ffmpeg_path(p_film)
    p_film.set_defaults(handler=cmd_film)
    return parser


def main(argv: list[str] | None = None) -> int:
    for stream in (sys.stdout, sys.stderr):
        if hasattr(stream, "reconfigure"):
            stream.reconfigure(errors="replace")  # old Windows consoles

    args = build_parser().parse_args(argv)
    log = lambda msg: print(msg, file=sys.stderr, flush=True)  # noqa: E731
    try:
        return args.handler(args, log)
    except InputError as e:
        print(e, file=sys.stderr)
        return 2
    except (official.SeriesNotFound, film.FilmError) as e:
        print(e, file=sys.stderr)
        return 1
    except KeyboardInterrupt:
        print("\nInterrompu. Relance la même commande pour reprendre.", file=sys.stderr)
        return 130


def cmd_info(args, log) -> int:
    http, ref = Http(), parse_input(args.url)
    series, _ = pipeline.load_series(http, ref, args.lang, log)
    free = [ep.number for ep in series.episodes if ep.free_url]
    print(f"Titre        : {series.title}")
    print(f"ID série     : {series.book_id}  (vidéos : {series.source_book_id}, langue : {series.lang or '?'})")
    print(f"Épisodes     : {series.episode_count}")
    if series.from_official:
        total_s = sum(ep.duration_ms or 0 for ep in series.episodes) / 1000
        print(f"Durée totale : {int(total_s // 3600)} h {int(total_s % 3600 // 60):02d} min")
        print(f"Gratuits     : {len(free)} sur le site officiel (épisodes {free[0]}-{free[-1]})" if free else "Gratuits     : aucun")
        print(f"Langues      : {', '.join(series.languages)}")
    if series.introduction:
        print(f"\n{series.introduction}")
    try:
        sources = dramafren.get_video(http, series.source_book_id, series.episodes[-1].number)
        print(f"\ndramafren    : OK (dernier épisode dispo en {', '.join(s.quality for s in sources)})")
    except dramafren.ResolveError as e:
        print(f"\ndramafren    : indisponible ({e})")
    return 0


def cmd_fetch(args, log) -> int:
    http, ref = Http(), parse_input(args.url)
    ffmpeg = film.find_ffmpeg(args.ffmpeg) if args.film else None  # fail before downloading
    opts = pipeline.FetchOptions(
        out_dir=args.out, lang=args.lang, quality=args.quality, jobs=args.jobs, episodes=args.episodes
    )
    result = pipeline.fetch(http, ref, opts, log)
    n_ok = len(result.done) + len(result.skipped)
    log(
        f"\nTerminé : {n_ok} épisode(s) OK ({len(result.done)} téléchargé(s), "
        f"{len(result.skipped)} déjà présent(s)), {len(result.failed)} échec(s)."
    )
    if result.failed:
        log(f"Épisodes en échec : {sorted(result.failed)}. Relance la même commande pour réessayer.")
        if args.film:
            log("Film non créé : il manque des épisodes.")
        return 1
    if args.film:
        selected = set(result.done + result.skipped) if args.episodes else None
        make_film(result.series_dir, ffmpeg, log, only=selected)
    return 0


def cmd_film(args, log) -> int:
    target = Path(args.target)
    if target.is_dir():
        series_dir = target
    else:
        series_dir = film.find_series_dir(args.out, parse_input(args.target), args.lang)
    make_film(
        series_dir,
        film.find_ffmpeg(args.ffmpeg),
        log,
        output=args.file,
        reencode=args.reencode,
        allow_missing=args.allow_missing,
        chapters=not args.no_chapters,
    )
    return 0


def make_film(
    series_dir: Path,
    ffmpeg: str,
    log,
    output: Path | None = None,
    reencode: bool = False,
    allow_missing: bool = False,
    chapters: bool = True,
    only: set[int] | None = None,
) -> film.FilmResult:
    plan = film.plan_film(series_dir, allow_missing, only)
    film.ensure_joinable(plan, reencode)
    if plan.missing:
        log(f"Attention : épisodes absents, film incomplet (manquent : {film.format_ranges(plan.missing)})")
    output = output or film.default_output(plan)
    how = "avec ré-encodage, c'est long" if reencode else "sans ré-encodage"
    log(f"Fusion de {len(plan.parts)} épisodes ({_hms(plan.duration)}, {how}) -> {output}")
    progress = _ProgressPrinter()
    try:
        result = film.build_film(plan, output, ffmpeg, reencode, chapters, progress)
    finally:
        progress.finish()
    log(f"Film créé : {result.path} ({_hms(result.duration)}, {result.size / 1e6:.0f} Mo)")
    return result


class _ProgressPrinter:
    """Percentage on one line in a terminal, every 25 % otherwise (logs, pipes)."""

    def __init__(self):
        self.tty = sys.stderr.isatty()
        self.last = -1

    def __call__(self, done: float, total: float) -> None:
        pct = int(done * 100 / total) if total else 100
        if self.tty and pct != self.last:
            print(f"\r  {pct:3d} %", end="", file=sys.stderr, flush=True)
            self.last = pct
        elif not self.tty and pct >= self.last + 25:
            print(f"  {pct} %", file=sys.stderr, flush=True)
            self.last = pct - pct % 25

    def finish(self) -> None:
        if self.tty and self.last >= 0:
            print(file=sys.stderr, flush=True)


def _hms(seconds: float) -> str:
    seconds = round(seconds)
    h, m, s = seconds // 3600, seconds % 3600 // 60, seconds % 60
    return f"{h} h {m:02d} min {s:02d} s" if h else f"{m} min {s:02d} s"


def cmd_links(args, log) -> int:
    http, ref = Http(), parse_input(args.url)
    opts = pipeline.FetchOptions(lang=args.lang, quality=args.quality, episodes=args.episodes)
    series, links = pipeline.resolve_links(http, ref, opts, log)
    if args.json:
        print(json.dumps({"title": series.title, "book_id": series.book_id, "episodes": links}, ensure_ascii=False, indent=2))
    else:
        for link in links:
            print(link["url"])
    return 0 if len(links) == len(pipeline.select_episodes(series, opts.episodes, lambda _: None)) else 1
