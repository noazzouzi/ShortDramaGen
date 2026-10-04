"""FlickReels through dramafren's player: links, detail and watch pages, downloads (offline)."""

import http.client
import json
import re
import tempfile
import unittest
from datetime import datetime, timezone
from pathlib import Path
from unittest import mock
from urllib.parse import parse_qs, urlparse

from fakes import FIXTURES, FakeHttp
from test_jobs import LiveTest
from test_providers import fake_remux, media_playlist

from shortdramagen import errors, library, pipeline
from shortdramagen.inputs import InputError, parse_input
from shortdramagen.library import LibraryIndex
from shortdramagen.models import BookRef
from shortdramagen.providers import flickreels, player, registry

FR_URL = "https://flickreels.dramafren.org/index.php?page=detail&id=9561&lang=fr"
CDN = "https://zshipricf.farsunpteltd.com/playlet-hls/"
COVER = "https://zshipubcf.farsunpteltd.com/playlet/1787042896_cKwzpBZjEd.jpg"
DETAIL = (FIXTURES / "flickreels_detail.html").read_text(encoding="utf-8")
WATCH = (FIXTURES / "flickreels_watch.html").read_text(encoding="utf-8")  # episode 30


def detail_page(count: int = 61) -> str:
    page = DETAIL.replace("Total: 61 Eps", f"Total: {count} Eps")
    return re.sub(r'\s*<a href="index.php\?page=watch&id=9561&ep=(\d+)[^\n]*', lambda m: m.group(0) if int(m.group(1)) <= count else "", page)


def watch_page(number: int, available: bool = True) -> str:
    if not available:  # what the player shows past the last episode
        return re.sub(r"var availableQualities = \[.*?\];", "var availableQualities = [];", WATCH).replace(
            re.search(r'var initialVideoUrl = "[^"]*"', WATCH).group(0), 'var initialVideoUrl = ""'
        )
    return WATCH.replace("1786948437_hls_43051", f"ep{number:03d}").replace("currentEp = 30", f"currentEp = {number}")


def flickreels_http(count: int = 3, durations=(10.0, 10.0, 5.84), missing=(), lying_playlist=()) -> FakeHttp:
    """dramafren's player (detail and watch pages) and the CDN's playlists and segments.
    ``lying_playlist``: episodes whose playlist announces 10 s more than their segments hold."""

    def player(url):
        q = {k: v[0] for k, v in parse_qs(urlparse(url).query).items()}
        if q.get("id") != "9561":
            return "<html><title>FlickReels Player - Watch Free Short Dramas</title></html>"
        if q["page"] == "detail":
            return detail_page(count)
        n = int(q["ep"])
        return watch_page(n, available=n <= count and n not in missing)

    pages: dict = {flickreels.PLAYER_URL: player, COVER: b"\xff\xd8\xff\xe0 jpeg"}
    for n in range(1, count + 1):
        names = [(f"ep{n:03d}-{i:05d}.ts", seconds) for i, seconds in enumerate(durations, 1)]
        announced = [(name, s + 10 if i == 0 and n in lying_playlist else s) for i, (name, s) in enumerate(names)]
        pages[f"{CDN}ep{n:03d}.m3u8"] = media_playlist(announced)
        pages.update({CDN + name: f"{seconds}|".encode() for name, seconds in names})
    return FakeHttp(pages=pages)


class LinkTest(unittest.TestCase):
    def test_links(self):
        ref = BookRef("9561", provider="flickreels")
        cases = {
            FR_URL: ref,
            "https://flickreels.dramafren.org/index.php?page=watch&id=9561&ep=30&lang=fr": BookRef("9561", episode=30, provider="flickreels"),
            "https://cdn-flickreels.dramafren.org/index.php?page=watch&id=9561&ep=1": BookRef("9561", episode=1, provider="flickreels"),
            "https://www.flickreels.net/fr/episodes-list/sss-le-dieu-de-la-foudre-9561": ref,
            "www.flickreels.net/movie/sss-le-dieu-de-la-foudre-9561": ref,
            "https://www.flickreels.net/playlist/sss-le-dieu-de-la-foudre/9561/episode-7": BookRef("9561", episode=7, provider="flickreels"),
            "https://www.flickreels.net/playlist/sss-le-dieu-de-la-foudre/9561/full-movie": ref,
            "flickreels:9561": ref,
            # the other players of dramafren keep their platform
            "https://cdn-goodshort.dramafren.org/index.php?page=watch&id=31000835255&ep=0": BookRef("31000835255", episode=1, provider="goodshort"),
            "https://dramabox.dramafren.org/index.php?page=detail&id=41000105199&lang=fr": BookRef("41000105199"),
        }  # fmt: skip
        for text, expected in cases.items():
            with self.subTest(text=text):
                self.assertEqual(parse_input(text), expected)
        self.assertEqual(ref.key, "flickreels:9561")

    def test_rejected(self):
        for text in ("https://flickreels.dramafren.org/index.php?page=home&lang=fr", "flickreels:abc", "https://www.flickreels.net/classify/avenge/1556/1"):
            with self.subTest(text=text), self.assertRaises(InputError):
                parse_input(text)


