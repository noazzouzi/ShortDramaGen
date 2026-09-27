"""Command line: ``sdg`` or ``python -m shortdramagen``."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from . import __version__, errors, film, inputs, pipeline
from .providers import registry
from .http import TRANSIENT_ERRORS, Http, HttpStatusError
from .inputs import InputError, parse_input
from .manifest import ManifestError

QUALITIES = ("best", "1080p", "720p", "540p")


def parse_episodes(spec: str | None) -> inputs.EpisodeRanges | None:
    """argparse type for -e: inputs.parse_episodes with argparse's error type."""
    try:
        return inputs.parse_episodes(spec)
    except InputError as e:
        raise argparse.ArgumentTypeError(str(e)) from None


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="sdg",
        description="Récupère automatiquement tous les épisodes d'une série DramaBox.",
    )
    parser.add_argument("--version", action="version", version=f"%(prog)s {__version__}")
    sub = parser.add_subparsers(dest="command", required=True)

    def common(p: argparse.ArgumentParser) -> None:
        p.add_argument("url", help="lien d'une série (DramaBox, GoodShort), n° DramaBox ou plateforme:n°")
        p.add_argument("--lang", help="langue (en, fr, es, ...) : version doublée si elle existe")

    def selection(p: argparse.ArgumentParser) -> None:
        p.add_argument("-q", "--quality", choices=QUALITIES, default="best", help="qualité (défaut : best)")
        p.add_argument("-e", "--episodes", type=parse_episodes, help='épisodes à traiter, ex. "1-10,28,40-"')

    def downloads_dir(p: argparse.ArgumentParser) -> None:
        p.add_argument("-o", "--out", type=Path, default=Path("downloads"), help="dossier des téléchargements (défaut : downloads)")

    def ffmpeg_path(p: argparse.ArgumentParser) -> None:
        p.add_argument("--ffmpeg", help="chemin de ffmpeg (défaut : PATH, puis le paquet imageio-ffmpeg)")

    def film_options(p: argparse.ArgumentParser, prefix: str = "") -> None:
        p.add_argument("--reencode", action="store_true", help=f"{prefix}ré-encode tout (lent) : nécessaire si les qualités sont mélangées")
        p.add_argument("--allow-missing", action="store_true", help=f"{prefix}fusionne même s'il manque des épisodes")
        p.add_argument("--no-chapters", action="store_true", help=f"{prefix}n'ajoute pas un chapitre par épisode")
        p.add_argument("--replace", action="store_true", help=f"{prefix}remplace un film existant (sinon il est gardé s'il est à jour)")

    p_info = sub.add_parser("info", help="affiche les infos de la série, sans rien télécharger")
    common(p_info)
    p_info.set_defaults(handler=cmd_info)

    p_fetch = sub.add_parser("fetch", help="télécharge les épisodes")
    common(p_fetch)
    selection(p_fetch)
    downloads_dir(p_fetch)
    p_fetch.add_argument("-j", "--jobs", type=int, default=3, help="téléchargements en parallèle (défaut : 3)")
    p_fetch.add_argument("--film", action="store_true", help="fusionne ensuite les épisodes en un seul film")
    film_options(p_fetch, "avec --film : ")
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
    film_options(p_film)
    ffmpeg_path(p_film)
    p_film.set_defaults(handler=cmd_film)

    p_ui = sub.add_parser("ui", help="ouvre l'interface web locale : bibliothèque, lecture des épisodes et des films")
    p_ui.add_argument(
        "-o", "--out", type=Path,
        help="dossier des téléchargements, mémorisé pour les fois suivantes (défaut : le dernier utilisé, sinon ./downloads)",
    )  # fmt: skip
    p_ui.add_argument("--port", type=port_number, help="port local (défaut : 8765, sinon le premier libre jusqu'à 8775)")
    p_ui.add_argument("--no-browser", action="store_true", help="n'ouvre pas le navigateur")
    p_ui.add_argument("--window", action="store_true", help="ouvre une fenêtre d'application (Edge ou Chrome) au lieu d'un onglet")
    p_ui.set_defaults(handler=cmd_ui)
    return parser


def port_number(text: str) -> int:
    if not text.isdigit() or not 1 <= int(text) <= 65535:
        raise argparse.ArgumentTypeError("port attendu : un nombre de 1 à 65535")
    return int(text)


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
    except (errors.SeriesNotFound, film.FilmError, ManifestError) as e:
        print(e, file=sys.stderr)
        return 1
    except (HttpStatusError, *TRANSIENT_ERRORS) as e:
        print(f"Erreur réseau ou disque : {e}", file=sys.stderr)
        return 1
    except KeyboardInterrupt:
        print("\nInterrompu. Relance la même commande pour reprendre.", file=sys.stderr)
        return 130


