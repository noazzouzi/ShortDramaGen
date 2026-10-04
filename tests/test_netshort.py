"""NetShort: links, official episode pages, dramafren's resolve_watch, every episode and its subtitles (offline)."""

import json
import tempfile
import unittest
from datetime import datetime, timezone
from pathlib import Path
from unittest import mock

from urllib.parse import parse_qs, urlparse

from fakes import FIXTURES, FakeHttp, make_mp4
from test_jobs import LiveTest

from shortdramagen import errors, library, pipeline
from shortdramagen.http import HttpStatusError
from shortdramagen.inputs import InputError, parse_input
from shortdramagen.library import LibraryIndex
from shortdramagen.models import BookRef
from shortdramagen.providers import netshort, registry

NS_ID = "2103009231497199618"  # French version of "Naked Tide": 50 episodes, 1 to 7 free
NS_URL = f"https://netshort.com/fr/episode/mon-rival-mon-demi-fr%C3%A8re-{NS_ID}"
PAGE = (FIXTURES / "netshort_episode.html").read_text(encoding="utf-8")  # episode 2
VIDEO = "https://cfcdn.netshort.com/o8cfQFQTG9MJb0VfCLWfX54B8egQqVEUm3AJy9?a=0&auth_key=1791353347-"
SUB_FR = "https://cfcdn.netshort.com/4edec9250c6f44d1a1c21b6c15b9fcf9?auth_key=1791707082-"
COVER = (
    "https://awscover.netshort.com/tos-vod-mya-v-da59d5a2040f5f77/imageG/production/2103009228447940610/"
    "1790844922637-3681890766200928-3%E6%AF%944jpg~tplv-vod-rs:540:720.webp"
)
CDN = "https://cfcdn.netshort.com/"
VTT = "WEBVTT\n\n00:00:06.366 --> 00:00:07.700\nTon maillot est toujours aussi lâche ?\n"
PLAYER = json.loads((FIXTURES / "netshort_resolve_watch.json").read_text(encoding="utf-8"))  # episode 10 of NS_ID
DF_CDN = "https://ns-aws-cdn.netshort.com/"
REFUSAL = {"ok": False, "status": 404, "server": 1, "message": "Video URL is unavailable for this episode."}


def episode_page(number: int, duration: float = 80.0, locked: bool = False, subtitles: bool = True) -> str:
    """The fixture's page, showing another episode: its own video and subtitles, or none when locked."""
    detail, current = netshort.page_data(PAGE)
    langs = ("it_IT", "fr_FR") if subtitles else ()
    current = dict(
        current,
        episodeNo=number,
        isLock=locked,
        duration=f"{duration}",
        playVoucher=None if locked else f"{CDN}ep{number:03d}?a=0&auth_key=1791353347-x-0-y&mime_type=video_mp4",
        subtitleList=[{"url": f"{CDN}sub-{lang}-{number:03d}?auth_key=1791707082-x-0-y", "format": "webvtt", "subtitleLanguage": lang} for lang in langs],
    )  # fmt: skip
    row = json.dumps(["$L2b", ["$", "$L2c", None, {"shortPlayDetailVo": detail, "initialCurrentEpisodeInfo": current}]])
    return f"<html><script>self.__next_f.push([1,{json.dumps('6:' + row)}])</script></html>"


def player_answer(number: int) -> dict:
    """What resolve_watch answers for an episode: its own MP4 and French subtitles."""
    url = f"{DF_CDN}df{number:03d}?a=0&auth_key=1791358483-x-0-y&mime_type=video_mp4"
    sub = f"{DF_CDN}dfsub-{number:03d}?auth_key=1791707082-x-0-y&mime_type=text_plain"
    return dict(PLAYER, videoUrl=url, qualities=[{"quality": "Default", "url": url}], subtitles=[{"subtitleLanguage": "fr_FR", "url": sub}])


