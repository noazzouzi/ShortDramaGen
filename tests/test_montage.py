"""Montage: recipe, timeline, ffmpeg graphs, cache of edited episodes, montage film, CLI (offline),
plus a few checks with a real ffmpeg (skipped without it)."""

import http.client
import io
import json
import math
import os
import struct
import subprocess
import tempfile
import unittest
from contextlib import redirect_stdout
from pathlib import Path
from unittest import mock

from fakes import audio_track, make_mp4, video_track
import test_jobs
from test_jobs import KEY

from shortdramagen import cli, errors, film, montage, mp4
from shortdramagen.montage import EFFECTS_OFF, RecipeError, Segment

PLAIN = {**EFFECTS_OFF, "mirror": False}  # the montage before the effects: only what a test sets

AVCC = bytes.fromhex("01640032ffe1")
ASC = bytes.fromhex("2b920800")


def episode(seconds: float) -> bytes:
    tracks = (video_track(1080, 1920, AVCC, seconds), audio_track(ASC, 128_000, seconds))
    return make_mp4(seconds, tracks=tracks)


def fake_ffmpeg(calls: list):
    """Stands for film._run_ffmpeg: writes an MP4 of the expected length where ffmpeg would write."""

    def run(args, total, log_path, on_progress, stop=None, low_priority=False):
        if "concat" in args:  # keep the list: its temporary folder is gone afterwards
            args = [*args, Path(args[args.index("-i") + 1]).read_text(encoding="utf-8")]
            calls.append(args)
            args = args[:-1]
        else:
            calls.append(args)
        Path(args[-1]).write_bytes(episode(total))
        if on_progress:
            on_progress(total, total)

    return run


class RecipeTest(unittest.TestCase):
    def test_defaults_and_normalisation(self):
        recipe = montage.validate({})
        self.assertEqual(recipe, montage.DEFAULT)
        self.assertFalse(montage.is_neutral(recipe))  # mirror and effects on by default
        self.assertEqual(montage.describe(recipe), (
            "miroir (sous-titres gardés) · zoom 4 %, plus chaud (30), courbe douce, grain 4 · découpe rapide 1-2 s (zoom)"
            " · tempo +3 % · son +0,5 demi-ton, égaliseur shelf, fond vent à -40 dB"))
        self.assertTrue(montage.is_neutral(montage.validate(PLAIN)))
        self.assertEqual(montage.describe(montage.validate(PLAIN)), "aucune retouche")
        recipe = montage.validate({**PLAIN, "mirror": True, "trim": {"end": 10}, "look": {"preset": "vif", "saturation": 1.5},
                                   "episodes": {"017": {"ranges": [{"from": 80, "to": 92, "cut": True}, {"from": 40, "to": 55, "speed": 1.5}]}}})  # fmt: skip
        self.assertEqual(recipe["trim"], {"start": 0, "end": 10.0})
        self.assertEqual([r["from"] for r in recipe["episodes"]["17"]["ranges"]], [40, 80])  # sorted, key normalised
        self.assertEqual(montage.look_settings(recipe), {"brightness": 0.02, "contrast": 1.06, "saturation": 1.5})
        self.assertEqual(montage.describe(recipe), "miroir (sous-titres gardés) · coupe 0 s au début, 10 s à la fin · look vif · 1 épisode(s) retouché(s) à part")

    def test_refusals_name_the_field(self):
        cases = {
            "mirro": {"mirro": True},
            "mirror": {"mirror": 1},
            "trim.start": {"trim": {"start": 500}},
            "speed": {"speed": 0.1},
            "look.preset": {"look": {"preset": "sepia"}},
            "render.encoder": {"render": {"encoder": "nvenc"}},
            "subtitle_band": {"subtitle_band": [0.5, 0.51]},
            "episodes.x": {"episodes": {"x": {}}},
            "episodes.3.ranges.1": {"episodes": {"3": {"ranges": [{"from": 1, "to": 5, "speed": 2}, {"from": 4, "to": 9, "cut": True}]}}},
            "episodes.3.ranges.0": {"episodes": {"3": {"ranges": [{"from": 1, "to": 5, "speed": 2, "cut": True}]}}},
            "episodes.3.ranges.0.to": {"episodes": {"3": {"ranges": [{"from": 5, "to": 1, "speed": 2}]}}},
            "zoom": {"zoom": 20},
            "stretch": {"stretch": "3"},
            "grain": {"grain": -1},
            "grade.temperature": {"grade": {"temperature": 150}},
            "grade.curve": {"grade": {"curve": "sepia"}},
            "grade.hue": {"grade": {"hue": 3}},
            "staccato.transition": {"staccato": {"transition": "fondu"}},
            "staccato.min": {"staccato": {"min": 0.1}},
            "staccato.max": {"staccato": {"min": 3, "max": 2}},
            "audio.pitch": {"audio": {"pitch": 5}},
            "audio.eq": {"audio": {"eq": "loudness"}},
            "audio.bed": {"audio": {"bed": "pluie"}},
            "audio.bed_level": {"audio": {"bed_level": -10}},
        }  # fmt: skip
        for field, data in cases.items():
            with self.subTest(field=field), self.assertRaises(RecipeError) as ctx:
                montage.validate(data)
            self.assertEqual((ctx.exception.field, ctx.exception.code), (field, errors.MONTAGE_INVALID))

    def test_effects_merge_key_by_key(self):
        recipe = montage.validate({"audio": {"bed": "aucun"}, "staccato": {"max": 3}, "grade": {"temperature": -40}})
        self.assertEqual(recipe["audio"], {"pitch": 0.5, "eq": "shelf", "bed": "aucun", "bed_level": -40})
        self.assertEqual(recipe["staccato"], {"transition": "zoom", "min": 1, "max": 3})
        self.assertEqual(recipe["grade"], {"temperature": -40, "curve": "douce"})
        self.assertIn("plus froid (40)", montage.describe(recipe))
        self.assertNotIn("fond", montage.describe(recipe))

    def test_save_and_load(self):
        with tempfile.TemporaryDirectory() as tmp:
            d = Path(tmp)
            self.assertIsNone(montage.load(d))
            montage.save(d, {"mirror": True})
            self.assertTrue(montage.load(d)["mirror"])
            (d / montage.RECIPE_FILE).write_text("{abîmé", encoding="utf-8")
            with self.assertRaises(RecipeError):
                montage.load(d)


