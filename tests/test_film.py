import json
import subprocess
import tempfile
import unittest
from pathlib import Path

from shortdramagen import cli, film, mp4
from shortdramagen.models import BookRef

from fakes import audio_track, make_mp4, video_track

AVCC_1080 = bytes.fromhex("01640032ffe1")
AVCC_720 = bytes.fromhex("01640028ffe1")
ASC = bytes.fromhex("2b920800")


def episode_bytes(seconds: float, avcc=AVCC_1080, size=(1080, 1920), bitrate=64_000) -> bytes:
    """Like a DramaBox episode: the edit lists hide ~0.115 s of AAC priming."""
    tracks = (
        video_track(*size, avcc, seconds, edit_s=seconds),
        audio_track(ASC, bitrate, seconds + 0.118, edit_s=seconds + 0.003),
    )
    return make_mp4(seconds + 0.118, tracks=tracks)


class TempDirTest(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.tmp = Path(self._tmp.name)

    def tearDown(self):
        self._tmp.cleanup()

    def series(self, name="41000105199-one-night-to-forever", episodes=(), title="Qui Est la Véritable Mme Lafont ?", **manifest):
        d = self.tmp / name
        d.mkdir()
        for number, data in episodes:
            (d / f"E{number:03d}.mp4").write_bytes(data)
        data = {"title": title, "episodes": [{"number": n} for n, _ in episodes], **manifest}
        (d / "manifest.json").write_text(json.dumps(data), encoding="utf-8")
        return d


class ProbeTest(TempDirTest):
    def test_tracks_and_durations(self):
        f = self.tmp / "e.mp4"
        f.write_bytes(episode_bytes(153.0))
        info = mp4.probe(f)
        self.assertAlmostEqual(info.duration, 153.118, places=3)
        self.assertAlmostEqual(info.presentation, 153.003, places=3)
        self.assertEqual((info.video.codec, info.video.width, info.video.height), ("avc1", 1080, 1920))
        self.assertEqual(info.video.config, AVCC_1080)
        self.assertEqual((info.audio.codec, info.audio.channels, info.audio.sample_rate), ("mp4a", 2, 44100))
        self.assertEqual(info.audio.config, b"\x40" + ASC)  # object type + AudioSpecificConfig

    def test_format_key_ignores_bitrate_but_not_resolution(self):
        paths = {}
        for name, data in {
            "a": episode_bytes(10, bitrate=64_017),
            "b": episode_bytes(20, bitrate=64_011),
            "c": episode_bytes(10, avcc=AVCC_720, size=(720, 1280)),
        }.items():
            paths[name] = self.tmp / f"{name}.mp4"
            paths[name].write_bytes(data)
        keys = {name: mp4.probe(p).format_key for name, p in paths.items()}
        self.assertEqual(keys["a"], keys["b"])
        self.assertNotEqual(keys["a"], keys["c"])

    def test_not_an_mp4(self):
        f = self.tmp / "x.mp4"
        f.write_bytes(b"<html>")
        self.assertIsNone(mp4.probe(f))


class PlanTest(TempDirTest):
    def test_complete_and_compatible(self):
        d = self.series(episodes=[(1, episode_bytes(153)), (2, episode_bytes(110))])
        plan = film.plan_film(d)
        self.assertTrue(plan.compatible)
        self.assertEqual([p.number for p in plan.parts], [1, 2])
        self.assertAlmostEqual(plan.length(reencode=False), 263.236, places=3)
        self.assertAlmostEqual(plan.length(reencode=True), 263.006, places=3)
        self.assertEqual(film.default_output(plan).name, "Qui Est la Véritable Mme Lafont.mp4")

    def test_missing_episodes(self):
        d = self.series(episodes=[(1, episode_bytes(10)), (4, episode_bytes(10))])
        (d / "manifest.json").write_text(json.dumps({"title": "t", "episodes": [{"number": n} for n in range(1, 6)]}))
        with self.assertRaises(film.FilmError) as ctx:
            film.plan_film(d)
        self.assertIn("2-3, 5", str(ctx.exception))
        plan = film.plan_film(d, allow_missing=True)
        self.assertEqual(([p.number for p in plan.parts], plan.missing), ([1, 4], [2, 3, 5]))
        self.assertEqual(film.default_output(plan).name, "t (épisodes 1, 4).mp4")

    def test_only_some_episodes(self):
        d = self.series(episodes=[(n, episode_bytes(10)) for n in range(1, 6)], title="t")
        plan = film.plan_film(d, only={2, 3})
        self.assertEqual(([p.number for p in plan.parts], plan.missing), ([2, 3], []))
        self.assertEqual(film.default_output(plan).name, "t (épisodes 2-3).mp4")

    def test_mixed_formats(self):
        d = self.series(
            episodes=[
                (1, episode_bytes(100)),
                (2, episode_bytes(30, avcc=AVCC_720, size=(720, 1280))),
                (3, episode_bytes(100)),
            ]
        )
        plan = film.plan_film(d)
        self.assertFalse(plan.compatible)
        self.assertEqual(plan.main_format().video.height, 1920)
        with self.assertRaises(film.FilmError) as ctx:
            film.ensure_joinable(plan, reencode=False)
        self.assertIn("720x1280", str(ctx.exception))
        film.ensure_joinable(plan, reencode=True)  # no error

    def test_folder_without_manifest(self):
        d = self.tmp / "vrac"
        d.mkdir()
        for n in (2, 1):
            (d / f"E{n:03d}.mp4").write_bytes(episode_bytes(5))
        (d / "notes.txt").write_text("x")
        self.assertEqual([p.number for p in film.plan_film(d).parts], [1, 2])


class FfmpegInputsTest(TempDirTest):
    def plan(self):
        d = self.series(name="l'été", episodes=[(1, episode_bytes(153)), (2, episode_bytes(110))], title="A = B ; #1")
        return film.plan_film(d)

    def test_concat_list_quotes_and_durations(self):
        text = film.concat_list_text(self.plan())
        lines = text.splitlines()
        self.assertEqual(lines[0], "ffconcat version 1.0")
        self.assertTrue(lines[1].startswith("file '") and "l'\\''été" in lines[1])
        self.assertEqual(lines[2], "duration 153.118000")
        self.assertEqual(lines[4], "duration 110.118000")

    def test_chapters_follow_the_segments(self):
        plan = self.plan()
        copy = film.ffmetadata(plan)
        self.assertIn("title=A \\= B \\; \\#1", copy)
        self.assertIn("START=153118\nEND=263236\ntitle=Épisode 2", copy)
        reencoded = film.ffmetadata(plan, reencode=True)
        self.assertIn("START=153003\nEND=263006", reencoded)
        self.assertNotIn("[CHAPTER]", film.ffmetadata(plan, chapters=False))

    def test_reencode_graph_inline_or_script(self):
        plan = self.plan()
        graph = film.reencode_filter(plan)
        self.assertIn("scale=1080:1920", graph)
        self.assertIn("concat=n=2:v=1:a=1[v][a]", graph)
        args = film.reencode_args("ffmpeg", plan, self.tmp / "m.txt", graph, self.tmp / "o.mp4", self.tmp)
        self.assertIn("-filter_complex", args)
        long_graph = graph + "null" * 10_000
        args = film.reencode_args("ffmpeg", plan, self.tmp / "m.txt", long_graph, self.tmp / "o.mp4", self.tmp)
        self.assertIn("-filter_complex_script", args)

    def test_helpers(self):
        self.assertEqual(film.safe_filename('Qui ? "Moi" : <toi>/lui. '), "Qui Moi toilui")
        self.assertEqual(film.safe_filename("???"), "film")
        self.assertEqual(film.format_ranges([7, 1, 2, 3, 9, 10]), "1-3, 7, 9-10")


class FindSeriesDirTest(TempDirTest):
    def test_picks_language(self):
        vo = self.series("41000105199-one-night-to-forever", lang="en", source_book_id="41000105199")
        vf = self.series("41000105199-one-night-to-forever-fr", lang="fr", source_book_id="41000111625")
        self.series("42000000000-autre", lang="en", source_book_id="42000000000")
        self.assertEqual(film.find_series_dir(self.tmp, BookRef("41000105199")), vo)
        self.assertEqual(film.find_series_dir(self.tmp, BookRef("41000105199"), "fr"), vf)
        self.assertEqual(film.find_series_dir(self.tmp, BookRef("41000105199", "fr")), vf)
        with self.assertRaises(film.FilmError):
            film.find_series_dir(self.tmp, BookRef("41000105199"), "es")
        with self.assertRaises(film.FilmError):
            film.find_series_dir(self.tmp, BookRef("41099999999"))


def _ffmpeg_or_none():
    try:
        return film.find_ffmpeg()
    except film.FilmError:
        return None


FFMPEG = _ffmpeg_or_none()


@unittest.skipUnless(FFMPEG, "ffmpeg absent (pip install imageio-ffmpeg pour ces tests)")
class RealFfmpegTest(TempDirTest):
    """End to end with a real ffmpeg on tiny generated episodes."""

    def encode(self, dest: Path, seconds: float, size: str, tone: int) -> None:
        subprocess.run(
            [FFMPEG, "-v", "error", "-y",
             "-f", "lavfi", "-i", f"testsrc=size={size}:rate=25:duration={seconds}",
             "-f", "lavfi", "-i", f"sine=frequency={tone}:sample_rate=44100:duration={seconds}",
             "-c:v", "libx264", "-preset", "ultrafast", "-c:a", "aac", "-shortest", str(dest)],
            check=True,
        )  # fmt: skip

    def make_series(self, sizes):
        d = self.series(episodes=[], title="Test : film ?")
        for n, size in enumerate(sizes, start=1):
            self.encode(d / f"E{n:03d}.mp4", 2, size, 300 + 100 * n)
        (d / "manifest.json").write_text(
            json.dumps({"title": "Test : film ?", "episodes": [{"number": n} for n in range(1, len(sizes) + 1)]}),
            encoding="utf-8",
        )
        return d

    def chapters(self, path: Path) -> int:
        out = subprocess.run([FFMPEG, "-hide_banner", "-i", str(path)], capture_output=True, text=True).stderr
        return out.count("Chapter #")

    def test_copy_join_with_chapters(self):
        d = self.make_series(["64x128"] * 3)
        plan = film.plan_film(d)
        seen = []
        result = film.build_film(plan, film.default_output(plan), FFMPEG, on_progress=lambda t, total: seen.append(t))
        self.assertEqual(result.path.name, "Test film.mp4")
        self.assertEqual(result.mode, "copy")
        self.assertAlmostEqual(result.duration, plan.length(reencode=False), delta=0.2)
        self.assertEqual(self.chapters(result.path), 3)
        self.assertEqual(mp4.probe(result.path).video.width, 64)
        self.assertTrue(seen)
        manifest = json.loads((d / "manifest.json").read_text(encoding="utf-8"))
        self.assertEqual(manifest["film"]["episodes"], [1, 2, 3])
        self.assertEqual(list(d.glob("*.part")), [])

    def test_mixed_sizes_need_reencode(self):
        d = self.make_series(["64x128", "32x64", "64x128"])
        plan = film.plan_film(d)
        with self.assertRaises(film.FilmError):
            film.build_film(plan, self.tmp / "out.mp4", FFMPEG)
        result = film.build_film(plan, self.tmp / "out.mp4", FFMPEG, reencode=True)
        info = mp4.probe(result.path)
        self.assertEqual((info.video.width, info.video.height), (64, 128))
        self.assertEqual(self.chapters(result.path), 3)

    def test_cli(self):
        d = self.make_series(["64x128"] * 2)
        self.assertEqual(cli.main(["film", str(d), "--ffmpeg", FFMPEG, "-f", str(self.tmp / "f.mp4")]), 0)
        self.assertTrue((self.tmp / "f.mp4").exists())
        self.assertEqual(cli.main(["film", "41000105199", "-o", str(self.tmp / "vide")]), 1)


if __name__ == "__main__":
    unittest.main()
