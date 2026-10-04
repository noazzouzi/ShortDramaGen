"""Command line: ``sdg`` or ``python -m shortdramagen``."""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

from . import __version__, errors, film, inputs, montage, pipeline
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
        p.add_argument("--montage", action="store_true", help=f"{prefix}applique le montage de la série (sdg montage) avant la fusion")

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

    add_montage_parser(sub, downloads_dir, ffmpeg_path)

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


def add_montage_parser(sub, downloads_dir, ffmpeg_path) -> None:
    p = sub.add_parser("montage", help="retouche les épisodes (miroir, coupes, look, vitesse, effets) avant le film")
    msub = p.add_subparsers(dest="montage_command", required=True)

    def target(q: argparse.ArgumentParser) -> None:
        q.add_argument("target", help="dossier de la série, ou URL / identifiant déjà téléchargé avec fetch")
        q.add_argument("--lang", help="version à retoucher si plusieurs langues ont été téléchargées")
        downloads_dir(q)

    q = msub.add_parser("show", help="affiche le montage de la série")
    target(q)
    q.set_defaults(handler=cmd_montage_show)

    q = msub.add_parser("set", help="modifie le montage (toute la série, ou un épisode avec -e)")
    target(q)
    q.add_argument("-e", "--episode", type=int, help="retouche propre à cet épisode (coupes, passages)")
    q.add_argument("--mirror", action=argparse.BooleanOptionalAction, help="image retournée gauche-droite")
    q.add_argument("--keep-subs", action=argparse.BooleanOptionalAction,
                   help="avec --mirror : garde les sous-titres incrustés lisibles (défaut : oui)")  # fmt: skip
    q.add_argument("--band", help='zone des sous-titres en %% de la hauteur, ex. "74-84", ou "auto"')
    q.add_argument("--trim-start", type=seconds, help="secondes retirées au début de chaque épisode (ex. 5, 1:05)")
    q.add_argument("--trim-end", type=seconds, help="secondes retirées à la fin de chaque épisode")
    q.add_argument("--speed", type=float, help="vitesse de toute la vidéo (0,5 à 3 ; ex. 1.25)")
    q.add_argument("--look", choices=list(montage.LOOKS), help="couleurs : " + ", ".join(montage.LOOKS))
    q.add_argument("--brightness", type=float, help="luminosité (-0,3 à 0,3)")
    q.add_argument("--contrast", type=float, help="contraste (0,5 à 2)")
    q.add_argument("--saturation", type=float, help="saturation (0 à 3 ; 0 = noir et blanc)")
    q.add_argument("--effects", action=argparse.BooleanOptionalAction,
                   help="--no-effects coupe tous les effets ci-dessous ; --effects les remet à leur valeur par défaut")  # fmt: skip
    q.add_argument("--zoom", type=float, help="zoom au centre, en %% (0 à 15 ; défaut : 4)")
    q.add_argument("--temperature", type=float, help="couleur : -100 (bleu) à 100 (orange) ; défaut : 30")
    q.add_argument("--curve", choices=list(montage.CURVES), help="courbe de luminance (défaut : douce)")
    q.add_argument("--grain", type=float, help="grain de film (0 à 20 ; défaut : 4 ; au-delà de 5, les fichiers grossissent vite)")
    q.add_argument("--staccato", choices=montage.TRANSITIONS,
                   help="découpe rapide : un effet tous les 1 à 2 s (défaut : zoom)")  # fmt: skip
    q.add_argument("--staccato-every", type=staccato_lengths, metavar="MIN-MAX",
                   help='durée des segments de la découpe rapide, ex. "1-2" (secondes)')  # fmt: skip
    q.add_argument("--stretch", type=float, help="tempo de toute la vidéo, en %% (-10 à 10 ; défaut : 3)")
    q.add_argument("--pitch", type=float, help="hauteur du son, en demi-tons (-3 à 3 ; défaut : 0,5)")
    q.add_argument("--eq", choices=list(montage.EQS), help="égaliseur (défaut : shelf)")
    q.add_argument("--bed", choices=list(montage.BEDS), help="fond sonore discret (défaut : vent)")
    q.add_argument("--bed-level", type=float, help="niveau du fond sonore, en dB (-60 à -20 ; défaut : -40)")
    q.add_argument("--encoder", choices=montage.ENCODERS, help="encodeur (défaut : auto, AMF s'il marche, sinon x264)")
    q.add_argument("--quality", choices=montage.QUALITIES, help="qualité (défaut : standard)")
    q.add_argument("--range", dest="ranges", action="append", type=passage, default=[],
                   help='avec -e : passage accéléré, ex. "0:40-0:55x1.5" (répétable)')  # fmt: skip
    q.add_argument("--cut", dest="cuts", action="append", type=passage, default=[],
                   help='avec -e : passage coupé, ex. "1:20-1:32" (répétable)')  # fmt: skip
    q.add_argument("--clear-ranges", action="store_true", help="avec -e : retire les passages de cet épisode")
    q.set_defaults(handler=cmd_montage_set)

    q = msub.add_parser("reset", help="supprime le montage (ou la retouche d'un épisode avec -e)")
    target(q)
    q.add_argument("-e", "--episode", type=int, help="seulement la retouche propre à cet épisode")
    q.set_defaults(handler=cmd_montage_reset)

    q = msub.add_parser("preview", help="rend quelques secondes d'un épisode pour juger du résultat")
    target(q)
    q.add_argument("-e", "--episode", type=int, default=1, help="épisode (défaut : 1)")
    q.add_argument("--at", type=seconds, default=0.0, help="à partir de (secondes de l'épisode, ex. 40 ou 0:40)")
    q.add_argument("--seconds", type=float, default=8.0, help="durée (défaut : 8, au plus 30)")
    q.add_argument("-f", "--file", type=Path, help="fichier à créer (défaut : <série>/montage/.apercu.mp4)")
    ffmpeg_path(q)
    q.set_defaults(handler=cmd_montage_preview)

    q = msub.add_parser("render", help="monte les épisodes sans créer le film (ceux déjà à jour sont gardés)")
    target(q)
    q.add_argument("-e", "--episodes", type=parse_episodes, help='épisodes, ex. "1-10,28"')
    q.add_argument("--force", action="store_true", help="refait aussi les épisodes à jour")
    ffmpeg_path(q)
    q.set_defaults(handler=cmd_montage_render)


