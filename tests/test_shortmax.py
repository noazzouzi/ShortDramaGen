"""ShortMax through its player (shortmax.ngeshorts.fun) and the video_server API (offline)."""

import json
import tempfile
import unittest
from pathlib import Path
from unittest import mock
from urllib.parse import parse_qs, urlparse

from fakes import FIXTURES, FakeHttp
from test_providers import fake_remux, media_playlist

from shortdramagen import errors, library, pipeline
from shortdramagen.inputs import InputError, parse_input
from shortdramagen.library import LibraryIndex
from shortdramagen.models import BookRef
from shortdramagen.providers import player, registry, shortmax

SM_URL = "https://shortmax.ngeshorts.fun/index.php?page=detail&id=24403&lang=fr"
HLS = "https://akamai-static.shorttv.live/hls/"
UUID = "681c719b-102a-49cd-b2e5-d05ec2a2d4e5"
DETAIL = (FIXTURES / "shortmax_detail.html").read_text(encoding="utf-8")
ANSWER = (FIXTURES / "shortmax_video_server.json").read_text(encoding="utf-8")  # episode 30, server1
REFUSED = {"ok": False, "message": "Server unavailable"}
V3, V5, OWN = shortmax.VIDEO_ENDPOINTS


def query(url: str) -> dict:
    return {k: v[0] for k, v in parse_qs(urlparse(url).query).items()}


def shortmax_http(count=3, durations=(10.0, 10.0, 4.68), refused=(), down=(), server1_refuses=()) -> FakeHttp:
    """The player's detail page, the video_server API on its three endpoints, the CDN's playlists and segments.
    ``refused``: episodes no server has; ``down``: endpoints answering 502; ``server1_refuses``: episodes only server2 has."""
    detail = DETAIL.replace("Total: 67 Eps", f"Total: {count} Eps").replace("ep=67&", f"ep={count}&")

    def api(url):
        q = query(url)
        if q.get("page") == "detail":
            return detail if q["id"] == "24403" else "<html><title>ShortMax Player</title></html>"
        n = int(q["ep"])
        if q["id"] != "24403" or n > count or n in refused or (n in server1_refuses and q["server"] == "server1"):
            return REFUSED
        return json.loads(ANSWER.replace(UUID, f"ep{n:03d}"))

    pages: dict = {}
    for endpoint in shortmax.VIDEO_ENDPOINTS:
        pages[endpoint] = 502 if endpoint in down else api
    pages[OWN] = 502 if OWN in down else api  # also the detail page
    for n in range(1, count + 1):
        for height in (1080, 720, 480):
            base = f"{HLS}ep{n:03d}_{height}/"
            pages[base + "main.m3u8"] = media_playlist([(f"main/segment-{i}.ts", s) for i, s in enumerate(durations)])
            pages.update({f"{base}main/segment-{i}.ts": f"{s}|".encode() for i, s in enumerate(durations)})
    return FakeHttp(pages=pages)


class LinkTest(unittest.TestCase):
    def test_links(self):
        ref = BookRef("24403", provider="shortmax")
        cases = {
            SM_URL: ref,
            "https://shortmax.ngeshorts.fun/index.php?page=watch&id=24403&ep=30&lang=fr": BookRef("24403", episode=30, provider="shortmax"),
            "https://shortmax.dramafren.org/index.php?page=detail&id=24403&lang=fr": ref,
            "https://www.shorttv.live/fr/drama/doubl%C3%A9prot%C3%A9g%C3%A9e-par-le-seigneur-serpent-24403": ref,
            "https://www.shorttv.live/fr/episode/doubl%C3%A9prot%C3%A9g%C3%A9e-par-le-seigneur-serpent-24403-12": BookRef("24403", episode=12, provider="shortmax"),
            "www.shortmax.com/drama/beauty-killer-27195": BookRef("27195", provider="shortmax"),
            "shortmax:24403": ref,
            "https://dramabox.dramafren.org/index.php?page=detail&id=41000105199": BookRef("41000105199"),
        }  # fmt: skip
        for text, expected in cases.items():
            with self.subTest(text=text):
                self.assertEqual(parse_input(text), expected)

    def test_rejected(self):
        for text in ("https://shortmax.ngeshorts.fun/index.php?page=home", "shortmax:abc", "https://www.shorttv.live/fr/"):
            with self.subTest(text=text), self.assertRaises(InputError):
                parse_input(text)