class TimelineTest(unittest.TestCase):
    def recipe(self, **data):
        return montage.validate({**PLAIN, **data})

    def test_trims_ranges_and_cuts(self):
        r = self.recipe(trim={"start": 5, "end": 10}, speed=1.25, episodes={"2": {"ranges": [
            {"from": 0, "to": 8, "speed": 2},  # partly in the trimmed start
            {"from": 40, "to": 55, "speed": 1.5}, {"from": 80, "to": 92, "cut": True}, {"from": 135, "to": 139, "speed": 2},  # the last one is trimmed away
        ]}})  # fmt: skip
        segs = montage.segments(r, 2, 140)
        self.assertEqual(segs, [Segment(5, 8, 2), Segment(8, 40, 1.25), Segment(40, 55, 1.5), Segment(55, 80, 1.25), Segment(92, 130, 1.25)])
        self.assertAlmostEqual(sum(s.out for s in segs), 1.5 + 25.6 + 10 + 20 + 30.4)
        self.assertEqual(montage.segments(r, 1, 140), [Segment(5, 130, 1.25)])  # other episodes: global settings only
        self.assertEqual(montage.clip(segs, 50, 60), [Segment(50, 55, 1.5), Segment(55, 60, 1.25)])

    def test_episode_trim_overrides_the_series(self):
        r = self.recipe(trim={"start": 5, "end": 10}, episodes={"3": {"trim": {"start": 12.5}}})
        self.assertEqual(montage.segments(r, 3, 100), [Segment(12.5, 90)])

    def test_tempo_applies_to_every_part(self):
        r = self.recipe(stretch=3, speed=1.25, episodes={"1": {"ranges": [{"from": 10, "to": 20, "speed": 2}]}})
        segs = montage.segments(r, 1, 30)
        self.assertEqual([s.speed for s in segs], [1.25 * 1.03, 2 * 1.03, 1.25 * 1.03])
        self.assertAlmostEqual(montage.out_time(segs, 15), 10 / 1.2875 + 5 / 2.06)
        self.assertAlmostEqual(montage.out_time(segs, 30), sum(s.out for s in segs))

    def test_staccato_intervals(self):
        r = self.recipe(staccato={"transition": "zoom", "min": 1, "max": 2})
        zoom = montage.staccato_intervals(r, 7, 60, "25")
        self.assertEqual(zoom, montage.staccato_intervals(r, 7, 60, "25"))  # the same cuts at every render
        self.assertNotEqual(zoom, montage.staccato_intervals(r, 8, 60, "25"))
        self.assertTrue(all(0.998 <= b - a <= 2.002 or b == 60 for a, b in zoom))
        self.assertTrue(all(b1 < a2 for (_, b1), (a2, _) in zip(zoom, zoom[1:])))  # every other segment
        self.assertTrue(1 <= zoom[0][0] <= 2)
        r = self.recipe(staccato={"transition": "flash", "min": 1, "max": 2})
        flash = montage.staccato_intervals(r, 7, 60, "25")
        self.assertEqual([round(b - a, 3) for a, b in flash], [0.079] * len(flash))  # 2 frames at 25 i/s
        self.assertEqual([a for a, _ in flash[::2]], [a for a, _ in zoom])  # same cuts, other look
        self.assertLess(flash[-1][0], 60 - 0.5)
        self.assertEqual(montage.staccato_intervals(self.recipe(), 7, 60, "25"), [])
        self.assertEqual(montage.shift([(1, 2), (4, 6), (7, 8), (9, 10)], 5, 4), [(0, 1), (2, 3)])  # seen from 5 s, for 4 s

    def test_nothing_left(self):
        r = self.recipe(trim={"start": 60, "end": 60})
        with self.assertRaises(RecipeError) as ctx:
            montage.segments(r, 1, 122)
        self.assertEqual((ctx.exception.code, ctx.exception.field), (errors.MONTAGE_EMPTY_EPISODE, "episodes.1.trim"))