_TIME_RE = re.compile(r"^(?:(\d+):)?(\d+(?:[.,]\d+)?)$")
_PASSAGE_RE = re.compile(r"^([\d:.,]+)-([\d:.,]+)(?:x([\d.,]+))?$")
_BAND_RE = re.compile(r"^\s*(\d+(?:[.,]\d+)?)\s*-\s*(\d+(?:[.,]\d+)?)\s*$")


def seconds(text: str) -> float:
    """argparse type: "90", "1:30", "1:30.5" -> seconds."""
    m = _TIME_RE.match(text.strip())
    if not m:
        raise argparse.ArgumentTypeError(f"durée attendue en secondes ou min:s, pas {text!r}")
    return int(m.group(1) or 0) * 60 + float(m.group(2).replace(",", "."))


def staccato_lengths(text: str) -> tuple[float, float]:
    """argparse type: "1-2" or "1,5" -> (min, max) seconds."""
    m = _BAND_RE.match(text) or re.match(r"^\s*(\d+(?:[.,]\d+)?)\s*$", text)
    if not m:
        raise argparse.ArgumentTypeError(f'durées attendues comme "1-2" (secondes), pas {text!r}')
    values = [float(g.replace(",", ".")) for g in m.groups()]
    return values[0], values[-1]


def passage(text: str) -> dict:
    """argparse type: "0:40-0:55x1.5" (accéléré) or "1:20-1:32" (coupé : sans x)."""
    m = _PASSAGE_RE.match(text.strip())
    if not m:
        raise argparse.ArgumentTypeError(f'passage attendu comme "0:40-0:55x1.5" ou "1:20-1:32", pas {text!r}')
    item = {"from": seconds(m.group(1)), "to": seconds(m.group(2))}
    if m.group(3):
        item["speed"] = float(m.group(3).replace(",", "."))
    return item


def _series_dir(args) -> Path:
    target = Path(args.target)
    return target if target.is_dir() else film.find_series_dir(args.out, parse_input(args.target), args.lang)


def _clock(value: float) -> str:
    """75.5 -> "1:15.5", 40 -> "40"."""
    if value < 60:
        return f"{value:g}"
    return f"{int(value // 60)}:{value % 60:04.1f}".replace(".0", "")


