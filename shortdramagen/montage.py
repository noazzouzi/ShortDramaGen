"""Montage: edit the downloaded episodes (mirror, trims, look, speed, cut or sped-up passages, and the
effects on by default: zoom, colour grading, grain, quick cuts, tempo, pitch, equaliser, background
sound), then join them.

The recipe of a series lives in ``<series>/montage.json``, outside the manifest (a running fetch
rewrites the whole manifest from memory and would drop it). Episode files are never modified: each
one is rendered by a single ffmpeg pass into ``<series>/montage/E017.mp4``. A key made of the output
profile, the recipe resolved for that episode and the source file identifies a rendered episode, so
editing episode 17 renders episode 17 again and nothing else. Every rendered episode of a series
shares one profile (size, frame rate, encoder), so the film joins them without re-encoding.

Times in the recipe are seconds of the source episode, as in a player.

Burned-in subtitles: the platforms burn white subtitles into the picture, which a mirror would
reverse. With ``keep_subtitles``, inside the subtitle band, the pixels of the original text (bright,
grey, next to a dark outline) are pasted back over the mirrored frame, whose own reversed text is
blurred away first. The masks are computed at half resolution: cheaper, and smoother edges.

Effects: the image is zoomed (cropped then scaled back), graded (chroma shift towards orange or
blue, luma curve) and grained; quick cuts mark every 1 to 2 s of output with a punch-in zoom, a
flash or a black frame (the story is kept whole); the tempo, the pitch and the equaliser change the
sound, and a quiet background (noise, wind, bass drone) is mixed under it. Each is off at its
neutral value (see EFFECTS_OFF). Measurements and choices: docs/06-montage.md.
"""

from __future__ import annotations

import hashlib
import json
import random
import re
import subprocess
import tempfile
import threading
from dataclasses import dataclass
from fractions import Fraction
from pathlib import Path
from typing import Callable

from . import errors, film, fsutil, mp4
from .film import FilmError

RECIPE_FILE = "montage.json"
MONTAGE_DIR = "montage"
INDEX_FILE = "index.json"
PREVIEW_FILE = ".apercu.mp4"
ENGINE = 1  # changes when the graphs change: every rendered episode is then made again

MAX_TRIM_S = 120.0
MIN_KEPT_S = 5.0
MIN_SEGMENT_S = 0.05
SPEED_RANGE = (0.5, 3.0)
LOOKS = {  # eq settings of each preset; explicit values override them
    "aucun": {},
    "vif": {"brightness": 0.02, "contrast": 1.06, "saturation": 1.25},
    "doux": {"brightness": 0.03, "contrast": 0.94, "saturation": 0.9},
    "nb": {"saturation": 0.0},
}
LOOK_LIMITS = {"brightness": (-0.3, 0.3), "contrast": (0.5, 2.0), "saturation": (0.0, 3.0)}
LOOK_NEUTRAL = {"brightness": 0.0, "contrast": 1.0, "saturation": 1.0}
ENCODERS = ("auto", "x264", "amf")
QUALITIES = ("standard", "compacte")
DEFAULT_BAND = (0.55, 0.85)  # of the height, when no subtitle is found to measure it

# Effects: limits, choices and filters. Tempo and zoom in %, pitch in semitones, levels in dBFS.
STRETCH_RANGE = (-10.0, 10.0)
ZOOM_RANGE = (0.0, 15.0)
TEMPERATURE_RANGE = (-100.0, 100.0)  # -: blue, +: orange; 100 moves U and V by 10 levels
GRAIN_RANGE = (0.0, 20.0)  # strength of ffmpeg's noise on the luma; above 5 the files grow fast
STACCATO_RANGE = (0.5, 10.0)  # length of a quick-cut segment, s of output
PITCH_RANGE = (-3.0, 3.0)
BED_LEVEL_RANGE = (-60.0, -20.0)
CURVES = {  # luma curves for lutyuv; x is the luma from 0 to 1
    "aucune": None,
    "douce": "0.045+0.91*{x}",  # lifted blacks, softer whites
    "contraste": "{x}-0.35/(2*PI)*sin(2*PI*{x})",  # S curve
}
TRANSITIONS = ("aucune", "zoom", "flash", "noir")
STACCATO_PUNCH = 0.08  # the "zoom" transition: every other segment is 8 % closer
FLASH_FRAMES = 2
EQS = {
    "aucun": None,
    "shelf": "bass=g=-8:f=120:t=q:w=0.7,treble=g=-8:f=7000:t=q:w=0.7",
    "notch": "equalizer=f=950:t=q:w=4:g=-18,equalizer=f=2900:t=q:w=4:g=-18",
}
BEDS = {  # source, and the gain that brings its RMS level to 0 dBFS (measured with astats)
    "aucun": None,
    "blanc": ("anoisesrc=r=44100:c=white:a=1:s=7", 4.8),
    "vent": ("anoisesrc=r=44100:c=brown:a=1:s=7,lowpass=f=500,tremolo=f=0.15:d=0.5", 17.1),
    "basse": ("aevalsrc=0.6*sin(2*PI*55*t)+0.4*sin(2*PI*82.5*t):s=44100,lowpass=f=200,tremolo=f=0.1:d=0.3", 7.2),
}
AUDIO_FORMAT = "aformat=sample_fmts=fltp:sample_rates=44100:channel_layouts=stereo"
GRAPH_INLINE_MAX = 16_000  # longer graphs go through a file (Windows limits a command line to 32 KiB)

DEFAULT = {
    "v": 1,
    "mirror": True,
    "keep_subtitles": True,
    "subtitle_band": "auto",
    "trim": {"start": 0, "end": 0},
    "speed": 1,
    "look": {"preset": "aucun"},
    "stretch": 3,
    "zoom": 4,
    "grade": {"temperature": 30, "curve": "douce"},
    "grain": 4,
    "staccato": {"transition": "zoom", "min": 1, "max": 2},
    "audio": {"pitch": 0.5, "eq": "shelf", "bed": "vent", "bed_level": -40},
    "render": {"encoder": "auto", "quality": "standard"},
    "episodes": {},
}
# Every effect at its neutral value (the mirror has its own switch): "sdg montage set --no-effects".
EFFECTS_OFF = {
    "stretch": 0,
    "zoom": 0,
    "grade": {"temperature": 0, "curve": "aucune"},
    "grain": 0,
    "staccato": {"transition": "aucune"},
    "audio": {"pitch": 0, "eq": "aucun", "bed": "aucun"},
}