def netshort_http(
    video_durations=None, broken_official=(), bad_subtitles=(), player_missing=(), player_down=False
) -> FakeHttp:
    """The official episode pages (any slug) and free MP4s, dramafren's resolve_watch and MP4s of
    every episode, the WebVTT files, the cover. Episode n lasts 80 + n s; ``video_durations``: what
    both files really last; ``broken_official``: free episodes whose official file is wrong."""
    durations = {n: 80.0 + n for n in range(1, 51)}
    real = durations | dict(video_durations or {})
    files = {f"{DF_CDN}df{n:03d}": make_mp4(real[n]) for n in durations}
    files |= {f"{CDN}ep{n:03d}": make_mp4(60.0 if n in broken_official else real[n]) for n in range(1, 8)}

    def page(url):
        number = int(url.rsplit("-ep-", 1)[1]) if "-ep-" in url else 1
        return episode_page(number, durations.get(number, 100.0), locked=number > 7)

    def resolve_watch(url):
        query = {k: v[0] for k, v in parse_qs(urlparse(url).query).items()}
        number = int(query["ep"])
        if query["action"] != "resolve_watch" or query["id"] != NS_ID or number not in durations or number in player_missing:
            raise HttpStatusError(url, 404, json.dumps(dict(REFUSAL, server=int(query["server"]))).encode())
        return player_answer(number)

    pages = {
        f"{netshort.BASE_URL}/episode/x-{NS_ID}": page,
        netshort.PLAYER_URL: 502 if player_down else resolve_watch,
        COVER: b"RIFF\x00\x00\x00\x00WEBP",
    }
    for n in durations:
        bad = "<html>Access denied</html>"
        pages[f"{CDN}sub-fr_FR-{n:03d}"] = bad if n in bad_subtitles else VTT
        pages[f"{CDN}sub-it_IT-{n:03d}"] = "WEBVTT\n\nnon voluto\n"
        pages[f"{DF_CDN}dfsub-{n:03d}"] = bad if n in bad_subtitles else VTT
    return FakeHttp(pages=pages, files=files)


class LinkTest(unittest.TestCase):
    def test_links(self):
        ref = BookRef(NS_ID, provider="netshort")
        cases = {
            NS_URL: ref,
            f"{NS_URL}-ep-12": BookRef(NS_ID, episode=12, provider="netshort"),
            f"https://netshort.com/episode/x-{NS_ID}-ep-3/": BookRef(NS_ID, episode=3, provider="netshort"),
            f"www.netshort.com/full-episodes/naked-tide-{NS_ID}": ref,
            f"https://netshort.com/hotseries/naked-tide-{NS_ID}": ref,
            f"https://netshort.com/zh/episode/宿敵繼兄的蓄謀已久-{NS_ID}": ref,
            f"https://netshort.dramafren.org/index.php?page=detail&id={NS_ID}&lang=fr": ref,
            f"https://netshort.dramafren.org/index.php?page=watch&id={NS_ID}&ep=26": BookRef(NS_ID, episode=26, provider="netshort"),
            f"https://cdn-netshort.dramafren.org/index.php?page=watch&id={NS_ID}&ep=2&server=1": BookRef(NS_ID, episode=2, provider="netshort"),
            f"netshort:{NS_ID}": ref,
        }  # fmt: skip
        for text, expected in cases.items():
            with self.subTest(text=text):
                self.assertEqual(parse_input(text), expected)
        self.assertEqual(ref.key, f"netshort:{NS_ID}")

    def test_rejected(self):
        for text in (
            "https://netshort.com/drama/Fantasy-1983832036856381442",  # a genre, not a series
            "https://netshort.com/all-episodes",
            "https://netshort.dramafren.org/index.php?page=detail&id=9561",
            "netshort:24403",
        ):
            with self.subTest(text=text), self.assertRaises(InputError):
                parse_input(text)


