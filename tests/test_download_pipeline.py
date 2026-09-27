import json
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from shortdramagen import mp4, pipeline
from shortdramagen.download import IntegrityError, UrlRejected, download, part_path
from shortdramagen.models import BookRef, VideoSource

from fakes import FakeHttp, cdn_url, make_mp4, series_http

class TempDirTest(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.tmp = Path(self._tmp.name)

    def tearDown(self):
        self._tmp.cleanup()


class Mp4Test(TempDirTest):
    def test_duration(self):
        f = self.tmp / "a.mp4"
        f.write_bytes(make_mp4(79.134))
        self.assertAlmostEqual(mp4.duration_seconds(f), 79.134, places=3)

    def test_not_mp4(self):
        f = self.tmp / "a.mp4"
        f.write_bytes(b"<html>Just a moment...</html>")
        self.assertIsNone(mp4.duration_seconds(f))


class DownloadTest(TempDirTest):
    URL = "https://cdn.example/video.mp4"

    def test_full_download_and_duration_check(self):
        data = make_mp4(79.134, payload=50_000)
        dest = self.tmp / "E028.mp4"
        self.assertEqual(download(FakeHttp(files={self.URL: data}), self.URL, dest, 79134), len(data))
        self.assertEqual(dest.read_bytes(), data)
        self.assertFalse((self.tmp / "E028.mp4.part").exists())

    def test_resume_from_part_file(self):
        data = make_mp4(10, payload=50_000)
        dest = self.tmp / "E001.mp4"
        part_path(dest, self.URL).write_bytes(data[:20_000])
        stale = self.tmp / "E001.other.1080p.mp4.part"  # left over by another quality
        stale.write_bytes(b"x" * 30_000)
        http = FakeHttp(files={self.URL: data})
        download(http, self.URL, dest, 10_000)
        self.assertEqual(http.calls[0][1]["Range"], "bytes=20000-")
        self.assertEqual(dest.read_bytes(), data)
        self.assertEqual(list(self.tmp.glob("*.part")), [])

    def test_part_files_are_per_rendition(self):
        dest = self.tmp / "E028.mp4"
        a = part_path(dest, "https://x/1_1/577159363.1080p.nav2.mp4?sig=1")
        b = part_path(dest, "https://x/1_1/577159363.720p.narrowv3.mp4?sig=1")
        self.assertEqual(a.name, "E028.577159363.1080p.nav2.mp4.part")
        self.assertNotEqual(a, b)

    def test_wrong_duration_is_rejected_and_removed(self):
        dest = self.tmp / "E002.mp4"
        with self.assertRaises(IntegrityError):
            download(FakeHttp(files={self.URL: make_mp4(30)}), self.URL, dest, 79_134)
        self.assertFalse(dest.exists())
        self.assertEqual(list(self.tmp.glob("*.part")), [])

    def test_expired_url(self):
        with self.assertRaises(UrlRejected):
            download(FakeHttp(files={self.URL: 403}), self.URL, self.tmp / "E003.mp4")


class PickSourceTest(unittest.TestCase):
    SOURCES = [VideoSource(f"u{q}", q, "dramafren") for q in ("720p", "1080p", "540p")]

    def test_pick(self):
        self.assertEqual(pipeline.pick_source(self.SOURCES, "best").quality, "1080p")
        self.assertEqual(pipeline.pick_source(self.SOURCES, "720p").quality, "720p")
        self.assertEqual(pipeline.pick_source(self.SOURCES, "480p").quality, "540p")  # nothing lower: smallest


class SelectEpisodesTest(unittest.TestCase):
    def test_ranges_and_warning(self):
        series = pipeline.Series("b", "b", "en", "t", "s", [pipeline.Episode(n, str(n), str(n)) for n in range(1, 63)])
        logs = []
        picked = pipeline.select_episodes(series, [(1, 2), (60, None), (70, 80)], logs.append)
        self.assertEqual([ep.number for ep in picked], [1, 2, 60, 61, 62])
        self.assertEqual(logs, ["Attention : la série compte 62 épisodes, ignoré au-delà : 70-80"])
        self.assertEqual(len(pipeline.select_episodes(series, None, logs.append)), 62)


class FetchTest(TempDirTest):
    """End to end on the 3-episode fixture (episodes 1, 2 and 28)."""

    def make_http(self, dramafren_answers=None, broken=()):
        return series_http(dramafren_answers, broken)

    def run_fetch(self, http, **kw):
        opts = pipeline.FetchOptions(out_dir=self.tmp, api_interval=0, **kw)
        with mock.patch("shortdramagen.pipeline.time.sleep"):
            return pipeline.fetch(http, BookRef("41000105199"), opts, log=lambda _: None)

    def test_downloads_everything_then_skips_on_rerun(self):
        result = self.run_fetch(self.make_http())
        self.assertEqual(result.done, [1, 2, 28])
        self.assertEqual(result.failed, {})
        manifest = json.loads((result.series_dir / "manifest.json").read_text(encoding="utf-8"))
        self.assertEqual([e["status"] for e in manifest["episodes"]], ["done"] * 3)
        self.assertEqual({e["quality"] for e in manifest["episodes"]}, {"1080p"})

        again = self.run_fetch(self.make_http())
        self.assertEqual((again.done, again.skipped), ([], [1, 2, 28]))

    def test_url_for_wrong_episode_is_rejected(self):
        # dramafren answers episode 28 with the video of episode 1: must not be saved as E028.
        wrong = cdn_url("41000105199", "577159336", "720p")
        http = self.make_http({28: {"ok": True, "videoUrl": wrong, "qualities": []}})
        result = self.run_fetch(http, episodes=[(28, 28)])
        self.assertIn(28, result.failed)
        self.assertFalse((result.series_dir / "E028.mp4").exists())

    def test_probes_dramafren_when_official_page_is_missing(self):
        http = self.make_http()
        del http.pages["https://www.dramaboxdb.com/movie/41000105199/"]  # -> 404
        result = self.run_fetch(http)
        self.assertFalse(result.series.from_official)
        self.assertEqual(result.done, [1, 2])  # the fake API has no episode 3: probing stops there

    def test_falls_back_to_official_free_video(self):
        http = self.make_http(broken={1})  # dramafren URLs of episode 1 are refused by the CDN
        result = self.run_fetch(http, episodes=[(1, 1)])
        self.assertEqual(result.done, [1])
        manifest = json.loads((result.series_dir / "manifest.json").read_text(encoding="utf-8"))
        self.assertEqual(manifest["episodes"][0]["origin"], "official")


if __name__ == "__main__":
    unittest.main()