Log = Callable[[str], None]
Progress = Callable[[float, float], None]


class RecipeError(FilmError):
    """An invalid recipe. ``field``: where, as a path ("episodes.17.ranges.0.speed")."""

    def __init__(self, field: str, message: str, code: str = errors.MONTAGE_INVALID):
        super().__init__(f"{field} : {message}" if field else message, code)
        self.field = field


# --- recipe ---------------------------------------------------------------------------------------


def _number(value, field: str, low: float, high: float) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise RecipeError(field, "nombre attendu")
    if not low <= value <= high:
        raise RecipeError(field, f"entre {low:g} et {high:g}")
    return float(value)


def _bool(value, field: str) -> bool:
    if not isinstance(value, bool):
        raise RecipeError(field, "true ou false attendu")
    return value


def _object(value, field: str, keys: set[str]) -> dict:
    if not isinstance(value, dict):
        raise RecipeError(field, "objet attendu")
    unknown = sorted(set(value) - keys)
    if unknown:
        raise RecipeError(f"{field}.{unknown[0]}" if field else unknown[0], "clé inconnue")
    return value


def _choice(value, field: str, options) -> str:
    if value not in options:
        raise RecipeError(field, f"parmi {', '.join(options)}")
    return value


def _trim(value, field: str) -> dict:
    data = _object(value, field, {"start", "end"})
    return {k: _number(data[k], f"{field}.{k}", 0, MAX_TRIM_S) for k in ("start", "end") if k in data}


def _ranges(value, field: str) -> list[dict]:
    if not isinstance(value, list):
        raise RecipeError(field, "liste attendue")
    out = []
    for i, item in enumerate(value):
        f = f"{field}.{i}"
        data = _object(item, f, {"from", "to", "speed", "cut"})
        if "from" not in data or "to" not in data:
            raise RecipeError(f, "« from » et « to » attendus (secondes de l'épisode)")
        start = _number(data["from"], f"{f}.from", 0, 36_000)
        end = _number(data["to"], f"{f}.to", 0, 36_000)
        if end <= start:
            raise RecipeError(f"{f}.to", "doit être après « from »")
        if data.get("cut") is not None and _bool(data["cut"], f"{f}.cut"):
            if "speed" in data:
                raise RecipeError(f, "un passage est coupé ou accéléré, pas les deux")
            out.append({"from": start, "to": end, "cut": True})
        elif "speed" in data:
            out.append({"from": start, "to": end, "speed": _number(data["speed"], f"{f}.speed", *SPEED_RANGE)})
        else:
            raise RecipeError(f, "« speed » ou « cut » attendu")
    out.sort(key=lambda r: r["from"])
    for i, (a, b) in enumerate(zip(out, out[1:])):
        if b["from"] < a["to"]:
            raise RecipeError(f"{field}.{i + 1}", "chevauche le passage précédent")
    return out


def validate(data) -> dict:
    """The recipe, complete and normalised. Raises RecipeError: unknown keys are refused."""
    data = _object(data, "", set(DEFAULT))
    if data.get("v", 1) != 1:
        raise RecipeError("v", "version de recette inconnue")
    recipe = json.loads(json.dumps(DEFAULT))
    for key in ("mirror", "keep_subtitles"):
        if key in data:
            recipe[key] = _bool(data[key], key)
    if "subtitle_band" in data:
        band = data["subtitle_band"]
        if band != "auto":
            if not (isinstance(band, list) and len(band) == 2):
                raise RecipeError("subtitle_band", "« auto » ou [haut, bas] en fractions de la hauteur attendu")
            top, bottom = (_number(x, f"subtitle_band.{i}", 0, 1) for i, x in enumerate(band))
            if bottom - top < 0.03:
                raise RecipeError("subtitle_band", "bande trop étroite")
            band = [top, bottom]
        recipe["subtitle_band"] = band
    if "trim" in data:
        recipe["trim"].update(_trim(data["trim"], "trim"))
    if "speed" in data:
        recipe["speed"] = _number(data["speed"], "speed", *SPEED_RANGE)
    if "look" in data:
        look = _object(data["look"], "look", {"preset", *LOOK_LIMITS})
        preset = look.get("preset", "aucun")
        if preset not in LOOKS:
            raise RecipeError("look.preset", f"parmi {', '.join(LOOKS)}")
        recipe["look"] = {"preset": preset}
        for k, (low, high) in LOOK_LIMITS.items():
            if k in look:
                recipe["look"][k] = _number(look[k], f"look.{k}", low, high)
    for key, limits in (("stretch", STRETCH_RANGE), ("zoom", ZOOM_RANGE), ("grain", GRAIN_RANGE)):
        if key in data:
            recipe[key] = _number(data[key], key, *limits)
    if "grade" in data:  # grade, staccato, audio: what is given replaces the default, key by key
        grade = _object(data["grade"], "grade", {"temperature", "curve"})
        if "temperature" in grade:
            recipe["grade"]["temperature"] = _number(grade["temperature"], "grade.temperature", *TEMPERATURE_RANGE)
        if "curve" in grade:
            recipe["grade"]["curve"] = _choice(grade["curve"], "grade.curve", CURVES)
    if "staccato" in data:
        staccato = _object(data["staccato"], "staccato", {"transition", "min", "max"})
        if "transition" in staccato:
            recipe["staccato"]["transition"] = _choice(staccato["transition"], "staccato.transition", TRANSITIONS)
        for k in ("min", "max"):
            if k in staccato:
                recipe["staccato"][k] = _number(staccato[k], f"staccato.{k}", *STACCATO_RANGE)
        if recipe["staccato"]["max"] < recipe["staccato"]["min"]:
            raise RecipeError("staccato.max", "doit être au moins égal à « min »")
    if "audio" in data:
        audio = _object(data["audio"], "audio", {"pitch", "eq", "bed", "bed_level"})
        if "pitch" in audio:
            recipe["audio"]["pitch"] = _number(audio["pitch"], "audio.pitch", *PITCH_RANGE)
        if "eq" in audio:
            recipe["audio"]["eq"] = _choice(audio["eq"], "audio.eq", EQS)
        if "bed" in audio:
            recipe["audio"]["bed"] = _choice(audio["bed"], "audio.bed", BEDS)
        if "bed_level" in audio:
            recipe["audio"]["bed_level"] = _number(audio["bed_level"], "audio.bed_level", *BED_LEVEL_RANGE)
    if "render" in data:
        render = _object(data["render"], "render", {"encoder", "quality"})
        if render.get("encoder", "auto") not in ENCODERS:
            raise RecipeError("render.encoder", f"parmi {', '.join(ENCODERS)}")
        if render.get("quality", "standard") not in QUALITIES:
            raise RecipeError("render.quality", f"parmi {', '.join(QUALITIES)}")
        recipe["render"].update(render)
    if "episodes" in data:
        if not isinstance(data["episodes"], dict):
            raise RecipeError("episodes", "objet attendu")
        for key, value in data["episodes"].items():
            if not (isinstance(key, str) and key.isdigit() and int(key) >= 1):
                raise RecipeError(f"episodes.{key}", "numéro d'épisode attendu")
            f = f"episodes.{int(key)}"
            ep = _object(value, f, {"trim", "ranges"})
            clean = {}
            if "trim" in ep:
                clean["trim"] = _trim(ep["trim"], f"{f}.trim")
            if "ranges" in ep:
                clean["ranges"] = _ranges(ep["ranges"], f"{f}.ranges")
            if clean:
                recipe["episodes"][str(int(key))] = clean
    return recipe