class SiteTest(unittest.TestCase):
    def test_series_from_an_episode_page(self):
        series = netshort.parse_series(netshort.page_data(PAGE)[0], NS_ID)
        self.assertEqual((series.provider, series.title, series.slug, series.lang), ("netshort", "MON RIVAL, MON DEMI-FRÈRE", "mon-rival-mon-demi-frere", "fr"))
        self.assertEqual((series.episode_count, series.free_numbers, series.free_only), (50, [1, 2, 3, 4, 5, 6, 7], False))
        self.assertEqual(series.episodes[1].chapter_id, "2104090586893328403")
        self.assertEqual(series.cover, COVER)  # the small WebP, its "比" encoded
        self.assertTrue(series.introduction.startswith("Membre de l’équipe de voile, At aime Mia en secret."))
        self.assertRegex(pipeline.series_dir_name(series), library.KEY_RE)

    def test_fetch_series(self):
        http = netshort_http()
        series = registry.get("netshort").fetch_series(http, parse_input(f"{NS_URL}-ep-12"), None)
        self.assertEqual((series.book_id, series.episode_count), (NS_ID, 50))
        self.assertEqual(http.calls[0][0], f"https://netshort.com/episode/x-{NS_ID}")  # the slug is not needed
        with self.assertRaises(errors.SeriesNotFound):  # an unknown id answers 404
            registry.get("netshort").fetch_series(http, BookRef("1234567890123456789", provider="netshort"), None)
        delisted = PAGE.replace('\\"isDelisted\\":false', '\\"isDelisted\\":true')
        self.assertNotEqual(delisted, PAGE)
        self.assertEqual(netshort.parse_series(netshort.page_data(delisted)[0], NS_ID).free_numbers, [])

    def test_episode_page(self):
        series = netshort.parse_series(netshort.page_data(PAGE)[0], NS_ID)
        ep = series.episodes[1]
        (source,) = netshort.official_sources(*netshort.page_data(PAGE), ep)
        self.assertEqual((source.quality, source.origin, source.kind), ("", "official", "mp4"))
        self.assertTrue(source.url.startswith(VIDEO))
        self.assertTrue(source.subtitles.startswith(SUB_FR))  # the version's language, not Italian or Spanish
        self.assertEqual(ep.duration_ms, 85240)
        self.assertEqual(registry.get("netshort").expires_at(source.url), datetime.fromtimestamp(1791353347, tz=timezone.utc))

        with self.assertRaises(errors.ResolveError) as ctx:  # the site showed another episode
            netshort.official_sources(*netshort.page_data(PAGE), series.episodes[2])
        self.assertEqual(ctx.exception.code, errors.URL_MISMATCH)
        paid = series.episodes[9]
        self.assertEqual(netshort.official_sources(*netshort.page_data(episode_page(10, 114.289, locked=True)), paid), [])
        self.assertEqual(paid.duration_ms, 114289)  # a paid episode's page still gives its duration
        (source,) = netshort.official_sources(*netshort.page_data(episode_page(3, subtitles=False)), series.episodes[2])
        self.assertIsNone(source.subtitles)  # subtitles burned into the video

    def test_player_answer(self):
        (source,) = netshort.parse_player_payload(PLAYER, "fr")
        self.assertEqual((source.quality, source.origin, source.kind), ("", "dramafren", "mp4"))
        self.assertTrue(source.url.startswith(f"{DF_CDN}oIZqEdxbfAQqM6wqNvhCAof2EEEQAQF4xyKufD?a=0&auth_key=1791358483-"))
        self.assertTrue(source.subtitles.startswith(f"{DF_CDN}523b6625baa0417aa81c95193eeec73f?auth_key="))
        self.assertEqual(registry.get("netshort").expires_at(source.url), datetime.fromtimestamp(1791358483, tz=timezone.utc))
        self.assertIsNone(netshort.parse_player_payload(PLAYER, "en")[0].subtitles)  # only the version's language
        self.assertEqual(netshort.parse_player_payload(REFUSAL, "fr"), [])
        self.assertEqual(netshort.parse_player_payload({"ok": True, "videoUrl": ""}, "fr"), [])

    def test_resolve(self):
        provider = registry.get("netshort")
        http = netshort_http()
        series = provider.fetch_series(http, BookRef(NS_ID, provider="netshort"), None)
        free = provider.resolve(http, series, series.episodes[2], None, None)  # the official 720p first
        self.assertEqual([(s.origin, s.url.split("?")[0]) for s in free], [("official", f"{CDN}ep003"), ("dramafren", f"{DF_CDN}df003")])
        self.assertEqual(http.calls[-2][0], f"https://netshort.com/episode/x-{NS_ID}-ep-3")
        self.assertEqual(http.calls[-1][0], f"{netshort.PLAYER_URL}?action=resolve_watch&id={NS_ID}&ep=3&server=1")

        paid = series.episodes[9]
        ((source),) = provider.resolve(http, series, paid, None, None)
        self.assertEqual((source.url.split("?")[0], source.subtitles.split("?")[0], paid.duration_ms), (f"{DF_CDN}df010", f"{DF_CDN}dfsub-010", 90000))

        http = netshort_http(player_missing=[10])
        with self.assertRaises(errors.ResolveError) as ctx:  # both servers say no
            provider.resolve(http, series, paid, None, None)
        self.assertEqual(ctx.exception.code, errors.EP_UNAVAILABLE)
        self.assertIn("serveur 2 : Video URL is unavailable", str(ctx.exception))
        self.assertTrue(http.calls[-1][0].endswith("&ep=10&server=2"))

        http = netshort_http(player_down=True)
        self.assertEqual([s.origin for s in provider.resolve(http, series, series.episodes[2], None, None)], ["official"])
        with self.assertRaises(errors.ResolveError) as ctx:
            provider.resolve(http, series, paid, None, None)
        self.assertEqual(ctx.exception.code, errors.NETWORK)
        self.assertEqual(len([u for u, _ in http.calls if u.startswith(netshort.PLAYER_URL)]), 2)  # no second server

        http = netshort_http()
        http.pages[f"{netshort.BASE_URL}/episode/x-{NS_ID}"] = 502  # the official site is down: dramafren's file, unchecked
        paid.duration_ms = None
        ((source),) = provider.resolve(http, series, paid, None, None)
        self.assertEqual((source.origin, paid.duration_ms), ("dramafren", None))

    def test_availability(self):
        provider = registry.get("netshort")
        http = netshort_http()
        series = provider.fetch_series(http, BookRef(NS_ID, provider="netshort"), None)
        found = provider.availability(http, series, None, None)
        self.assertEqual((found.available, found.qualities), (True, []))
        self.assertTrue(http.calls[-1][0].endswith("&ep=50&server=1"))  # the last episode
        found = provider.availability(netshort_http(player_missing=[50]), series, None, None)
        self.assertEqual((found.available, found.error.code), (False, errors.EP_UNAVAILABLE))
        found = provider.availability(netshort_http(player_down=True), series, None, None)
        self.assertEqual((found.available, found.error.code), (False, errors.NETWORK))