class GraphTest(unittest.TestCase):
    PROFILE = montage.Profile(1080, 1920, "25", "x264", "standard", 9)

    def graph(self, segs, band=None, has_audio=True, cuts=(), **recipe):
        return montage.episode_graph(segs, self.PROFILE, montage.validate({**PLAIN, **recipe}), has_audio, band, cuts)

    def test_plain_episode_has_no_split(self):
        g = self.graph([Segment(0, 100)])
        self.assertNotIn("split", g)
        self.assertIn("[0:a]aformat=sample_rates=44100:channel_layouts=stereo[a]", g)
        self.assertTrue(g.endswith("[vn]format=yuv420p[v]"))

    def test_speed_and_parts(self):
        g = self.graph([Segment(0, 100, 1.25)])
        self.assertIn("setpts=PTS/1.25", g)
        self.assertIn("atempo=1.25", g)
        g = self.graph([Segment(0, 35), Segment(35, 50, 1.5), Segment(62, 100)])
        self.assertIn("[s1]trim=35.000:50.000,setpts=(PTS-35.000/TB)/1.5[v1]", g)
        self.assertIn("[t1]atrim=35.000:50.000,asetpts=PTS-35.000/TB,atempo=1.5[a1]", g)
        self.assertIn("concat=n=3:v=1:a=1[vc][ac]", g)
        self.assertNotIn("STARTPTS", g)  # ShortMax's video starts 0.16 s after its audio
        self.assertEqual(montage._atempo(3), "atempo=2,atempo=1.5")

    def test_mirror_look_and_subtitles(self):
        g = self.graph([Segment(0, 100)], mirror=True, keep_subtitles=False, look={"preset": "nb"})
        self.assertIn("[vn]hflip[vm]", g)
        self.assertTrue(g.endswith("[vm]eq=brightness=0:contrast=1:saturation=0,format=yuv420p[v]"))
        g = self.graph([Segment(0, 100)], band=(0.735, 0.837), mirror=True)
        top, bottom = montage.band_pixels((0.735, 0.837), 1920)
        self.assertEqual((top % 4, bottom % 4, top, bottom), (0, 0, 1408, 1608))
        self.assertIn(f"[k_o1]crop=1080:{bottom - top}:0:{top},scale=540:{(bottom - top) // 2}", g)
        self.assertIn(f"[k_base][k_txt]overlay=0:{top}:format=yuv420[vm]", g)
        self.assertIn("[vm]format=yuv420p[v]", g)
        self.assertNotIn("hflip[vm]", g)  # the text pasted back is never mirrored

    def test_silent_episode_gets_silence(self):
        g = self.graph([Segment(0, 30), Segment(40, 50, 2)], has_audio=False)
        self.assertIn("concat=n=2:v=1:a=0[vc]", g)
        self.assertIn("anullsrc=r=44100:cl=stereo,atrim=duration=35.000[a]", g)

    def test_image_effects(self):
        g = self.graph([Segment(0, 100)], zoom=4, grade={"temperature": 30, "curve": "douce"}, grain=4)
        self.assertIn("[vn]crop=1038:1846:21:37,scale=1080:1920[vz]", g)  # 4 % closer, even sizes, centred
        self.assertTrue(g.endswith(
            "[vz]lutyuv=y='16+219*(0.045+0.91*clip((val-16)/219,0,1))':u='clip(val-3,16,240)':v='clip(val+3,16,240)',"
            "noise=c0s=4:c0f=t,format=yuv420p[v]"))  # fmt: skip
        g = self.graph([Segment(0, 100)], grade={"temperature": -40})
        self.assertIn(":u='clip(val+4,16,240)':v='clip(val-4,16,240)'", g)  # towards blue (the default curve kept)
        g = self.graph([Segment(0, 100)], mirror=True, keep_subtitles=False, zoom=5)
        self.assertLess(g.index("hflip[vm]"), g.index("[vm]crop="))  # zoomed after the mirror (and the subtitles)

    def test_staccato(self):
        cuts = [(1.2, 2.5), (4, 5.5)]
        g = self.graph([Segment(0, 100)], cuts=cuts, zoom=4, staccato={"transition": "zoom"})
        self.assertIn("[vn]split[z_a][z_b]", g)
        self.assertIn("[z_a]crop=1038:1846:21:37,scale=1080:1920[z_base]", g)
        self.assertIn("[z_b]crop=960:1708:60:106,scale=1080:1920[z_close]", g)  # 4 % then 8 % closer
        self.assertIn("[z_base][z_close]overlay=0:0:enable='between(t,1.200,2.500)+between(t,4.000,5.500)'[vz]", g)
        g = self.graph([Segment(0, 100)], cuts=cuts, staccato={"transition": "zoom"})
        self.assertIn("[z_a]null[z_base]", g)
        g = self.graph([Segment(0, 100)], cuts=cuts, staccato={"transition": "flash"})
        self.assertTrue(g.endswith("[vn]lutyuv=y='min(val+90,235)':enable='between(t,1.200,2.500)+between(t,4.000,5.500)',format=yuv420p[v]"))
        g = self.graph([Segment(0, 100)], cuts=cuts, staccato={"transition": "noir"})
        self.assertIn("drawbox=x=0:y=0:w=iw:h=ih:color=black:t=fill:enable='between(t,1.200,2.500)", g)
        self.assertTrue(self.graph([Segment(0, 100)], staccato={"transition": "flash"}).endswith("[vn]format=yuv420p[v]"))  # no cuts

    def test_sound_effects(self):
        g = self.graph([Segment(0, 100, 1.03)], audio={"pitch": 0.5, "eq": "shelf", "bed": "vent", "bed_level": -40})
        self.assertIn("[0:a]atempo=1.03,aformat=sample_rates=44100:channel_layouts=stereo[am]", g)
        self.assertIn("[am]asetrate=45392,aresample=44100,atempo=0.971537,bass=g=-8:f=120:t=q:w=0.7,treble=g=-8:f=7000:t=q:w=0.7,"
                      f"{montage.AUDIO_FORMAT}[a_main]", g)  # fmt: skip
        self.assertIn(f"anoisesrc=r=44100:c=brown:a=1:s=7,lowpass=f=500,tremolo=f=0.15:d=0.5,volume=-22.9dB,{montage.AUDIO_FORMAT}[a_bed]", g)
        self.assertIn("[a_main][a_bed]amerge=inputs=2,pan=stereo|c0=c0+c2|c1=c1+c3[a]", g)
        g = self.graph([Segment(0, 100)], audio={"pitch": -1, "eq": "notch", "bed": "aucun"})
        self.assertIn("[am]asetrate=41625,aresample=44100,atempo=1.05946,equalizer=f=950", g)
        self.assertTrue(g.split(";\n")[1].endswith("g=-18[a]"))
        g = self.graph([Segment(0, 30), Segment(40, 50, 2)], has_audio=False, audio={"bed": "blanc"})
        self.assertIn("anullsrc=r=44100:cl=stereo,atrim=duration=35.000[am]", g)  # a silent episode gets the bed too

    def test_render_args_seek_before_input(self):
        args = montage.render_args("ffmpeg", Path("E001.mp4"), 5, 130, "g", self.PROFILE, Path("out.mp4"))
        self.assertLess(args.index("-ss"), args.index("-i"))
        self.assertEqual(args[args.index("-ss") + 1 : args.index("-to") + 2], ["5.000", "-to", "130.000"])
        with mock.patch.object(film, "ffmpeg_major", return_value=9):
            args = montage.render_args("ffmpeg", Path("E001.mp4"), 5, 130, "g", self.PROFILE, Path("out.mp4"), Path("graphe.txt"))
        self.assertEqual(args[args.index("-/filter_complex") + 1], "graphe.txt")  # a long graph goes through a file
        self.assertNotIn("-filter_complex", args)
        amf = montage.encoder_args(montage.Profile(720, 1280, "25", "amf", "standard", 9))
        self.assertEqual(amf[amf.index("-b:v") + 1], "1111k")  # 2500k for 1080x1920, scaled to the picture

    def test_band_from_rows(self):
        rows = [0] * 960
        for y in list(range(706, 724)) + list(range(740, 758)):  # two lines of subtitles
            rows[y] = 400
        rows[100] = 900  # something bright near the top: outside the searched zone
        top, bottom = montage.band_from_rows(rows, 960)
        self.assertAlmostEqual(top, (706 - 19.2) / 960)
        self.assertAlmostEqual(bottom, (758 + 19.2) / 960)
        self.assertIsNone(montage.band_from_rows([0] * 960, 960))