def load(series_dir: Path) -> dict | None:
    path = series_dir / RECIPE_FILE
    if not path.exists():
        return None
    try:
        data = json.loads(fsutil.read_text(path))
    except ValueError:
        raise RecipeError("", f"{path.name} illisible (JSON invalide)") from None
    return validate(data)


def recipe_of(series_dir: Path) -> dict:
    """montage.json, or the default montage (its effects on) when the series has none."""
    return load(series_dir) or validate({})


def save(series_dir: Path, recipe: dict) -> dict:
    recipe = validate(recipe)
    fsutil.write_text(series_dir / RECIPE_FILE, json.dumps(recipe, ensure_ascii=False, indent=2) + "\n")
    return recipe


def is_neutral(recipe: dict) -> bool:
    """Nothing to do: the montage would give the episodes back unchanged."""
    return (
        not recipe["mirror"] and not any(recipe["trim"].values()) and recipe["speed"] == 1
        and look_settings(recipe) == LOOK_NEUTRAL and not recipe["episodes"]
        and not image_effects(recipe) and not sound_effects(recipe) and not recipe["stretch"]
        and recipe["staccato"]["transition"] == "aucune"
    )  # fmt: skip


def look_settings(recipe: dict) -> dict:
    look = recipe["look"]
    return {**LOOK_NEUTRAL, **LOOKS[look["preset"]], **{k: look[k] for k in LOOK_LIMITS if k in look}}


def image_effects(recipe: dict) -> list[str]:
    """["zoom 4 %", "plus chaud (30)", "courbe douce", "grain 4"]: the effects on the picture."""
    out = []
    if recipe["zoom"]:
        out.append(f"zoom {_n(recipe['zoom'])} %")
    temperature = recipe["grade"]["temperature"]
    if temperature:
        out.append(f"{'plus chaud' if temperature > 0 else 'plus froid'} ({_n(abs(temperature))})")
    if recipe["grade"]["curve"] != "aucune":
        out.append(f"courbe {recipe['grade']['curve']}")
    if recipe["grain"]:
        out.append(f"grain {_n(recipe['grain'])}")
    return out


def sound_effects(recipe: dict) -> list[str]:
    """["+0,5 demi-ton", "égaliseur shelf", "fond vent à -40 dB"]: the effects on the sound (tempo aside)."""
    audio, out = recipe["audio"], []
    if audio["pitch"]:
        out.append(f"{'+' if audio['pitch'] > 0 else ''}{_n(audio['pitch'])} demi-ton")
    if audio["eq"] != "aucun":
        out.append(f"égaliseur {audio['eq']}")
    if audio["bed"] != "aucun":
        out.append(f"fond {audio['bed']} à {_n(audio['bed_level'])} dB")
    return out


def describe(recipe: dict) -> str:
    """"Miroir (sous-titres gardés) · coupe 5 s / 10 s · vif · ×1,25 · zoom 4 %, grain 4 · … · 2 épisodes retouchés"."""
    parts = []
    if recipe["mirror"]:
        parts.append("miroir" + (" (sous-titres gardés)" if recipe["keep_subtitles"] else ""))
    start, end = recipe["trim"]["start"], recipe["trim"]["end"]
    if start or end:
        parts.append(f"coupe {_s(start)} au début, {_s(end)} à la fin")
    if recipe["look"]["preset"] != "aucun" or any(k in recipe["look"] for k in LOOK_LIMITS):
        parts.append(f"look {recipe['look']['preset']}")
    if recipe["speed"] != 1:
        parts.append(f"vitesse ×{_n(recipe['speed'])}")
    if image_effects(recipe):
        parts.append(", ".join(image_effects(recipe)))
    staccato = recipe["staccato"]
    if staccato["transition"] != "aucune":
        lengths = _n(staccato["min"]) if staccato["min"] == staccato["max"] else f"{_n(staccato['min'])}-{_n(staccato['max'])}"
        parts.append(f"découpe rapide {lengths} s ({staccato['transition']})")
    if recipe["stretch"]:
        parts.append(f"tempo {'+' if recipe['stretch'] > 0 else ''}{_n(recipe['stretch'])} %")
    if sound_effects(recipe):
        parts.append("son " + ", ".join(sound_effects(recipe)))
    if recipe["episodes"]:
        parts.append(f"{len(recipe['episodes'])} épisode(s) retouché(s) à part")
    return " · ".join(parts) or "aucune retouche"


def _s(seconds: float) -> str:
    return f"{_n(seconds)} s"


def _n(value: float) -> str:
    return f"{value:g}".replace(".", ",")


# --- timeline -------------------------------------------------------------------------------------


@dataclass(frozen=True)
class Segment:
    start: float  # seconds of the source episode
    end: float
    speed: float = 1.0

    @property
    def out(self) -> float:
        return (self.end - self.start) / self.speed


def episode_trim(recipe: dict, number: int) -> dict:
    return {**recipe["trim"], **recipe["episodes"].get(str(number), {}).get("trim", {})}