def cmd_montage_show(args, log) -> int:
    series_dir = _series_dir(args)
    recipe = montage.load(series_dir)
    if recipe is None:
        print(f"Pas de montage réglé pour {series_dir.name} : le montage par défaut s'appliquera.")
        print(f"Montage : {montage.describe(montage.validate({}))}")
        print(f"Exemple : sdg montage set {args.target} --trim-start 3 --no-effects")
        return 0
    print(f"Montage : {montage.describe(recipe)}")
    for number, ep in sorted(recipe["episodes"].items(), key=lambda kv: int(kv[0])):
        parts = []
        if "trim" in ep:
            names = {"start": "début", "end": "fin"}
            parts.append(", ".join(f"coupe {v:g} s ({names[k]})" for k, v in ep["trim"].items()))
        for r in ep.get("ranges", []):
            parts.append(f"{_clock(r['from'])}-{_clock(r['to'])} " + ("coupé" if r.get("cut") else f"×{r['speed']:g}"))
        print(f"  Épisode {number} : {', '.join(parts)}")
    status = montage.status(series_dir)
    if status["band"]:
        print(f"Sous-titres  : entre {status['band'][0]:.0%} et {status['band'][1]:.0%} de la hauteur")
    print(f"Déjà montés  : {status['rendered']} épisode(s), {status['bytes'] / 1e9:.1f} Go ({montage.montage_dir(series_dir)})")
    print(f"Recette      : {series_dir / montage.RECIPE_FILE}")
    return 0


def cmd_montage_set(args, log) -> int:
    series_dir = _series_dir(args)
    recipe = montage.load(series_dir) or montage.validate({})
    if args.episode is not None:
        if args.episode < 1:
            raise InputError("numéro d'épisode attendu (1, 2, …)")
        series_wide = ("mirror", "keep_subs", "band", "speed", "look", "brightness", "contrast", "saturation", *EFFECT_ARGS,
                       "encoder", "quality")  # fmt: skip
        used = [f for f in series_wide if getattr(args, f) is not None]
        if used:
            raise InputError(f"--{used[0].replace('_', '-')} vaut pour toute la série : retire -e")
        if any("speed" not in r for r in args.ranges):
            raise InputError('--range attend une vitesse, ex. "0:40-0:55x1.5" (pour couper un passage : --cut)')
        if any("speed" in c for c in args.cuts):
            raise InputError('--cut ne prend pas de vitesse, ex. "1:20-1:32"')
        ep = recipe["episodes"].setdefault(str(args.episode), {})
        trim = {k: v for k, v in (("start", args.trim_start), ("end", args.trim_end)) if v is not None}
        if trim:
            ep["trim"] = {**ep.get("trim", {}), **trim}
        if args.clear_ranges:
            ep.pop("ranges", None)
        added = [*args.ranges, *({**c, "cut": True} for c in args.cuts)]
        if added:
            ep["ranges"] = [*ep.get("ranges", []), *added]
        if not ep:
            recipe["episodes"].pop(str(args.episode))
    else:
        if args.ranges or args.cuts or args.clear_ranges:
            raise InputError("--range, --cut et --clear-ranges s'appliquent à un épisode : ajoute -e N")
        for arg, key in (("mirror", "mirror"), ("keep_subs", "keep_subtitles"), ("speed", "speed")):
            if getattr(args, arg) is not None:
                recipe[key] = getattr(args, arg)
        if args.band is not None:
            recipe["subtitle_band"] = _band(args.band)
        for arg, key in (("trim_start", "start"), ("trim_end", "end")):
            if getattr(args, arg) is not None:
                recipe["trim"][key] = getattr(args, arg)
        if args.look is not None:
            recipe["look"] = {"preset": args.look}
        for key in montage.LOOK_LIMITS:
            if getattr(args, key) is not None:
                recipe["look"][key] = getattr(args, key)
        _set_effects(recipe, args)
        for key in ("encoder", "quality"):
            if getattr(args, key) is not None:
                recipe["render"][key] = getattr(args, key)
    recipe = montage.save(series_dir, recipe)
    print(f"Montage : {montage.describe(recipe)}")
    return 0


EFFECT_ARGS = ("effects", "zoom", "temperature", "curve", "grain", "staccato", "staccato_every", "stretch", "pitch", "eq",
               "bed", "bed_level")  # fmt: skip