class PlayerPagesTest(unittest.TestCase):
    def test_detail_page(self):
        series = player.parse_detail_page(DETAIL, "9561", "flickreels", "dramafren (FlickReels)")
        self.assertEqual((series.provider, series.title, series.slug, series.lang), ("flickreels", "SSS : Le Dieu de la Foudre", "sss-le-dieu-de-la-foudre", ""))
        self.assertEqual((series.episode_count, series.total_duration_ms, series.free_numbers), (61, None, []))
        self.assertEqual(series.cover, COVER)
        self.assertTrue(series.introduction.startswith("Pris pour un Éveillé raté, Nate cache"))
        self.assertRegex(pipeline.series_dir_name(series), library.KEY_RE)  # "flickreels-9561-…": a short id

    def test_unknown_id_gives_the_home_page(self):
        with self.assertRaises(errors.SeriesNotFound):
            registry.get("flickreels").fetch_series(flickreels_http(), BookRef("123", provider="flickreels"), None)

    def test_watch_page(self):
        sources = flickreels.parse_watch_page(WATCH, 30)
        self.assertEqual([(s.quality, s.origin, s.kind) for s in sources], [("", "dramafren", "hls")])
        self.assertTrue(sources[0].url.startswith(CDN + "1786948437_hls_43051.m3u8?verify=1790529231-"))
        self.assertEqual(registry.get("flickreels").expires_at(sources[0].url), datetime.fromtimestamp(1790529231, tz=timezone.utc))
        with self.assertRaises(errors.ResolveError) as ctx:
            flickreels.parse_watch_page(watch_page(62, available=False), 62)
        self.assertEqual(ctx.exception.code, errors.EP_UNAVAILABLE)
        with self.assertRaises(errors.ResolveError):
            flickreels.parse_watch_page("<html>rien</html>", 1)

    def test_resolve_and_availability(self):
        provider = registry.get("flickreels")
        http = flickreels_http()
        series = provider.fetch_series(http, parse_input(FR_URL), None)
        self.assertEqual(provider.resolve(http, series, series.episodes[1], None, None)[0].url.split("?")[0], CDN + "ep002.m3u8")
        asked = {k: v[0] for k, v in parse_qs(urlparse(http.calls[-1][0]).query).items()}
        self.assertEqual(asked, {"page": "watch", "id": "9561", "ep": "2"})
        self.assertEqual((provider.availability(http, series, None, None).available, http.calls[-1][0][-4:]), (True, "ep=3"))
        found = provider.availability(flickreels_http(missing=[3]), series, None, None)
        self.assertEqual((found.available, found.error.code), (False, errors.EP_UNAVAILABLE))
        broken = FakeHttp(pages={flickreels.PLAYER_URL: 502})
        with self.assertRaises(errors.ResolveError) as ctx:
            provider.resolve(broken, series, series.episodes[0], None, None)
        self.assertEqual(ctx.exception.code, errors.NETWORK)


class FetchTest(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.out = Path(tmp.name)
        patcher = mock.patch("shortdramagen.hls._ffmpeg_remux", return_value=fake_remux)
        patcher.start()
        self.addCleanup(patcher.stop)

    def fetch(self, http, **opts):
        options = pipeline.FetchOptions(out_dir=self.out, api_interval=0, **opts)
        return pipeline.fetch(http, parse_input(FR_URL), options, log=lambda _: None)

    def test_every_episode(self):
        result = self.fetch(flickreels_http())
        self.assertEqual((result.done, result.failed), ([1, 2, 3], {}))
        self.assertEqual(result.series_dir.name, "flickreels-9561-sss-le-dieu-de-la-foudre")
        manifest = json.loads((result.series_dir / "manifest.json").read_text(encoding="utf-8"))
        self.assertEqual((manifest["platform"], manifest["episode_count"], manifest["episodes"][0]["origin"]), ("flickreels", 3, "dramafren"))
        self.assertEqual(sorted(p.name for p in result.series_dir.iterdir()), ["E001.mp4", "E002.mp4", "E003.mp4", "cover.jpg", "manifest.json"])

        index = LibraryIndex(self.out)
        index.refresh(force=True)
        group = index.library()["groups"][0]
        self.assertEqual((group["ref"], group["provider_label"], group["versions"][0]["state"]), ("flickreels:9561", "FlickReels", "complete"))

    def test_each_file_is_checked_against_its_playlist(self):
        result = self.fetch(flickreels_http(missing=[3], lying_playlist=[2]))
        self.assertEqual(result.done, [1])
        self.assertEqual(result.failed_codes, {2: errors.DURATION_MISMATCH, 3: errors.EP_UNAVAILABLE})


class ServerTest(LiveTest):
    def make_http(self):
        return flickreels_http()

    def setUp(self):
        patcher = mock.patch("shortdramagen.hls._ffmpeg_remux", return_value=fake_remux)
        patcher.start()
        self.addCleanup(patcher.stop)
        super().setUp()

    def test_preview_then_download(self):
        status, data = self.call("POST", "/api/preview", {"input": FR_URL})
        self.assertEqual(status, 200, data)
        self.assertEqual((data["provider"], data["ref"], data["title"], data["episode_count"]), ("flickreels", "flickreels:9561", "SSS : Le Dieu de la Foudre", 3))
        self.assertEqual((data["availability"]["source"], data["availability"]["qualities"], data["estimate"]), ("ok", [], {}))
        self.assertEqual(data["cover_url"], "/media/preview/flickreels:9561/vo/cover")
        conn = http.client.HTTPConnection("127.0.0.1", self.port, timeout=5)
        conn.request("GET", data["cover_url"], headers={"Host": f"127.0.0.1:{self.port}"})
        resp = conn.getresponse()
        self.assertEqual((resp.status, resp.read()[:2]), (200, b"\xff\xd8"))  # the route accepts a short id
        conn.close()

        status, data = self.call("POST", "/api/jobs", {"kind": "fetch", "input": FR_URL})
        self.assertEqual(status, 201, data)
        job = self.wait_job(data["job"]["id"], "done", "failed")
        self.assertEqual(job["status"], "done", job)
        status, lib = self.call("GET", "/api/library")
        self.assertEqual((lib["groups"][0]["ref"], lib["groups"][0]["versions"][0]["state"]), ("flickreels:9561", "complete"))


if __name__ == "__main__":
    unittest.main()