def segments(recipe: dict, number: int, duration: float) -> list[Segment]:
    """What is kept of an episode, in order, each part with its speed (the tempo change included)."""
    tempo = 1 + recipe["stretch"] / 100
    trim = episode_trim(recipe, number)
    low, high = trim["start"], duration - trim["end"]
    if high - low < MIN_KEPT_S:
        raise RecipeError(
            f"episodes.{number}.trim", f"il resterait moins de {_s(MIN_KEPT_S)} de l'épisode {number} ({_s(round(duration, 1))})",
            errors.MONTAGE_EMPTY_EPISODE,
        )
    out, cursor = [], low
    for r in recipe["episodes"].get(str(number), {}).get("ranges", []):
        a, b = max(r["from"], low), min(r["to"], high)
        if b <= a:
            continue  # outside what the trims keep
        if a > cursor:
            out.append(Segment(cursor, a, recipe["speed"] * tempo))
        if not r.get("cut"):
            out.append(Segment(a, b, r["speed"] * tempo))
        cursor = max(cursor, b)
    if high > cursor:
        out.append(Segment(cursor, high, recipe["speed"] * tempo))
    merged: list[Segment] = []
    for seg in out:
        if seg.end - seg.start < MIN_SEGMENT_S:
            continue
        if merged and merged[-1].speed == seg.speed and abs(merged[-1].end - seg.start) < 1e-9:
            merged[-1] = Segment(merged[-1].start, seg.end, seg.speed)
        else:
            merged.append(seg)
    if sum(s.out for s in merged) < MIN_KEPT_S:
        raise RecipeError(f"episodes.{number}.ranges", f"il resterait moins de {_s(MIN_KEPT_S)} de l'épisode {number}",
                          errors.MONTAGE_EMPTY_EPISODE)  # fmt: skip
    return merged


def clip(segs: list[Segment], low: float, high: float) -> list[Segment]:
    """The part of a timeline inside [low, high] (source seconds), for a preview."""
    out = []
    for s in segs:
        a, b = max(s.start, low), min(s.end, high)
        if b - a >= MIN_SEGMENT_S:
            out.append(Segment(a, b, s.speed))
    return out


def out_time(segs: list[Segment], t: float) -> float:
    """Where source second ``t`` lands in the edited episode (seconds of output)."""
    total = 0.0
    for s in segs:
        if t <= s.start:
            break
        total += (min(t, s.end) - s.start) / s.speed
    return total


Intervals = list[tuple[float, float]]  # seconds of output, where a quick-cut transition shows


def staccato_intervals(recipe: dict, number: int, length: float, fps: str) -> Intervals:
    """The quick cuts of an episode of ``length`` s of output: segments of min to max seconds,
    drawn from a generator seeded with the episode number (the same cuts at every render).
    "zoom": every other segment; "flash", "noir": the first frames of each segment but the first."""
    st = recipe["staccato"]
    if st["transition"] == "aucune":
        return []
    rng = random.Random(number)
    cuts, t = [], 0.0
    while True:
        t += rng.uniform(st["min"], st["max"])
        if t > length - st["min"] / 2:  # no tiny segment at the end
            break
        cuts.append(round(t, 3))
    if st["transition"] == "zoom":
        bounds = [*cuts, round(length, 3)]
        return [(bounds[i], bounds[i + 1]) for i in range(0, len(bounds) - 1, 2)]
    frames = round(FLASH_FRAMES / float(Fraction(fps)) - 0.001, 3)  # just short of the next frame
    return [(c, round(c + frames, 3)) for c in cuts]


def shift(intervals: Intervals, offset: float, length: float) -> Intervals:
    """Intervals seen from a window of the episode starting at ``offset`` s of output (a preview)."""
    out = []
    for a, b in intervals:
        a, b = max(a - offset, 0.0), min(b - offset, length)
        if b > a:
            out.append((round(a, 3), round(b, 3)))
    return out


# --- ffmpeg graph ---------------------------------------------------------------------------------


@dataclass(frozen=True)
class Profile:
    """What every rendered episode of a series shares, so that the film is a plain copy."""

    width: int
    height: int
    fps: str
    encoder: str  # "x264" or "amf"
    quality: str
    ffmpeg: int  # major version: another ffmpeg may encode differently

    def as_dict(self) -> dict:
        return dict(self.__dict__)