def _set_effects(recipe: dict, args) -> None:
    """The effects options of "montage set", over the recipe (validated when saved)."""
    if args.effects is not None:
        preset = montage.validate({} if args.effects else montage.EFFECTS_OFF)
        recipe.update({key: preset[key] for key in montage.EFFECTS_OFF})
    for arg in ("zoom", "grain", "stretch"):
        if getattr(args, arg) is not None:
            recipe[arg] = getattr(args, arg)
    for arg, group, key in (
        ("temperature", "grade", "temperature"), ("curve", "grade", "curve"), ("staccato", "staccato", "transition"),
        ("pitch", "audio", "pitch"), ("eq", "audio", "eq"), ("bed", "audio", "bed"), ("bed_level", "audio", "bed_level"),
    ):  # fmt: skip
        if getattr(args, arg) is not None:
            recipe[group][key] = getattr(args, arg)
    if args.staccato_every is not None:
        recipe["staccato"]["min"], recipe["staccato"]["max"] = args.staccato_every


def _band(text: str):
    if text.strip() == "auto":
        return "auto"
    m = _BAND_RE.match(text)
    if not m:
        raise InputError('--band attend "auto" ou deux pourcentages, ex. "74-84"')
    return [float(m.group(i).replace(",", ".")) / 100 for i in (1, 2)]


def cmd_montage_reset(args, log) -> int:
    series_dir = _series_dir(args)
    recipe = montage.load(series_dir)
    if recipe is None:
        print("Pas de montage à supprimer.")
    elif args.episode is not None:
        recipe["episodes"].pop(str(args.episode), None)
        print(f"Montage : {montage.describe(montage.save(series_dir, recipe))}")
    else:
        (series_dir / montage.RECIPE_FILE).unlink()
        print(f"Montage supprimé. Les épisodes déjà montés restent dans {montage.montage_dir(series_dir)}.")
    return 0


def cmd_montage_preview(args, log) -> int:
    if not 0 < args.seconds <= 30:
        raise InputError("--seconds : entre 1 et 30")
    series_dir = _series_dir(args)
    ffmpeg = film.find_ffmpeg(args.ffmpeg)
    print(montage.preview(series_dir, args.episode, args.at, args.seconds, ffmpeg, output=args.file, log=log))
    return 0


def cmd_montage_render(args, log) -> int:
    series_dir = _series_dir(args)
    recipe = montage.recipe_of(series_dir)
    only = {n for a, b in args.episodes for n in range(a, (b or 9999) + 1)} if args.episodes else None
    plan = film.plan_film(series_dir, True, only)
    ffmpeg = film.find_ffmpeg(args.ffmpeg)
    progress = _ProgressPrinter()
    try:
        report, _ = montage.render_series(series_dir, recipe, ffmpeg, plan.parts, log, progress, force=args.force)
    finally:
        progress.finish()
    log(f"Terminé : {len(report.rendered)} épisode(s) monté(s), {len(report.reused)} déjà à jour.")
    return 0


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
    if free:
        print(f"Gratuits     : {len(free)} sur le site officiel (épisodes {free[0]}-{free[-1]})")
    if series.languages:
        print(f"Langues      : {', '.join(series.languages)}")
    if series.introduction:
        print(f"\n{series.introduction}")
    if not preview.available:
        print(f"\nSource       : indisponible ({preview.source_error})")
    elif series.free_only:
        print("\nSource       : site officiel, épisodes gratuits seulement")
    else:
        offered = f" en {', '.join(preview.qualities)}" if preview.qualities else ""
        print(f"\nSource       : OK (dernier épisode dispo{offered})")
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
            chapters=not args.no_chapters, only=selected, replace=args.replace, with_montage=args.montage,
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
        with_montage=args.montage,
    )  # fmt: skip
    return 0


def _make_film(series_dir: Path, ffmpeg: str, log, with_montage: bool = False, **options) -> film.FilmResult:
    progress = _ProgressPrinter()
    try:
        if with_montage:
            if options.pop("reencode", False):
                raise InputError("--montage et --reencode ne vont pas ensemble : le montage ré-encode déjà chaque épisode")
            options.pop("replace", None)  # the montage film replaces our own film in any case
            return montage.make_montage_film(series_dir, ffmpeg, log, on_progress=progress, **options)
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