class SeriesTest(unittest.TestCase):
    def test_detail_page(self):
        series = player.parse_detail_page(DETAIL, "24403", "shortmax", "le lecteur ShortMax")
        self.assertEqual((series.title, series.slug, series.episode_count), ("[Doublé]Protégée par le Seigneur Serpent", "double-protegee-par-le-seigneur-serpent", 67))
        self.assertTrue(series.cover.startswith("https://akamai-static.shorttv.live/images/cover/"))
        self.assertTrue(series.introduction.startswith("Trahie et ruinée, Madeleine Beaulieu revient de l'enfer carcéral."))
        self.assertRegex(pipeline.series_dir_name(series), library.KEY_RE)
        with self.assertRaises(errors.SeriesNotFound):
            registry.get("shortmax").fetch_series(shortmax_http(), BookRef("1", provider="shortmax"), None)

    def test_video_server(self):
        http = shortmax_http()
        sources = shortmax.get_video(http, "24403", 2)
        self.assertEqual([(s.quality, s.origin, s.kind) for s in sources], [("1080p", "dramafren", "hls"), ("720p", "dramafren", "hls"), ("480p", "dramafren", "hls")])
        self.assertTrue(sources[0].url.startswith(f"{HLS}ep002_1080/main.m3u8?auth_key="))  # the CDN, not dramafren's proxy
        self.assertEqual([u.split("?")[0] for u, _ in http.calls], [V3])
        self.assertEqual(query(http.calls[0][0]), {"action": "video_server", "server": "server1", "id": "24403", "ep": "2", "stale": "1"})

    def test_endpoints_then_servers(self):
        http = shortmax_http(down=[V3])  # network trouble: the next endpoint
        self.assertEqual(shortmax.get_video(http, "24403", 1)[0].quality, "1080p")
        self.assertEqual([u.split("?")[0] for u, _ in http.calls], [V3, V5])

        http = shortmax_http(server1_refuses=[1])  # a refusal: the next server
        shortmax.get_video(http, "24403", 1)
        self.assertEqual([(u.split("?")[0], query(u)["server"]) for u, _ in http.calls], [(V3, "server1"), (V3, "server2")])

        http = shortmax_http(refused=[1])
        with self.assertRaises(errors.ResolveError) as ctx:
            shortmax.get_video(http, "24403", 1)
        self.assertEqual((ctx.exception.code, len(http.calls)), (errors.EP_UNAVAILABLE, 2))

        http = shortmax_http(down=list(shortmax.VIDEO_ENDPOINTS))
        with self.assertRaises(errors.ResolveError) as ctx:
            shortmax.get_video(http, "24403", 1)
        self.assertEqual((ctx.exception.code, len(http.calls)), (errors.NETWORK, 6))

    def test_availability(self):
        provider = registry.get("shortmax")
        series = provider.fetch_series(shortmax_http(), parse_input(SM_URL), None)
        found = provider.availability(shortmax_http(), series, None, None)
        self.assertEqual((found.available, found.qualities), (True, ["1080p", "720p", "480p"]))
        found = provider.availability(shortmax_http(refused=[3]), series, None, None)
        self.assertEqual((found.available, found.error.code), (False, errors.EP_UNAVAILABLE))


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
        return pipeline.fetch(http, parse_input(SM_URL), options, log=lambda _: None)

    def test_every_episode(self):
        result = self.fetch(shortmax_http(refused=[3]))
        self.assertEqual((result.done, result.failed_codes), ([1, 2], {3: errors.EP_UNAVAILABLE}))
        self.assertEqual(result.series_dir.name, "shortmax-24403-double-protegee-par-le-seigneur-serpent")
        manifest = json.loads((result.series_dir / "manifest.json").read_text(encoding="utf-8"))
        self.assertEqual((manifest["platform"], manifest["episodes"][0]["quality"]), ("shortmax", "1080p"))

        index = LibraryIndex(self.out)
        index.refresh(force=True)
        group = index.library()["groups"][0]
        self.assertEqual((group["ref"], group["provider_label"]), ("shortmax:24403", "ShortMax"))

    def test_quality(self):
        result = self.fetch(shortmax_http(), quality="720p", episodes=[(2, 2)])
        manifest = json.loads((result.series_dir / "manifest.json").read_text(encoding="utf-8"))
        self.assertEqual((result.done, manifest["episodes"][1]["quality"]), ([2], "720p"))


if __name__ == "__main__":
    unittest.main()
