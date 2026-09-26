"""Command line: ``sdg`` or ``python -m shortdramagen``."""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

from . import __version__, dramafren, official, pipeline
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

    p_info = sub.add_parser("info", help="affiche les infos de la série, sans rien télécharger")
    common(p_info)

    p_fetch = sub.add_parser("fetch", help="télécharge les épisodes")
    common(p_fetch)
    selection(p_fetch)
    p_fetch.add_argument("-o", "--out", type=Path, default=Path("downloads"), help="dossier de sortie (défaut : downloads)")
    p_fetch.add_argument("-j", "--jobs", type=int, default=3, help="téléchargements en parallèle (défaut : 3)")

    p_links = sub.add_parser("links", help="résout les URLs sans télécharger (pour aria2c, IDM...)")
    common(p_links)
    selection(p_links)
    p_links.add_argument("--json", action="store_true", help="sortie JSON au lieu d'une URL par ligne")
    return parser


def main(argv: list[str] | None = None) -> int:
    for stream in (sys.stdout, sys.stderr):
        if hasattr(stream, "reconfigure"):
            stream.reconfigure(errors="replace")  # old Windows consoles

    args = build_parser().parse_args(argv)
    try:
        ref = parse_input(args.url)
    except InputError as e:
        print(e, file=sys.stderr)
        return 2
    http = Http()
    log = lambda msg: print(msg, file=sys.stderr, flush=True)  # noqa: E731

    try:
        if args.command == "info":
            return cmd_info(http, ref, args, log)
        if args.command == "fetch":
            return cmd_fetch(http, ref, args, log)
        return cmd_links(http, ref, args, log)
    except official.SeriesNotFound as e:
        print(e, file=sys.stderr)
        return 1
    except KeyboardInterrupt:
        print("\nInterrompu. Relance la même commande pour reprendre.", file=sys.stderr)
        return 130


def cmd_info(http: Http, ref, args, log) -> int:
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


def cmd_fetch(http: Http, ref, args, log) -> int:
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
        return 1
    return 0


def cmd_links(http: Http, ref, args, log) -> int:
    opts = pipeline.FetchOptions(lang=args.lang, quality=args.quality, episodes=args.episodes)
    series, links = pipeline.resolve_links(http, ref, opts, log)
    if args.json:
        print(json.dumps({"title": series.title, "book_id": series.book_id, "episodes": links}, ensure_ascii=False, indent=2))
    else:
        for link in links:
            print(link["url"])
    return 0 if len(links) == len(pipeline.select_episodes(series, opts.episodes, lambda _: None)) else 1