def cmd_info(args, log) -> int:
    http, ref = Http(), parse_input(args.url)

    def on_event(name: str, data: dict) -> None:
        if name == "lang_fallback":
            log(
                f"Attention : langue « {data['requested']} » indisponible pour cette série, version originale "
                f"utilisée (disponibles : {', '.join(data['available'])})"
            )

    preview = pipeline.preview_series(http, ref, args.lang, pipeline.FetchControl(on_event=on_event))
    series = preview.series
    free = series.free_numbers
    print(f"Plateforme   : {registry.get(series.provider).label}")
    print(f"Titre        : {series.title}")
    if series.title_vo and series.title_vo != series.title:
        print(f"Titre VO     : {series.title_vo}")
    print(f"ID série     : {series.book_id}  (vidéos : {series.source_book_id}, langue : {series.lang or '?'})")
    print(f"Épisodes     : {series.episode_count}")
    total_ms = series.total_duration_ms
    if total_ms:
        print(f"Durée totale : {film.format_duration(total_ms / 1000)}")
    print(f"Gratuits     : {len(free)} sur le site officiel (épisodes {free[0]}-{free[-1]})" if free else "Gratuits     : aucun")
    print(f"Langues      : {', '.join(series.languages)}")
    if series.introduction:
        print(f"\n{series.introduction}")
    if not preview.available:
        print(f"\nSource       : indisponible ({preview.source_error})")
    elif series.free_only:
        print("\nSource       : site officiel, épisodes gratuits seulement")
    else:
        print(f"\nSource       : OK (dernier épisode dispo en {', '.join(preview.qualities)})")
    return 0


def cmd_fetch(args, log) -> int:
    http, ref = Http(), parse_input(args.url)
    ffmpeg = film.find_ffmpeg(args.ffmpeg) if args.film else None  # fail before downloading
    opts = pipeline.FetchOptions(
        out_dir=args.out, lang=args.lang, quality=args.quality, jobs=args.jobs, episodes=args.episodes,
        ffmpeg_path=args.ffmpeg,
    )
    result = pipeline.fetch(http, ref, opts, log)
    n_ok = len(result.done) + len(result.skipped)
    log(
        f"\nTerminé : {n_ok} épisode(s) OK ({len(result.done)} téléchargé(s), "
        f"{len(result.skipped)} déjà présent(s)), {len(result.failed)} échec(s)."
    )
    if result.stop_reason:
        log("Arrêt avant la fin : libère de la place puis relance la même commande.")
        return 1
    if result.failed:
        log(f"Épisodes en échec : {sorted(result.failed)}. Relance la même commande pour réessayer.")
        if args.film and not args.allow_missing:
            log("Film non créé : il manque des épisodes (--allow-missing pour un film partiel).")
            return 1
    if args.film:
        # With -e, the film holds the requested episodes; otherwise the whole version.
        selected = set(result.done + result.skipped) if args.episodes else None
        _make_film(
            result.series_dir, ffmpeg, log, reencode=args.reencode, allow_missing=args.allow_missing,
            chapters=not args.no_chapters, only=selected, replace=args.replace,
        )  # fmt: skip
    return 1 if result.failed else 0


def cmd_film(args, log) -> int:
    target = Path(args.target)
    if target.is_dir():
        series_dir = target
    else:
        series_dir = film.find_series_dir(args.out, parse_input(args.target), args.lang)
    _make_film(
        series_dir, film.find_ffmpeg(args.ffmpeg), log, output=args.file, reencode=args.reencode,
        allow_missing=args.allow_missing, chapters=not args.no_chapters, replace=args.replace,
    )  # fmt: skip
    return 0


def _make_film(series_dir: Path, ffmpeg: str, log, **options) -> film.FilmResult:
    progress = _ProgressPrinter()
    try:
        return film.make_film(series_dir, ffmpeg, log, on_progress=progress, **options)
    finally:
        progress.finish()


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


def cmd_links(args, log) -> int:
    http, ref = Http(), parse_input(args.url)
    opts = pipeline.FetchOptions(lang=args.lang, quality=args.quality, episodes=args.episodes)
    series, links = pipeline.resolve_links(http, ref, opts, log)
    if args.json:
        data = {"title": series.title, "provider": series.provider, "book_id": series.book_id, "episodes": links}
        print(json.dumps(data, ensure_ascii=False, indent=2))
    else:
        for link in links:
            print(link["url"])
    wanted = pipeline.default_selection(series, opts.episodes)
    return 0 if len(links) == len(pipeline.select_episodes(series, wanted, lambda _: None)) else 1


def cmd_ui(args, log) -> int:
    from .server.launch import run_ui  # the server is only loaded when needed

    return run_ui(args.out, args.port, open_browser=not args.no_browser, window=args.window, log=log)