class FetchTest(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.out = Path(tmp.name)
        patcher = mock.patch.object(pipeline, "RETRY_BASE_DELAY", 0)
        patcher.start()
        self.addCleanup(patcher.stop)

    def fetch(self, http, **opts):
        options = pipeline.FetchOptions(out_dir=self.out, api_interval=0, **opts)
        return pipeline.fetch(http, parse_input(NS_URL), options, log=lambda _: None)

    def test_every_episode_with_its_subtitles(self):
        result = self.fetch(netshort_http())
        self.assertEqual((result.done, result.failed), (list(range(1, 51)), {}))
        self.assertEqual(result.series_dir.name, f"netshort-{NS_ID}-mon-rival-mon-demi-frere")
        names = sorted(p.name for p in result.series_dir.iterdir())
        self.assertEqual(names[:4], ["E001.fr.vtt", "E001.mp4", "E002.fr.vtt", "E002.mp4"])
        self.assertEqual(names[-2:], ["cover.jpg", "manifest.json"])
        self.assertEqual(len(names), 102)
        self.assertEqual((result.series_dir / "E001.fr.vtt").read_text(encoding="utf-8"), VTT)
        self.assertEqual((result.series_dir / "E010.fr.vtt").read_text(encoding="utf-8"), VTT)
        manifest = json.loads((result.series_dir / "manifest.json").read_text(encoding="utf-8"))
        first, paid = manifest["episodes"][0], manifest["episodes"][9]
        self.assertEqual((manifest["platform"], manifest["free_only"]), ("netshort", False))
        self.assertEqual((first["origin"], first["url_expires_at"]), ("official", "2026-10-07T06:09:07+00:00"))
        self.assertEqual((paid["origin"], paid["url_expires_at"]), ("dramafren", "2026-10-07T07:34:43+00:00"))

        index = LibraryIndex(self.out)
        index.refresh(force=True)
        group = index.library()["groups"][0]
        self.assertEqual((group["ref"], group["provider_label"]), (f"netshort:{NS_ID}", "NetShort"))

        again = self.fetch(netshort_http())
        self.assertEqual((again.done, again.skipped), ([], list(range(1, 51))))

    def test_fallbacks_and_checks(self):
        http = netshort_http(broken_official=[2], video_durations={4: 70.0}, bad_subtitles=[3], player_missing=[9])
        result = self.fetch(http, episodes=[(1, 4), (9, 9)])
        self.assertEqual(result.done, [1, 2])  # E002: the official file is wrong, dramafren's is right
        self.assertEqual(
            result.failed_codes,
            {3: errors.SUBTITLES_UNREADABLE, 4: errors.DURATION_MISMATCH, 9: errors.EP_UNAVAILABLE},
        )
        self.assertFalse((result.series_dir / "E003.fr.vtt").exists())
        manifest = json.loads((result.series_dir / "manifest.json").read_text(encoding="utf-8"))
        self.assertEqual([e["origin"] for e in manifest["episodes"][:2]], ["official", "dramafren"])


class ServerTest(LiveTest):
    def make_http(self):
        return netshort_http()

    def test_preview_then_download(self):
        status, data = self.call("POST", "/api/preview", {"input": NS_URL})
        self.assertEqual(status, 200, data)
        self.assertEqual((data["provider"], data["ref"], data["title"], data["episode_count"]), ("netshort", f"netshort:{NS_ID}", "MON RIVAL, MON DEMI-FRÈRE", 50))
        self.assertEqual((data["free_only"], data["free_episodes"], data["availability"]["source"]), (False, [1, 2, 3, 4, 5, 6, 7], "ok"))
        self.assertEqual(data["cover_url"], f"/media/preview/netshort:{NS_ID}/vo/cover")  # the route accepts a 19-digit id

        status, data = self.call("POST", "/api/jobs", {"kind": "fetch", "input": NS_URL})
        self.assertEqual(status, 201, data)
        job = self.wait_job(data["job"]["id"], "done", "failed")
        self.assertEqual(job["status"], "done", job)
        status, lib = self.call("GET", "/api/library")
        self.assertEqual(lib["groups"][0]["ref"], f"netshort:{NS_ID}")


if __name__ == "__main__":
    unittest.main()