class RenderTest(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.dir = Path(tmp.name) / "goodshort-31000835255-serie"
        self.dir.mkdir()
        for n, seconds in ((1, 60.0), (2, 70.0), (3, 80.0)):
            (self.dir / f"E{n:03d}.mp4").write_bytes(episode(seconds))
        manifest = {"title": "Série", "episodes": [{"number": n} for n in (1, 2, 3)]}
        (self.dir / "manifest.json").write_text(json.dumps(manifest), encoding="utf-8")
        self.calls = []
        patches = [
            mock.patch.object(film, "_run_ffmpeg", fake_ffmpeg(self.calls)),
            mock.patch.object(film, "ffmpeg_major", return_value=9),
            mock.patch.object(montage, "frame_rate", return_value="25"),
            mock.patch.object(montage, "amf_available", return_value=False),
            mock.patch.object(montage, "detect_band", return_value=(0.74, 0.84)),
        ]
        for p in patches:
            p.start()
            self.addCleanup(p.stop)

    def render(self, recipe):
        parts = film.plan_film(self.dir).parts
        report, _ = montage.render_series(self.dir, montage.validate(recipe), "ffmpeg", parts, log=lambda _: None)
        return report

    def test_only_what_changed_is_rendered_again(self):
        recipe = {**PLAIN, "mirror": True, "trim": {"start": 3}}
        first = self.render(recipe)
        self.assertEqual((first.rendered, first.reused, first.band, first.profile.encoder), ([1, 2, 3], [], (0.74, 0.84), "x264"))
        self.assertAlmostEqual(first.output_s, 60 + 70 + 80 - 9)
        self.assertEqual(self.render(recipe).rendered, [])
        recipe["episodes"] = {"2": {"ranges": [{"from": 10, "to": 20, "speed": 2}]}}
        self.assertEqual(self.render(recipe).rendered, [2])
        os.utime(self.dir / "E003.mp4", (2_000_000_000, 2_000_000_000))  # the source changed (re-downloaded)
        self.assertEqual(self.render(recipe).rendered, [3])
        recipe["look"] = {"preset": "vif"}
        self.assertEqual(self.render(recipe).rendered, [1, 2, 3])
        recipe["audio"] = {"bed": "blanc"}  # an effect: every episode again
        self.assertEqual(self.render(recipe).rendered, [1, 2, 3])
        self.assertEqual(self.render(recipe).rendered, [])
        self.assertEqual(montage.status(self.dir)["episodes"], [1, 2, 3])
        self.assertEqual(sorted(p.name for p in (self.dir / "montage").iterdir()), ["E001.mp4", "E002.mp4", "E003.mp4", "index.json"])
        self.assertEqual(sorted(p.name for p in self.dir.glob("E*")), ["E001.mp4", "E002.mp4", "E003.mp4"])  # sources untouched

    def test_default_effects(self):
        report = self.render({"trim": {"start": 3}})
        self.assertAlmostEqual(report.output_s, (60 + 70 + 80 - 9) / 1.03)  # tempo +3 %
        renders = [a for a in self.calls if "-filter_complex" in a]
        self.assertEqual(len(renders), 3)
        graph = renders[0][renders[0].index("-filter_complex") + 1]
        for part in ("hflip", "crop=", "[z_close]", "lutyuv", "noise=", "asetrate", "bass=", "anoisesrc"):
            self.assertIn(part, graph)
        self.assertNotEqual(graph.split("enable=")[1][:60], renders[1][renders[1].index("-filter_complex") + 1].split("enable=")[1][:60])  # own cuts

    def test_montage_film_replaces_the_plain_film(self):
        montage.save(self.dir, {**PLAIN, "mirror": True, "trim": {"start": 2, "end": 1}})
        plain = film.make_film(self.dir, "ffmpeg", log=lambda _: None)
        self.assertEqual(plain.path.name, "Série.mp4")
        result = montage.make_montage_film(self.dir, "ffmpeg", log=lambda _: None)
        self.assertEqual((result.path, result.mode, result.reused), (plain.path, "copy", False))
        record = json.loads((self.dir / "manifest.json").read_text(encoding="utf-8"))["film"]
        self.assertEqual(record["edit"]["summary"], "miroir (sous-titres gardés) · coupe 2 s au début, 1 s à la fin")
        self.assertEqual([round(end - start) for _, start, end in record["chapter_times"]], [57, 67, 77])
        concat_list = [a for a in self.calls if "concat" in a][-1][-1]
        self.assertIn(str(self.dir / "montage" / "E001.mp4"), concat_list)  # the film joins the edited episodes
        again = montage.make_montage_film(self.dir, "ffmpeg", log=lambda _: None)
        self.assertTrue(again.reused)
        with self.assertRaises(film.FilmError) as ctx:  # the plain film no longer replaces a montage silently
            film.make_film(self.dir, "ffmpeg", log=lambda _: None)
        self.assertEqual(ctx.exception.code, errors.FILM_EXISTS)

    def test_no_recipe_means_the_default_montage(self):
        montage.make_montage_film(self.dir, "ffmpeg", log=lambda _: None)
        record = json.loads((self.dir / "manifest.json").read_text(encoding="utf-8"))["film"]
        self.assertEqual(record["edit"]["summary"], montage.describe(montage.DEFAULT))
        self.assertIsNone(montage.load(self.dir))  # nothing saved


class CliTest(RenderTest):
    def run_cli(self, *argv):
        out = io.StringIO()
        with redirect_stdout(out):
            code = cli.main(list(argv))
        return code, out.getvalue()

    def test_set_show_reset(self):
        d = str(self.dir)
        self.assertEqual(self.run_cli("montage", "set", d, "--mirror", "--trim-start", "0:05", "--look", "vif")[0], 0)
        code, out = self.run_cli("montage", "set", d, "-e", "2", "--range", "0:40-0:55x1.5", "--cut", "1:20-1:32")
        self.assertEqual(code, 0)
        recipe = montage.load(self.dir)
        self.assertEqual((recipe["mirror"], recipe["trim"]["start"], recipe["look"]["preset"]), (True, 5, "vif"))
        self.assertEqual(recipe["episodes"]["2"]["ranges"], [{"from": 40, "to": 55, "speed": 1.5}, {"from": 80, "to": 92, "cut": True}])
        code, out = self.run_cli("montage", "show", d)
        self.assertIn("Épisode 2 : 40-55 ×1.5, 1:20-1:32 coupé", out)
        self.assertEqual(self.run_cli("montage", "set", d, "-e", "2", "--mirror")[0], 2)  # series-wide option with -e
        self.assertEqual(self.run_cli("montage", "set", d, "--speed", "9")[0], 1)
        self.run_cli("montage", "reset", d, "-e", "2")
        self.assertEqual(montage.load(self.dir)["episodes"], {})
        self.run_cli("montage", "reset", d)
        self.assertIsNone(montage.load(self.dir))

    def test_effects_options(self):
        d = str(self.dir)
        code, out = self.run_cli("montage", "show", d)
        self.assertIn("le montage par défaut s'appliquera", out)
        self.assertEqual(self.run_cli("montage", "set", d, "--no-effects", "--grain", "2", "--staccato", "flash", "--staccato-every", "1,5-3")[0], 0)
        recipe = montage.load(self.dir)
        self.assertEqual((recipe["zoom"], recipe["grain"], recipe["audio"]["bed"]), (0, 2, "aucun"))
        self.assertEqual(recipe["staccato"], {"transition": "flash", "min": 1.5, "max": 3})
        self.run_cli("montage", "set", d, "--effects", "--pitch", "-1", "--bed", "basse", "--bed-level", "-45", "--temperature", "-20",
                     "--curve", "contraste", "--eq", "notch", "--stretch", "-2", "--zoom", "5")  # fmt: skip
        recipe = montage.load(self.dir)
        self.assertEqual((recipe["grain"], recipe["zoom"], recipe["stretch"], recipe["staccato"]["transition"]), (4, 5, -2, "zoom"))
        self.assertEqual(recipe["audio"], {"pitch": -1, "eq": "notch", "bed": "basse", "bed_level": -45})
        self.assertEqual(recipe["grade"], {"temperature": -20, "curve": "contraste"})
        self.assertEqual(self.run_cli("montage", "set", d, "-e", "2", "--zoom", "3")[0], 2)  # series-wide option with -e
        self.assertEqual(self.run_cli("montage", "set", d, "--zoom", "30")[0], 1)

    def test_film_with_montage(self):
        d = str(self.dir)
        self.run_cli("montage", "set", d, "--mirror", "--no-effects")
        self.assertEqual(self.run_cli("film", d, "--montage")[0], 0)
        self.assertEqual(json.loads((self.dir / "manifest.json").read_text(encoding="utf-8"))["film"]["edit"]["summary"], "miroir (sous-titres gardés)")
        self.assertEqual(self.run_cli("film", d, "--montage", "--reencode")[0], 2)


class ApiTest(test_jobs.LiveTest):
    """sdg ui: the montage card's routes and the film job with a montage (ffmpeg faked)."""

    make_http = test_jobs.FilmJobTest.make_http  # episodes with real tracks

    def fake_montage_film(self, calls):
        def make(series_dir, ffmpeg, log=print, recipe=None, on_phase=None, **options):
            on_phase("rendering")
            on_phase("merging")
            calls.append({"recipe": recipe, **options})
            path = series_dir / "One Night to Forever.mp4"
            path.write_bytes(b"film")
            return film.FilmResult(path, 12.5, 4, "copy", 3)

        return mock.patch.object(montage, "make_montage_film", side_effect=make)

    def test_recipe_routes_and_film(self):
        self.wait_job(self.fetch_job(), "done")
        url = f"/api/series/{KEY}/montage"
        status, data = self.call("GET", url)
        self.assertEqual((status, data["recipe"], data["looks"]), (200, None, ["aucun", "vif", "doux", "nb"]))
        self.assertEqual((data["default_summary"], data["effects_off"]["grain"]), (montage.describe(montage.DEFAULT), 0))
        status, data = self.call("PUT", url, {"mirror": True, "speed": 9})
        self.assertEqual((status, data["error"]["code"], data["error"]["details"]["field"]), (422, "invalid_input", "speed"))
        status, data = self.call("PUT", url, {"mirror": True, "trim": {"start": 3}, **montage.EFFECTS_OFF})
        self.assertEqual((status, data["summary"]), (200, "miroir (sous-titres gardés) · coupe 3 s au début, 0 s à la fin"))
        self.assertTrue((self.root / KEY / montage.RECIPE_FILE).exists())

        self.assertEqual(self.call("POST", f"/api/series/{KEY}/film", {"montage": True, "reencode": True})[0], 422)
        calls = []
        with self.fake_montage_film(calls):
            status, data = self.call("POST", f"/api/series/{KEY}/film", {"montage": True})
            self.assertEqual(status, 201, data)
            self.call("PUT", url, {"mirror": False})  # edited meanwhile: the job keeps its own recipe
            job = self.wait_job(data["job"]["id"], "done")
        self.assertEqual((job["result"]["file"], calls[0]["recipe"]["mirror"], calls[0]["recipe"]["trim"]["start"]), ("One Night to Forever.mp4", True, 3))

        self.assertIsNone(self.call("DELETE", url)[1]["recipe"])
        with self.fake_montage_film(calls):  # no recipe saved: the default montage, effects on
            status, data = self.call("POST", f"/api/series/{KEY}/film", {"montage": True})
            self.assertEqual(status, 201, data)
            self.wait_job(data["job"]["id"], "done")
        self.assertEqual(calls[1]["recipe"], montage.DEFAULT)

    def test_preview(self):
        self.wait_job(self.fetch_job(), "done")

        def fake_preview(series_dir, number, at, seconds, ffmpeg, log=print, **_):
            path = series_dir / montage.MONTAGE_DIR / montage.PREVIEW_FILE
            path.parent.mkdir(exist_ok=True)
            path.write_bytes(episode(seconds))
            return path

        with mock.patch.object(montage, "preview", side_effect=fake_preview):
            status, data = self.call("POST", f"/api/series/{KEY}/montage/preview", {"episode": 2, "at": 10, "seconds": 8})
        self.assertEqual(status, 200, data)
        self.assertTrue(data["media_url"].startswith(f"/media/series/{KEY}/montage/preview?v="))
        status, _ = self.call("POST", f"/api/series/{KEY}/montage/preview", {"seconds": 60})
        self.assertEqual(status, 422)
        conn = http.client.HTTPConnection("127.0.0.1", self.port, timeout=5)
        conn.request("GET", data["media_url"], headers={"Host": f"127.0.0.1:{self.port}"})
        resp = conn.getresponse()
        self.assertEqual((resp.status, resp.getheader("Content-Type")), (200, "video/mp4"))
        resp.read()
        conn.close()


def _ffmpeg_or_none():
    try:
        return film.find_ffmpeg()
    except film.FilmError:
        return None


FFMPEG = _ffmpeg_or_none()


@unittest.skipUnless(FFMPEG, "ffmpeg absent (pip install imageio-ffmpeg pour ces tests)")
class RealFfmpegTest(unittest.TestCase):
    """A 216x384 clip: a red square at the top left, white "letters" with a black outline at the
    bottom left (like burned-in subtitles), a beep every second."""

    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.dir = Path(tmp.name) / "flickreels-1-test"
        self.dir.mkdir()
        letters = ",".join(f"drawbox=x={20 + 12 * i}:y=282:w=4:h=20:color=white:t=fill" for i in range(5))
        subprocess.run([
            FFMPEG, "-v", "error", "-y",
            "-f", "lavfi", "-i", "color=c=0x404040:s=216x384:r=25:d=12",
            "-f", "lavfi", "-i", "sine=frequency=880:duration=12:beep_factor=4",
            "-vf", f"drawbox=x=10:y=20:w=40:h=40:color=red:t=fill,drawbox=x=12:y=276:w=66:h=32:color=black:t=fill,{letters}",
            "-c:v", "libx264", "-preset", "ultrafast", "-pix_fmt", "yuv420p", "-c:a", "aac", "-shortest",
            str(self.dir / "E001.mp4"),
        ], check=True)  # fmt: skip
        (self.dir / "manifest.json").write_text(json.dumps({"title": "Test", "episodes": [{"number": 1}]}), encoding="utf-8")

    def gray(self, path: Path, at: float) -> bytes:
        return subprocess.run(
            [FFMPEG, "-v", "error", "-ss", str(at), "-i", str(path), "-frames:v", "1", "-f", "rawvideo", "-pix_fmt", "gray", "-"],
            capture_output=True, check=True,
        ).stdout  # fmt: skip

    def test_mirror_keeps_the_subtitles_readable(self):
        band = montage.detect_band(FFMPEG, [self.dir / "E001.mp4"], 216, 384)
        self.assertLessEqual(band[0], 282 / 384)
        self.assertGreaterEqual(band[1], 302 / 384)
        montage.save(self.dir, {**PLAIN, "mirror": True, "trim": {"start": 1, "end": 1}, "render": {"encoder": "x264"},
                                "episodes": {"1": {"ranges": [{"from": 4, "to": 6, "speed": 2}, {"from": 8, "to": 9, "cut": True}]}}})  # fmt: skip
        result = montage.make_montage_film(self.dir, FFMPEG, log=lambda _: None)
        self.assertAlmostEqual(mp4.duration_seconds(result.path), 3 + 1 + 2 + 2, delta=0.2)
        frame = self.gray(result.path, 0.5)
        row = lambda y: frame[y * 216 : (y + 1) * 216]  # noqa: E731
        red, letters = row(40), row(292)
        self.assertGreater(max(red[170:206]), max(red[10:46]))  # the square moved to the right: mirrored
        self.assertGreater(max(letters[20:70]), 200)  # the letters stayed on the left, readable
        self.assertLess(max(letters[146:196]), 150)  # and their mirrored copy is gone

    def rgb(self, path: Path, at: float, width: int = 216) -> bytes:
        return subprocess.run(
            [FFMPEG, "-v", "error", "-ss", str(at), "-i", str(path), "-frames:v", "1", "-f", "rawvideo", "-pix_fmt", "rgb24", "-"],
            capture_output=True, check=True,
        ).stdout  # fmt: skip

    def strength(self, samples: list[int], freq: float) -> float:
        """How much of ``freq`` (Hz) is in mono 44.1 kHz samples: one DFT bin."""
        re_ = sum(x * math.cos(2 * math.pi * freq * i / 44100) for i, x in enumerate(samples))
        im = sum(x * math.sin(2 * math.pi * freq * i / 44100) for i, x in enumerate(samples))
        return math.hypot(re_, im)

    def test_default_effects(self):
        """Mirror, zoom, quick cuts, grade, grain, tempo +3 %, pitch +0.5 semitone, EQ, bed: one pass, right length."""
        result = montage.make_montage_film(self.dir, FFMPEG, log=lambda _: None)
        self.assertAlmostEqual(mp4.duration_seconds(result.path), 12 / 1.03, delta=0.2)
        recipe = montage.DEFAULT
        cuts = montage.staccato_intervals(recipe, 1, 12 / 1.03, "25")
        normal, close = cuts[0][0] / 2, (cuts[0][0] + cuts[0][1]) / 2
        red = lambda frame, y: [frame[(y * 216 + x) * 3] for x in range(150, 216)]  # noqa: E731  (R of the right side)
        a, b = self.rgb(result.path, normal), self.rgb(result.path, close)
        self.assertGreater(max(red(a, 50)), 180)  # the red square, mirrored to the right, still on row 50
        self.assertLess(max(red(b, 50)), 140)  # 8 % closer: its bottom edge went above row 50
        raw = subprocess.run(
            [FFMPEG, "-v", "error", "-ss", "2.3", "-t", "0.2", "-i", str(result.path), "-f", "s16le", "-ac", "1", "-ar", "44100", "-"],
            capture_output=True, check=True,
        ).stdout  # fmt: skip
        samples = list(struct.unpack(f"<{len(raw) // 2}h", raw))
        self.assertGreater(self.strength(samples, 880 * 2 ** (0.5 / 12)), 3 * self.strength(samples, 880))  # higher by half a tone