def band_pixels(band: tuple[float, float], height: int) -> tuple[int, int]:
    """Band rows, on multiples of 4 (the masks are computed at 1/2, the blur at 1/4)."""
    top = int(band[0] * height) // 4 * 4
    bottom = min(height, -(-int(band[1] * height) // 4) * 4)
    return top, bottom


def _atempo(speed: float) -> str:
    """atempo takes 0.5-2 per filter in older ffmpeg: chain them."""
    factors = []
    while speed > 2.0 + 1e-9:
        factors.append(2.0)
        speed /= 2.0
    while speed < 0.5 - 1e-9:
        factors.append(0.5)
        speed /= 0.5
    factors.append(speed)
    return ",".join(f"atempo={f:.6g}" for f in factors)


def _keep_subtitles(width: int, top: int, bottom: int) -> list[str]:
    """[vn] -> [vm]: mirrored frame, original subtitles pasted back (see the module docstring)."""
    h = bottom - top
    w2, h2, w4, h4 = width // 2, h // 2, width // 4, h // 4
    blur = max(1, min(5, min(w4, h4) // 4 - 1))  # boxblur refuses a radius over half the (chroma) plane
    dil = lambda n: ",".join(["dilation"] * n)  # noqa: E731
    return [
        "[vn]split=3[k_o1][k_o2][k_o3]",
        f"[k_o1]crop={width}:{h}:0:{top},scale={w2}:{h2},format=yuv444p,extractplanes=y+u+v[k_y][k_u][k_v]",
        "[k_y]split[k_y1][k_y2]",
        "[k_y1]lut=y='if(gt(val,200),255,0)'[k_b]",
        f"[k_y2]lut=y='if(lt(val,90),255,0)',{dil(3)}[k_d]",
        "[k_u]lut=y='if(lt(abs(val-128),14),255,0)'[k_cu]",
        "[k_v]lut=y='if(lt(abs(val-128),14),255,0)'[k_cv]",
        "[k_b][k_d]blend=all_mode=multiply[k_bd]",
        "[k_bd][k_cu]blend=all_mode=multiply[k_bdu]",
        f"[k_bdu][k_cv]blend=all_mode=multiply,{dil(2)},split[k_mh][k_mmh]",
        f"[k_mh]scale={width}:{h}:flags=bilinear[k_m]",
        f"[k_mmh]hflip,dilation,scale={width}:{h}:flags=bilinear[k_mm]",
        "[k_o2]hflip,split[k_f][k_f2]",
        f"[k_f2]crop={width}:{h}:0:{top},scale={w4}:{h4},boxblur={blur}:2,scale={width}:{h}:flags=bilinear[k_fb]",
        "[k_fb][k_mm]alphamerge[k_fba]",
        f"[k_f][k_fba]overlay=0:{top}:format=yuv420[k_base]",
        f"[k_o3]crop={width}:{h}:0:{top}[k_ob]",
        "[k_ob][k_m]alphamerge[k_txt]",
        f"[k_base][k_txt]overlay=0:{top}:format=yuv420[vm]",
    ]


def episode_graph(
    segs: list[Segment],
    profile: Profile,
    recipe: dict,
    has_audio: bool,
    band: tuple[float, float] | None,
    staccato: Intervals = (),
) -> str:
    """The filter graph of one episode. ``segs`` are relative to the input seek point (0 = first kept frame),
    ``staccato`` (see staccato_intervals) to the first frame of output.

    Parts are cut on the common clock (PTS - start), never with STARTPTS: ShortMax's video starts
    0.16 s after its audio, resetting each stream would shift the sound.
    """
    lines = []
    n = len(segs)
    sound = "[am]" if sound_effects(recipe) else "[a]"
    if n == 1 and segs[0].start < 1e-6:
        s = segs[0]
        video = "[0:v]" + (f"setpts=PTS/{s.speed:.6g}," if s.speed != 1 else "")
        audio = f"[0:a]{_atempo(s.speed)}," if s.speed != 1 else "[0:a]"
        if has_audio:
            lines.append(f"{audio}aformat=sample_rates=44100:channel_layouts=stereo{sound}")
    else:
        lines.append(f"[0:v]split={n}" + "".join(f"[s{i}]" for i in range(n)))
        if has_audio:
            lines.append(f"[0:a]asplit={n}" + "".join(f"[t{i}]" for i in range(n)))
        for i, s in enumerate(segs):
            speed = f"/{s.speed:.6g}" if s.speed != 1 else ""
            lines.append(f"[s{i}]trim={s.start:.3f}:{s.end:.3f},setpts=(PTS-{s.start:.3f}/TB){speed}[v{i}]")
            if has_audio:
                tempo = f",{_atempo(s.speed)}" if s.speed != 1 else ""
                lines.append(f"[t{i}]atrim={s.start:.3f}:{s.end:.3f},asetpts=PTS-{s.start:.3f}/TB{tempo}[a{i}]")
        if has_audio:
            lines.append("".join(f"[v{i}][a{i}]" for i in range(n)) + f"concat=n={n}:v=1:a=1[vc][ac]")
            lines.append(f"[ac]aformat=sample_rates=44100:channel_layouts=stereo{sound}")
        else:
            lines.append("".join(f"[v{i}]" for i in range(n)) + f"concat=n={n}:v=1:a=0[vc]")
        video = "[vc]"
    if not has_audio:  # a silent episode still needs a sound track to join the others
        lines.append(f"anullsrc=r=44100:cl=stereo,atrim=duration={sum(s.out for s in segs):.3f}{sound}")
    if sound != "[a]":
        lines += _sound_effects(recipe["audio"])

    w, h = profile.width, profile.height
    lines.append(
        f"{video}fps={profile.fps},scale={w}:{h}:force_original_aspect_ratio=decrease,"
        f"pad={w}:{h}:(ow-iw)/2:(oh-ih)/2,setsar=1[vn]"
    )
    last = "[vn]"
    if recipe["mirror"]:
        if recipe["keep_subtitles"] and band:
            lines += _keep_subtitles(w, *band_pixels(band, h))
        else:
            lines.append("[vn]hflip[vm]")
        last = "[vm]"
    zoom = 1 + recipe["zoom"] / 100
    transition = recipe["staccato"]["transition"] if staccato else "aucune"
    if transition == "zoom":  # a closer copy of the frame laid over it, every other segment
        lines.append(f"{last}split[z_a][z_b]")
        lines.append(f"[z_a]{_zoom(w, h, zoom) or 'null'}[z_base]")
        lines.append(f"[z_b]{_zoom(w, h, zoom * (1 + STACCATO_PUNCH))}[z_close]")
        lines.append(f"[z_base][z_close]overlay=0:0:enable='{_during(staccato)}'[vz]")
        last = "[vz]"
    elif zoom != 1:
        lines.append(f"{last}{_zoom(w, h, zoom)}[vz]")
        last = "[vz]"
    look = look_settings(recipe)
    tail = []
    if look != LOOK_NEUTRAL:
        tail.append(f"eq=brightness={look['brightness']:g}:contrast={look['contrast']:g}:saturation={look['saturation']:g}")
    grade = _grade(recipe["grade"])
    if grade:
        tail.append(grade)
    if recipe["grain"]:  # temporal noise on the luma only: film grain, not coloured specks
        tail.append(f"noise=c0s={recipe['grain']:g}:c0f=t")
    if transition == "flash":
        tail.append(f"lutyuv=y='min(val+90,235)':enable='{_during(staccato)}'")
    elif transition == "noir":
        tail.append(f"drawbox=x=0:y=0:w=iw:h=ih:color=black:t=fill:enable='{_during(staccato)}'")
    tail.append("format=yuv420p")  # always last: after RGB-ish work, x264 would pick 4:4:4, unreadable in browsers
    lines.append(f"{last}{','.join(tail)}[v]")
    return ";\n".join(lines)


def _zoom(width: int, height: int, factor: float) -> str:
    """The centre of the frame, ``factor`` times closer, at the same size ("" for no zoom)."""
    if factor <= 1:
        return ""
    cw, ch = int(width / factor) // 2 * 2, int(height / factor) // 2 * 2
    return f"crop={cw}:{ch}:{(width - cw) // 2}:{(height - ch) // 2},scale={width}:{height}"


def _during(intervals: Intervals) -> str:
    """A timeline expression true inside the intervals (a lone 0 when there are none)."""
    return "+".join(f"between(t,{a:.3f},{b:.3f})" for a, b in intervals) or "0"


def _grade(grade: dict) -> str:
    """Temperature as a chroma shift (U down and V up: orange), curve on the luma: one lutyuv, cheap."""
    parts = []
    curve = CURVES[grade["curve"]]
    if curve:
        parts.append(f"y='16+219*({curve.format(x='clip((val-16)/219,0,1)')})'")
    shift = round(grade["temperature"] / 10, 1)
    if shift:
        parts.append(f"u='clip(val{-shift:+g},16,240)'")
        parts.append(f"v='clip(val{shift:+g},16,240)'")
    return f"lutyuv={':'.join(parts)}" if parts else ""


def _sound_effects(audio: dict) -> list[str]:
    """[am] -> [a]: pitch, equaliser, then the background mixed under the sound."""
    chain = []
    if audio["pitch"]:
        # played faster (higher), then slowed back to its length without changing the pitch
        rate = round(44100 * 2 ** (audio["pitch"] / 12))
        chain += [f"asetrate={rate}", "aresample=44100", _atempo(44100 / rate)]
    if EQS[audio["eq"]]:
        chain.append(EQS[audio["eq"]])
    if not BEDS[audio["bed"]]:
        return [f"[am]{','.join(chain)}[a]"]
    source, gain = BEDS[audio["bed"]]
    chain.append(AUDIO_FORMAT)  # amerge wants the same sample format on both sides
    return [
        f"[am]{','.join(chain)}[a_main]",
        f"{source},volume={audio['bed_level'] + gain:.1f}dB,{AUDIO_FORMAT}[a_bed]",
        "[a_main][a_bed]amerge=inputs=2,pan=stereo|c0=c0+c2|c1=c1+c3[a]",  # ends with the sound: the bed never does
    ]


def encoder_args(profile: Profile) -> list[str]:
    if profile.encoder == "amf":
        # AMF left to itself writes 20 Mb/s: the rate is set, scaled to the picture size
        kbps = {"standard": 2500, "compacte": 1800}[profile.quality] * profile.width * profile.height / (1080 * 1920)
        return ["-c:v", "h264_amf", "-quality", "balanced", "-rc", "vbr_peak", "-b:v", f"{int(kbps)}k",
                "-maxrate", f"{int(kbps * 1.6)}k"]  # fmt: skip
    return ["-c:v", "libx264", "-preset", "veryfast", "-crf", {"standard": "23", "compacte": "26"}[profile.quality]]


def render_args(
    ffmpeg: str, source: Path, low: float, high: float, graph: str, profile: Profile, output: Path,
    script: Path | None = None,
) -> list[str]:
    """Seeking before -i with a re-encode cuts at the exact frame and skips decoding the trimmed start.
    ``script``: the file that holds the graph, when it is too long for a command line."""
    graph_args = film.filter_script_args(ffmpeg, script) if script else ["-filter_complex", graph.replace("\n", "")]
    return [
        ffmpeg, "-hide_banner", "-nostdin", "-y", "-loglevel", "error", "-progress", "pipe:1", "-nostats",
        "-ss", f"{low:.3f}", "-to", f"{high:.3f}", "-i", str(source.resolve()),
        *graph_args, "-map", "[v]", "-map", "[a]",
        "-map_metadata", "-1", "-map_chapters", "-1",
        *encoder_args(profile), "-c:a", "aac", "-b:a", "128k", "-ar", "44100", "-ac", "2",
        "-movflags", "+faststart", "-f", "mp4", str(output),
    ]  # fmt: skip


# --- machine: encoders, frame rate, subtitle band -------------------------------------------------

_AMF: dict[str, bool] = {}


def amf_available(ffmpeg: str) -> bool:
    """AMD's hardware encoder works here (3 frames encoded: 0.2 s). NVENC and QSV are listed by
    ffmpeg builds even without the hardware, so only what really encodes counts."""
    if ffmpeg not in _AMF:
        try:
            proc = subprocess.run(
                [ffmpeg, "-hide_banner", "-v", "error", "-f", "lavfi", "-i", "color=s=1080x1920", "-frames:v", "3",
                 "-c:v", "h264_amf", "-f", "null", "-"],
                capture_output=True, timeout=30, creationflags=film.NO_WINDOW,
            )  # fmt: skip
            _AMF[ffmpeg] = proc.returncode == 0
        except (OSError, subprocess.TimeoutExpired):
            _AMF[ffmpeg] = False
    return _AMF[ffmpeg]


def resolve_encoder(ffmpeg: str, wanted: str) -> str:
    if wanted == "auto":
        return "amf" if amf_available(ffmpeg) else "x264"
    if wanted == "amf" and not amf_available(ffmpeg):
        raise FilmError(
            "L'encodeur AMD (AMF) ne fonctionne pas sur cette machine : choisis « auto » ou « x264 ».",
            errors.MONTAGE_ENCODER_UNAVAILABLE,
        )
    return wanted


def frame_rate(ffmpeg: str, path: Path) -> str:
    """"25", "30", "30000/1001"… as ffmpeg reads the video stream; 25 if unknown."""
    try:
        text = subprocess.run(
            [ffmpeg, "-hide_banner", "-i", str(path)], capture_output=True, text=True, encoding="utf-8",
            errors="replace", timeout=30, creationflags=film.NO_WINDOW,
        ).stderr  # fmt: skip
    except (OSError, subprocess.TimeoutExpired):
        return "25"
    m = re.search(r"Video:.*?(\d+(?:\.\d+)?) fps", text)
    if not m:
        return "25"
    rate = m.group(1)
    ntsc = {"29.97": "30000/1001", "23.98": "24000/1001", "59.94": "60000/1001"}
    return ntsc.get(rate) or (rate.rstrip("0").rstrip(".") if "." in rate else rate)


def _mask_graph(width: int, height: int) -> str:
    """The text mask of a whole frame at half resolution, for measuring the band."""
    return (
        f"[0:v]scale={width // 2}:{height // 2},format=yuv444p,extractplanes=y+u+v[y][u][v];[y]split[y1][y2];"
        "[y1]lut=y='if(gt(val,200),255,0)'[b];[y2]lut=y='if(lt(val,90),255,0)',dilation,dilation,dilation[d];"
        "[u]lut=y='if(lt(abs(val-128),14),255,0)'[cu];[v]lut=y='if(lt(abs(val-128),14),255,0)'[cv];"
        "[b][d]blend=all_mode=multiply[bd];[bd][cu]blend=all_mode=multiply[bdu];"
        "[bdu][cv]blend=all_mode=multiply,format=gray[m]"
    )


def band_from_rows(rows: list[int], height: int) -> tuple[float, float] | None:
    """The subtitle band from the count of text pixels per row (half-resolution rows).

    Subtitles are one or two lines in the same place for the whole series: the densest block
    of rows between 30 % and 95 % of the height, with gaps of up to 3 % (between two lines).
    """
    n = len(rows)
    if not n:
        return None
    low, high = int(n * 0.30), int(n * 0.95)
    peak = max(rows[low:high], default=0)
    if peak < 50:  # nothing like text here
        return None
    hot = [y for y in range(low, high) if rows[y] >= peak * 0.15]
    blocks: list[list[int]] = []
    for y in hot:
        if blocks and y - blocks[-1][-1] <= max(2, int(n * 0.03)):
            blocks[-1].append(y)
        else:
            blocks.append([y])
    best = max(blocks, key=lambda b: sum(rows[y] for y in range(b[0], b[-1] + 1)))
    pad = n * 0.02
    return max(0.0, (best[0] - pad) / n), min(1.0, (best[-1] + 1 + pad) / n)


def detect_band(ffmpeg: str, sources: list[Path], width: int, height: int) -> tuple[float, float] | None:
    """Where the burned-in subtitles are: text pixels counted per row on 18 frames of 3 episodes."""
    w2, h2 = width // 2, height // 2
    rows = [0] * h2
    picks = [sources[i * (len(sources) - 1) // 2] for i in range(3)] if len(sources) >= 3 else sources
    for source in dict.fromkeys(picks):
        info = mp4.probe(source)
        duration = info.presentation if info else 0
        for fraction in (0.12, 0.26, 0.4, 0.54, 0.68, 0.82):
            try:
                raw = subprocess.run(
                    [ffmpeg, "-v", "error", "-ss", f"{duration * fraction:.2f}", "-i", str(source), "-frames:v", "1",
                     "-filter_complex", _mask_graph(width, height), "-map", "[m]", "-f", "rawvideo", "-pix_fmt", "gray", "-"],
                    capture_output=True, timeout=60, creationflags=film.NO_WINDOW,
                ).stdout  # fmt: skip
            except (OSError, subprocess.TimeoutExpired):
                continue
            if len(raw) != w2 * h2:
                continue
            for y in range(h2):
                row = raw[y * w2 : (y + 1) * w2]
                rows[y] += w2 - row.count(0)
    return band_from_rows(rows, h2)


# --- rendering ------------------------------------------------------------------------------------


@dataclass
class RenderReport:
    profile: Profile
    band: tuple[float, float] | None
    rendered: list[int]
    reused: list[int]
    output_s: float  # length of the edited episodes


def montage_dir(series_dir: Path) -> Path:
    return series_dir / MONTAGE_DIR


def _index(series_dir: Path) -> dict:
    path = montage_dir(series_dir) / INDEX_FILE
    try:
        data = json.loads(fsutil.read_text(path)) if path.exists() else {}
    except ValueError:
        data = {}
    return data if isinstance(data, dict) else {}


def _save_index(series_dir: Path, index: dict) -> None:
    fsutil.write_text(montage_dir(series_dir) / INDEX_FILE, json.dumps(index, ensure_ascii=False, indent=1) + "\n")


def status(series_dir: Path) -> dict:
    """What is on disk, without ffmpeg: rendered episodes, their size, the measured subtitle band."""
    index = _index(series_dir)
    out_dir = montage_dir(series_dir)
    rendered = {int(n): e for n, e in (index.get("episodes") or {}).items() if (out_dir / f"E{int(n):03d}.mp4").exists()}
    band = index.get("band")
    return {
        "rendered": len(rendered),
        "episodes": sorted(rendered),
        "bytes": sum(e.get("bytes", 0) for e in rendered.values()),
        "band": tuple(band) if band else None,
    }


def episode_key(
    profile: Profile, recipe: dict, number: int, segs: list[Segment], band, source: Path, staccato: Intervals = ()
) -> str:
    stat = source.stat()
    data = {
        "engine": ENGINE, "profile": profile.as_dict(), "segments": [[s.start, s.end, s.speed] for s in segs],
        "mirror": recipe["mirror"], "keep": recipe["keep_subtitles"] and recipe["mirror"], "band": band,
        "look": look_settings(recipe), "source": [stat.st_size, stat.st_mtime_ns],
        "effects": {k: recipe[k] for k in ("zoom", "grade", "grain", "audio")},
        "staccato": [recipe["staccato"]["transition"], [list(i) for i in staccato]],
    }  # fmt: skip
    return hashlib.sha256(json.dumps(data, sort_keys=True).encode()).hexdigest()[:20]


def film_edit(recipe: dict, keys: dict[int, str]) -> dict:
    """What the manifest's film record keeps of a montage: a fingerprint of every rendered episode."""
    fp = hashlib.sha256(json.dumps(sorted(keys.items())).encode()).hexdigest()[:20]
    return {"fp": fp, "summary": describe(recipe)}


def prepare(series_dir: Path, recipe: dict, ffmpeg: str, parts: list[film.Part], log: Log = print) -> tuple[Profile, tuple | None]:
    """The profile of this series' montage, and its subtitle band (measured once, then kept)."""
    main = film.FilmPlan(series_dir, "", 0, parts).main_format()
    index = _index(series_dir)
    fps = index.get("fps") or frame_rate(ffmpeg, parts[0].path)
    encoder = resolve_encoder(ffmpeg, recipe["render"]["encoder"])
    profile = Profile(main.video.width, main.video.height, fps, encoder, recipe["render"]["quality"], film.ffmpeg_major(ffmpeg))
    band = None
    if recipe["mirror"] and recipe["keep_subtitles"]:
        if recipe["subtitle_band"] != "auto":
            band = tuple(recipe["subtitle_band"])
        elif "band" in index:
            band = tuple(index["band"]) if index["band"] else None
        else:
            log("Recherche de la zone des sous-titres…")
            band = detect_band(ffmpeg, [p.path for p in parts], profile.width, profile.height)
            index["band"] = list(band) if band else None
            log(f"Sous-titres entre {band[0]:.0%} et {band[1]:.0%} de la hauteur" if band
                else "Aucun sous-titre incrusté repéré : miroir simple")  # fmt: skip
    index["fps"] = fps
    montage_dir(series_dir).mkdir(exist_ok=True)
    _save_index(series_dir, index)
    return profile, band


def render_series(
    series_dir: Path,
    recipe: dict,
    ffmpeg: str,
    parts: list[film.Part],
    log: Log = print,
    on_progress: Progress | None = None,
    stop: threading.Event | None = None,
    force: bool = False,
) -> tuple[RenderReport, dict[int, str]]:
    """Render the episodes whose key changed. Returns the report and the key of every episode."""
    profile, band = prepare(series_dir, recipe, ffmpeg, parts, log)
    out_dir = montage_dir(series_dir)
    index = _index(series_dir)
    done = index.setdefault("episodes", {})
    plans, keys, output_s = [], {}, 0.0
    for part in parts:
        segs = segments(recipe, part.number, part.info.presentation)
        length = sum(s.out for s in segs)
        output_s += length
        cuts = staccato_intervals(recipe, part.number, length, profile.fps)
        key = episode_key(profile, recipe, part.number, segs, band, part.path, cuts)
        keys[part.number] = key
        target = out_dir / f"E{part.number:03d}.mp4"
        entry = done.get(str(part.number)) or {}
        fresh = entry.get("key") == key and target.exists() and target.stat().st_size == entry.get("bytes")
        if force or not fresh:
            plans.append((part, segs, cuts, key, target))
    total = sum(sum(s.out for s in segs) for _, segs, *_ in plans)
    todo = {part.number for part, *_ in plans}
    report = RenderReport(profile, band, [], [p.number for p in parts if p.number not in todo], output_s)
    if plans:
        log(f"Montage de {len(plans)} épisode(s) ({profile.encoder}, {film.format_duration(total)} de vidéo), "
            f"{len(report.reused)} déjà prêt(s)")  # fmt: skip
    offset = 0.0
    for part, segs, cuts, key, target in plans:
        length = sum(s.out for s in segs)
        progress = (lambda t, _total, base=offset: on_progress(base + t, total)) if on_progress else None
        size = render_episode(ffmpeg, part, segs, profile, recipe, band, target, progress, stop, staccato=cuts)
        done[str(part.number)] = {"key": key, "out_s": round(length, 3), "bytes": size}
        _save_index(series_dir, {**_index(series_dir), "episodes": done})
        report.rendered.append(part.number)
        offset += length
    return report, keys


def render_episode(
    ffmpeg: str,
    part: film.Part,
    segs: list[Segment],
    profile: Profile,
    recipe: dict,
    band,
    target: Path,
    on_progress: Progress | None = None,
    stop: threading.Event | None = None,
    low_priority: bool = True,
    staccato: Intervals = (),
) -> int:
    """One episode through ffmpeg, checked (length, format), then put in place. Returns its size."""
    low, high = segs[0].start, segs[-1].end
    relative = [Segment(s.start - low, s.end - low, s.speed) for s in segs]
    graph = episode_graph(relative, profile, recipe, part.info.audio is not None, band, staccato)
    tmp = target.with_name(f".rendu-{target.stem}.mp4")
    expected = sum(s.out for s in segs)
    try:
        with tempfile.TemporaryDirectory(prefix="sdg-montage-") as work:
            script = None
            if len(graph) > GRAPH_INLINE_MAX:  # many quick cuts in a long episode
                script = Path(work) / "graphe.txt"
                script.write_text(graph.replace("\n", ""), encoding="utf-8")
            args = render_args(ffmpeg, part.path, low, high, graph, profile, tmp, script)
            film._run_ffmpeg(args, expected, Path(work) / "ffmpeg.log", on_progress, stop, low_priority)
        duration = mp4.duration_seconds(tmp) if tmp.exists() else None
        tolerance = 0.15 + 0.04 * len(segs)
        if duration is None or abs(duration - expected) > tolerance:
            raise FilmError(
                f"Épisode {part.number} monté de travers : {duration or 0:.2f} s au lieu de {expected:.2f} s",
                errors.MONTAGE_DURATION,
            )
        fsutil.replace(tmp, target)
    finally:
        tmp.unlink(missing_ok=True)
    return target.stat().st_size


def make_montage_film(
    series_dir: Path,
    ffmpeg: str,
    log: Log = print,
    output: Path | None = None,
    allow_missing: bool = False,
    chapters: bool = True,
    only: set[int] | None = None,
    stop: threading.Event | None = None,
    on_progress: Progress | None = None,
    recipe: dict | None = None,
    on_phase: Callable[[str], None] | None = None,
) -> film.FilmResult:
    """Render what changed, then join the edited episodes without re-encoding.

    The film takes the name of the plain one and replaces it (see film.make_film).
    ``recipe``: the one frozen when a job was created, else montage.json, else the default montage.
    ``on_phase``: told "rendering", then "merging".
    """
    recipe = recipe or recipe_of(series_dir)
    source = film.plan_film(series_dir, allow_missing, only)
    if source.missing:
        log(f"Attention : épisodes absents, film incomplet (manquent : {film.format_ranges(source.missing)})")
    if on_phase:
        on_phase("rendering")
    report, keys = render_series(series_dir, recipe, ffmpeg, source.parts, log, on_progress, stop)
    if on_phase:
        on_phase("merging")
    plan = film.plan_film(series_dir, True, {p.number for p in source.parts}, montage_dir(series_dir))
    if not plan.compatible:  # another ffmpeg or driver in between: make them all again
        raise FilmError(
            "Les épisodes montés n'ont pas tous le même format (ffmpeg ou pilote changé ?). "
            "Refais-les tous : sdg montage render <série> --force",
            errors.MONTAGE_FORMAT_MISMATCH,
        )
    output = output or film.default_output(source)
    return film.make_film(
        series_dir, ffmpeg, log, output=output, allow_missing=True, chapters=chapters,
        only={p.number for p in source.parts}, stop=stop, on_progress=on_progress, episodes_dir=montage_dir(series_dir),
        edit=film_edit(recipe, keys),
    )  # fmt: skip


def preview(
    series_dir: Path, number: int, at: float, seconds: float, ffmpeg: str, recipe: dict | None = None,
    output: Path | None = None, log: Log = print,
) -> Path:
    """A few seconds of one episode as the montage will render it, from ``at`` (source seconds)."""
    recipe = recipe or recipe_of(series_dir)
    plan = film.plan_film(series_dir, True, {number})
    if not plan.parts:
        raise FilmError(f"Épisode {number} absent ou illisible", errors.FILM_MISSING_EPISODES)
    part = plan.parts[0]
    source_plan = film.plan_film(series_dir, True)
    profile, band = prepare(series_dir, recipe, ffmpeg, source_plan.parts, log)
    full = segments(recipe, number, part.info.presentation)
    window = clip(full, at, at + seconds)
    if not window:
        raise FilmError(f"Rien à montrer entre {_s(at)} et {_s(at + seconds)} : ce passage est coupé.", errors.MONTAGE_INVALID)
    cuts = staccato_intervals(recipe, number, sum(s.out for s in full), profile.fps)  # as in the whole episode
    cuts = shift(cuts, out_time(full, window[0].start), sum(s.out for s in window))
    output = output or montage_dir(series_dir) / PREVIEW_FILE
    render_episode(ffmpeg, part, window, profile, recipe, band, output, low_priority=False, staccato=cuts)
    return output
