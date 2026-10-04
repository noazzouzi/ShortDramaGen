"""Platforms: link parsing, GoodShort metadata and dramafren sources, HLS episodes (offline)."""

import http.client
import json
import tempfile
import unittest
from datetime import datetime, timezone
from pathlib import Path
from unittest import mock
from urllib.parse import parse_qs, urlparse

from fakes import FakeHttp, fixture_json, make_mp4
from test_jobs import LiveTest

from shortdramagen import dramafren, errors, hls, library, pipeline
from shortdramagen.download import IntegrityError
from shortdramagen.inputs import InputError, parse_input
from shortdramagen.jobs import Job
from shortdramagen.library import LibraryIndex
from shortdramagen.models import BookRef
from shortdramagen.providers import goodshort, registry

GS_URL = "https://www.goodshort.com/drama/perfect-love-31000662271"
GS_PROXY = "https://cdn-goodshort.dramafren.org/proxy?token="
GS_QUALITIES = ("720P", "540P", "1080P")  # in the order dramafren lists them


def goodshort_html(state: dict) -> str:
    # as served: the state is followed by a self-removing script on the same line
    return (
        f"<html><script>window.__INITIAL_STATE__={json.dumps(state)};(function(){{var s;}}());</script></html>"
    )


def media_playlist(names_and_durations, key: str = "") -> str:
    lines = ["#EXTM3U", "#EXT-X-VERSION:3", "#EXT-X-TARGETDURATION:5", *([key] if key else [])]
    for name, seconds in names_and_durations:
        lines += [f"#EXTINF:{seconds:.6f},", name]
    return "\n".join(lines + ["#EXT-X-ENDLIST", ""])


def fake_remux(src: Path, dst: Path) -> None:
    """Stands for ffmpeg: an MP4 whose duration is the sum written by the fake segments."""
    seconds = sum(float(x) for x in src.read_bytes().decode().split("|") if x)
    dst.write_bytes(make_mp4(seconds))


def segment_durations(play_time: int) -> list[float]:
    """What an episode of ``play_time`` seconds is cut into: 5 s segments, the last one a bit longer than announced."""
    return [5.0] * (play_time // 5) + [play_time % 5 + 0.3]


def goodshort_chapters() -> list[dict]:
    """The 56 chapters of the fixture series, as ``chapter/page`` lists them (the page embeds only 5)."""
    embedded = {ch["index"]: ch for ch in fixture_json("goodshort_state.json")["BookInfoModule"]["chapterVoList"]}
    return [embedded.get(i) or {"id": 6439092 + i, "index": i, "playTime": 60, "price": 20} for i in range(56)]


def chapters_api(chapters: list[dict]):
    def answer(payload):
        if payload.get("bookId") != "31000662271":
            return {"status": 12000, "message": "Book not exists.", "data": None}
        size, page = payload["pageSize"], payload["pageNo"]
        pages = -(-len(chapters) // size)
        records = chapters[(page - 1) * size : page * size]
        return {"status": 0, "data": {"current": page, "size": size, "total": len(chapters), "pages": pages, "records": records}}

    return answer


def dramafren_goodshort(locked=(), locked_on_server1=()):
    """dramafren's get_video_url: one proxied playlist per quality. ``locked``: chapter ids no server serves;
    ``locked_on_server1``: chapter ids only the other servers serve."""

    def answer(url):
        q = {k: v[0] for k, v in parse_qs(urlparse(url).query).items()}
        chap = q["chap_id"]
        if q["action"] != "get_video_url" or chap in locked or (chap in locked_on_server1 and q["sv"] == "1"):
            return {"status": "error", "video_url": "", "qualities": []}
        qualities = [{"quality": name, "url": f"{GS_PROXY}c{chap}.{name}"} for name in GS_QUALITIES]
        return {"status": "success", "video_url": qualities[0]["url"], "qualities": qualities}

    return answer


def dramafren_proxy(durations: dict[str, list[float]]):
    """``/proxy?token=…``: a playlist (every EXTINF says 5 s, as dramafren writes them), then its segments."""

    def answer(url):
        token = url[len(GS_PROXY):]
        chap, rest = token[1:].split(".", 1)
        quality, _, segment = rest.partition(".s")
        if segment:
            return f"{durations[chap][int(segment)]}|".encode()
        return media_playlist([(f"{GS_PROXY}c{chap}.{quality}.s{i}", 5.0) for i in range(len(durations[chap]))])

    return answer


def goodshort_http(locked=(), locked_on_server1=()) -> FakeHttp:
    """The fixture series page, the chapter API, dramafren (API and proxy) and the official free playlists."""
    state = fixture_json("goodshort_state.json")
    chapters = goodshort_chapters()
    pages: dict = {
        GS_URL: goodshort_html(state),
        goodshort.CHAPTERS_API_URL: chapters_api(chapters),
        dramafren.GOODSHORT_ENDPOINT: dramafren_goodshort({str(c) for c in locked}, {str(c) for c in locked_on_server1}),
        GS_PROXY: dramafren_proxy({str(ch["id"]): segment_durations(ch["playTime"]) for ch in chapters}),
    }
    for ch in chapters:
        url = ch.get("m3u8Path")
        if not url:
            continue
        base = url.split("?")[0].rsplit("/", 1)[0]
        parts = [(f"s{i}.ts", seconds) for i, seconds in enumerate(segment_durations(ch["playTime"]))]
        pages[url.split("?")[0]] = media_playlist(parts)
        for name, seconds in parts:
            pages[f"{base}/{name}"] = f"{seconds}|".encode()
    return FakeHttp(pages=pages)


def goodshort_series():
    return registry.get("goodshort").fetch_series(goodshort_http(), parse_input(GS_URL), None)


class LinkTest(unittest.TestCase):
    def test_goodshort_links(self):
        cases = {
            GS_URL: BookRef("31000662271", provider="goodshort", slug="perfect-love"),
            "goodshort.com/episodes/perfect-love-31000662271": BookRef("31000662271", provider="goodshort", slug="perfect-love"),
            "https://www.goodshort.com/episode/perfect-love-31000662271/003-6439094":
                BookRef("31000662271", episode=3, provider="goodshort", slug="perfect-love"),
            "goodshort:31000662271": BookRef("31000662271", provider="goodshort"),
        }  # fmt: skip
        for text, ref in cases.items():
            with self.subTest(text=text):
                self.assertEqual(parse_input(text), ref)
        self.assertEqual(parse_input(GS_URL).key, "goodshort:31000662271")

    def test_dramafren_goodshort_links(self):
        """dramafren's slug is not the site's: only the id is kept, and ``ep`` counts from 0."""
        base = "https://goodshort.dramafren.org/index.php?"
        cases = {
            base + "page=detail&id=31000835255&lang=fr&slug=engag-e-un-milliardaire-b-tard&sv=1":
                BookRef("31000835255", provider="goodshort"),
            base + "page=watch&id=31000835255&ep=3&lang=fr&slug=engag-e-un-milliardaire-b-tard&sv=1":
                BookRef("31000835255", episode=4, provider="goodshort"),
            base + "page=watch&id=31000835255&ep=0&lang=fr&sv=1": BookRef("31000835255", episode=1, provider="goodshort"),
            "https://dramabox.dramafren.org/index.php?page=detail&id=41000105199&lang=fr": BookRef("41000105199"),
            "https://www.goodshort.com/drama/engag%C3%A9e-%C3%A0-un-milliardaire-b%C3%A2tard-31000835255":
                BookRef("31000835255", provider="goodshort", slug="engagée-à-un-milliardaire-bâtard"),
        }  # fmt: skip
        for text, ref in cases.items():
            with self.subTest(text=text):
                self.assertEqual(parse_input(text), ref)
        with self.assertRaises(InputError):
            parse_input(base + "page=home&lang=fr")

    def test_bare_ids_and_unknown_hosts_stay_dramabox(self):
        self.assertEqual(parse_input("41000105199"), BookRef("41000105199"))
        self.assertEqual(parse_input("https://share.example.com/drama/41000105199").provider, "dramabox")
        self.assertEqual(BookRef("41000105199").key, "41000105199")

    def test_rejected(self):
        for text in ("https://www.goodshort.com/channel/Hot-List", "goodshort:abc", "https://www.goodshort.com/"):
            with self.subTest(text=text), self.assertRaises(InputError):
                parse_input(text)

    def test_registry(self):
        self.assertEqual(registry.get(None).name, "dramabox")
        self.assertEqual(registry.get("goodshort").label, "GoodShort")
        with self.assertRaises(ValueError):
            registry.get("netflix")


class GoodShortPageTest(unittest.TestCase):
    def test_parse_series_page(self):
        series = goodshort.parse_series_page(goodshort_html(fixture_json("goodshort_state.json")), "31000662271")
        self.assertEqual((series.provider, series.title, series.slug, series.lang), ("goodshort", "Perfect Love", "perfect-love", "en"))
        self.assertEqual(series.episode_count, 56)  # chapterCount, beyond the 5 listed chapters
        self.assertEqual(series.free_numbers, [1, 2, 3])
        self.assertEqual((series.episodes[0].duration_ms, series.episodes[3].duration_ms, series.episodes[9].duration_ms), (118_000, 58_000, None))
        self.assertFalse(series.free_only)
        self.assertEqual(series.free_url_kind, "hls")

    def test_every_chapter_comes_from_the_chapter_api(self):
        with mock.patch.object(goodshort, "CHAPTERS_PAGE_SIZE", 20):  # 3 pages
            http = goodshort_http()
            series = registry.get("goodshort").fetch_series(http, parse_input(GS_URL), None)
        self.assertEqual(series.episode_count, 56)
        self.assertTrue(all(ep.chapter_id and ep.duration_ms for ep in series.episodes))
        self.assertEqual((series.episodes[0].chapter_id, series.episodes[55].chapter_id), ("6439092", "6439147"))
        self.assertEqual((series.episodes[9].duration_ms, series.free_numbers), (60_000, [1, 2, 3]))
        self.assertEqual(sum(url == goodshort.CHAPTERS_API_URL for url, _ in http.calls), 3)

    def test_missing_series(self):
        state = fixture_json("goodshort_state.json")
        state["BookInfoModule"]["nullBook"] = True
        for html in (goodshort_html(state), "<html>rien</html>"):
            with self.assertRaises(errors.SeriesNotFound):
                goodshort.parse_series_page(html, "31000662271")

    def test_without_the_sites_slug_the_api_is_asked(self):
        state = fixture_json("goodshort_state.json")
        answer = {"status": 0, "message": "success", "data": state["BookInfoModule"]}
        provider = registry.get("goodshort")
        for ref in (BookRef("31000662271", provider="goodshort"), BookRef("31000662271", provider="goodshort", slug="autre")):
            with self.subTest(slug=ref.slug):
                http = FakeHttp(pages={
                    goodshort.BOOK_API_URL: lambda payload: answer if payload == {"bookId": "31000662271"} else 500,
                    goodshort.CHAPTERS_API_URL: chapters_api(goodshort_chapters()),
                })  # fmt: skip
                series = provider.fetch_series(http, ref, None)
                self.assertEqual((series.title, series.slug, series.episode_count, series.free_numbers), ("Perfect Love", "perfect-love", 56, [1, 2, 3]))
                self.assertEqual(series.episodes[40].chapter_id, "6439132")
                self.assertEqual(http.calls[-1][0], goodshort.BOOK_API_URL)
        unknown = {"status": 0, "message": "success", "data": {"seo404Vo": {"jumpType": 4}}}
        http = FakeHttp(pages={goodshort.BOOK_API_URL: unknown, goodshort.CHAPTERS_API_URL: chapters_api([])})
        with self.assertRaises(errors.SeriesNotFound):
            provider.fetch_series(http, BookRef("31999999999", provider="goodshort"), None)

    def test_folder_slug_is_ascii(self):
        state = fixture_json("goodshort_state.json")
        state["BookInfoModule"]["book"]["bookResourceUrl"] = "engagée-à-un-milliardaire-bâtard-31000662271"
        series = goodshort.parse_state(state, "31000662271")
        self.assertEqual(series.slug, "engagee-a-un-milliardaire-batard")
        self.assertEqual(pipeline.series_dir_name(series), "goodshort-31000662271-engagee-a-un-milliardaire-batard")
        self.assertRegex(pipeline.series_dir_name(series), library.KEY_RE)  # the library sees the folder
        self.assertEqual(registry.get("goodshort").series_url("31000662271", "engagée-à"), "https://www.goodshort.com/drama/engag%C3%A9e-%C3%A0-31000662271")

    def test_expiry_from_url(self):
        url = "https://v3.goodshort.com/x/ep.m3u8?expiredTime=1791811371&tul=ab"
        self.assertEqual(registry.get("goodshort").expires_at(url), datetime.fromtimestamp(1791811371, tz=timezone.utc))



class GoodShortSourcesTest(unittest.TestCase):
    """Videos from dramafren (every episode), the official free playlist as a last resort."""

    def setUp(self):
        self.series = goodshort_series()

    def resolve(self, http, number):
        return pipeline.resolve_episode(http, self.series, self.series.episodes[number - 1])

    def test_paid_episode_comes_from_dramafren(self):
        http = goodshort_http()
        sources = self.resolve(http, 40)
        self.assertEqual([(s.quality, s.origin, s.kind) for s in sources], [("1080p", "dramafren", "hls"), ("720p", "dramafren", "hls"), ("540p", "dramafren", "hls")])
        self.assertEqual(sources[0].url, f"{GS_PROXY}c6439131.1080P")
        asked = parse_qs(urlparse(http.calls[-1][0]).query)
        self.assertEqual({k: v[0] for k, v in asked.items()}, {"action": "get_video_url", "id": "31000662271", "chap_id": "6439131", "sv": "1", "lang": "en"})

    def test_free_episode_keeps_the_official_playlist_last(self):
        sources = self.resolve(goodshort_http(), 1)
        self.assertEqual([(s.quality, s.origin) for s in sources], [("1080p", "dramafren"), ("720p", "dramafren"), ("540p", "dramafren"), ("", "official")])
        self.assertEqual(sources[-1].url, self.series.episodes[0].free_url)
        self.assertEqual(self.resolve(goodshort_http(locked=[6439092]), 1)[0].origin, "official")

    def test_other_servers_are_asked(self):
        http = goodshort_http(locked_on_server1=[6439131])
        self.assertEqual(self.resolve(http, 40)[0].quality, "1080p")
        self.assertEqual([parse_qs(urlparse(u).query)["sv"][0] for u, _ in http.calls], ["1", "2"])

        http = goodshort_http(locked=[6439131])
        with self.assertRaises(errors.ResolveError) as ctx:
            self.resolve(http, 40)
        self.assertEqual(ctx.exception.code, errors.EP_UNAVAILABLE)
        self.assertEqual(len(http.calls), 3)  # servers 1, 2 and 3

    def test_network_error_is_not_asked_three_times(self):
        http = goodshort_http()
        http.pages[dramafren.GOODSHORT_ENDPOINT] = 502
        with self.assertRaises(errors.ResolveError) as ctx:
            self.resolve(http, 40)
        self.assertEqual((ctx.exception.code, len(http.calls)), (errors.NETWORK, 1))
        self.assertEqual(self.resolve(http, 2)[0].origin, "official")  # a free episode still has its playlist

    def test_episode_without_chapter_id(self):
        series = goodshort.parse_series_page(goodshort_html(fixture_json("goodshort_state.json")), "31000662271")
        with self.assertRaises(errors.ResolveError) as ctx:
            pipeline.resolve_episode(goodshort_http(), series, series.episodes[20])
        self.assertEqual(ctx.exception.code, errors.EP_UNAVAILABLE)

    def test_availability_asks_for_the_last_episode(self):
        provider = registry.get("goodshort")
        http = goodshort_http()
        found = provider.availability(http, self.series, None, None)
        self.assertEqual((found.available, found.qualities), (True, ["1080p", "720p", "540p"]))
        self.assertEqual(parse_qs(urlparse(http.calls[-1][0]).query)["chap_id"], ["6439147"])
        found = provider.availability(goodshort_http(locked=[6439147]), self.series, None, None)
        self.assertEqual((found.available, found.error.code), (False, errors.EP_UNAVAILABLE))

    def test_expired_free_playlist_is_read_again(self):
        ep = self.series.episodes[0]
        fresh = ep.free_url
        ep.free_url = fresh.replace("expiredTime=4102444800", "expiredTime=1000000000")
        http = goodshort_http(locked=[6439092])
        self.assertEqual(self.resolve(http, 1)[0].url, fresh)
        self.assertIn(goodshort.CHAPTERS_API_URL, [u for u, _ in http.calls])


class HlsTest(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.dir = Path(tmp.name)

    def test_master_playlist_picks_the_best_variant(self):
        master = "\n".join([
            "#EXTM3U",
            "#EXT-X-STREAM-INF:BANDWIDTH=800000,RESOLUTION=540x960", "low/index.m3u8",
            "#EXT-X-STREAM-INF:BANDWIDTH=2400000,RESOLUTION=1080x1920", "high/index.m3u8",
        ])  # fmt: skip
        http = FakeHttp(pages={
            "https://cdn.test/v/master.m3u8": master,
            "https://cdn.test/v/high/index.m3u8": media_playlist([("a.ts", 2.0)]),
            "https://cdn.test/v/high/a.ts": b"2.0|",
        })  # fmt: skip
        size = hls.download_hls(http, "https://cdn.test/v/master.m3u8", self.dir / "E001.mp4", 2000, remux=fake_remux)
        self.assertEqual(size, (self.dir / "E001.mp4").stat().st_size)
        self.assertEqual(sorted(p.name for p in self.dir.iterdir()), ["E001.mp4"])  # no .part left

    def test_encrypted_stream_is_refused(self):
        text = media_playlist([("a.ts", 2.0)], key='#EXT-X-KEY:METHOD=AES-128,URI="https://cdn.test/key"')
        with self.assertRaises(IntegrityError) as ctx:
            hls.parse_playlist(text, "https://cdn.test/v/index.m3u8")
        self.assertEqual(ctx.exception.code, errors.HLS_UNSUPPORTED)

    def test_resume_after_an_interruption(self):
        url = "https://cdn.test/v/index.m3u8"
        pages = {url: media_playlist([("a.ts", 2.0), ("b.ts", 2.0), ("c.ts", 1.5)])}
        pages.update({f"https://cdn.test/v/{n}.ts": f"{s}|".encode() for n, s in (("a", 2.0), ("b", 2.0), ("c", 1.5))})
        http = FakeHttp(pages=pages)
        dest = self.dir / "E002.mp4"
        # a previous run finished a.ts, then was cut in the middle of b.ts
        (self.dir / "E002.index.ts.part").write_bytes(b"2.0|2.")
        (self.dir / "E002.index.idx.part").write_text("4\n", encoding="ascii")
        hls.download_hls(http, url, dest, 5500, remux=fake_remux)
        fetched = [u for u, _ in http.calls if u.endswith(".ts")]
        self.assertEqual(fetched, ["https://cdn.test/v/b.ts", "https://cdn.test/v/c.ts"])
        self.assertTrue(dest.exists())

    def test_renditions_behind_one_proxy_path_are_kept_apart(self):
        """dramafren's playlists all live at /proxy: a 1080p .part must not be resumed as 720p."""
        url = GS_PROXY + "c1.720P"
        http = FakeHttp(pages={GS_PROXY: dramafren_proxy({"1": [2.0, 1.5]})})
        (self.dir / "E001.proxy.1080p.ts.part").write_bytes(b"9.0|")
        (self.dir / "E001.proxy.1080p.idx.part").write_text("4\n", encoding="ascii")
        hls.download_hls(http, url, self.dir / "E001.mp4", 3500, remux=fake_remux, rendition="720p")
        self.assertEqual(len(http.calls), 3)  # the playlist and both segments: nothing resumed
        self.assertEqual(sorted(p.name for p in self.dir.iterdir()), ["E001.mp4"])  # the 1080p leftovers are gone

    def test_wrong_duration_is_rejected(self):
        url = "https://cdn.test/v/index.m3u8"
        http = FakeHttp(pages={url: media_playlist([("a.ts", 2.0)]), "https://cdn.test/v/a.ts": b"2.0|"})
        with self.assertRaises(IntegrityError) as ctx:
            hls.download_hls(http, url, self.dir / "E001.mp4", 30_000, remux=fake_remux)
        self.assertEqual(ctx.exception.code, errors.DURATION_MISMATCH)


class GoodShortFetchTest(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.out = Path(tmp.name)
        patcher = mock.patch("shortdramagen.hls._ffmpeg_remux", return_value=fake_remux)
        patcher.start()
        self.addCleanup(patcher.stop)

    def fetch(self, http, **opts):
        options = pipeline.FetchOptions(out_dir=self.out, api_interval=0, **opts)
        return pipeline.fetch(http, parse_input(GS_URL), options, log=lambda _: None)

    def manifest(self, result):
        return json.loads((result.series_dir / "manifest.json").read_text(encoding="utf-8"))

    def test_everything_means_every_episode(self):
        result = self.fetch(goodshort_http())
        self.assertEqual((result.done, result.failed), (list(range(1, 57)), {}))
        self.assertEqual(result.series_dir.name, "goodshort-31000662271-perfect-love")
        manifest = self.manifest(result)
        self.assertEqual((manifest["platform"], manifest["free_only"], manifest["episode_count"]), ("goodshort", False, 56))
        self.assertIsNone(manifest["requested"]["episodes"])
        paid = next(e for e in manifest["episodes"] if e["number"] == 40)
        self.assertEqual((paid["quality"], paid["origin"]), ("1080p", "dramafren"))
        self.assertEqual(len(list(result.series_dir.glob("E*.mp4"))), 56)

        library = LibraryIndex(self.out)
        library.refresh(force=True)
        group = library.library()["groups"][0]
        self.assertEqual((group["ref"], group["provider_label"]), ("goodshort:31000662271", "GoodShort"))
        self.assertEqual(group["versions"][0]["state"], "complete")

    def test_quality_and_fallbacks(self):
        # episode 2 (free): dramafren says no, the official playlist remains; episode 4 (paid): nothing
        result = self.fetch(goodshort_http(locked=[6439093, 6439095]), episodes=[(1, 4)], quality="720p")
        self.assertEqual((result.done, result.failed_codes), ([1, 2, 3], {4: errors.EP_UNAVAILABLE}))
        episodes = {e["number"]: e for e in self.manifest(result)["episodes"]}
        self.assertEqual((episodes[1]["quality"], episodes[1]["origin"]), ("720p", "dramafren"))
        self.assertEqual(episodes[2]["origin"], "official")


class GoodShortServerTest(LiveTest):
    """The web interface with a GoodShort link: preview, cover, queue, library."""

    def make_http(self):
        http = goodshort_http()
        http.pages[fixture_json("goodshort_state.json")["BookInfoModule"]["book"]["cover"]] = b"\xff\xd8\xff\xe0 jpeg"
        return http

    def setUp(self):
        patcher = mock.patch("shortdramagen.hls._ffmpeg_remux", return_value=fake_remux)
        patcher.start()
        self.addCleanup(patcher.stop)
        super().setUp()

    def test_preview_then_download(self):
        status, data = self.call("POST", "/api/preview", {"input": GS_URL})
        self.assertEqual(status, 200, data)
        self.assertEqual((data["provider"], data["ref"], data["free_only"]), ("goodshort", "goodshort:31000662271", False))
        self.assertEqual((data["free_episodes"], data["availability"]["source"], data["estimate"]), ([1, 2, 3], "ok", {}))
        self.assertEqual((data["availability"]["checked_episode"], data["availability"]["qualities"]), (56, ["1080p", "720p", "540p"]))
        self.assertEqual(data["cover_url"], "/media/preview/goodshort:31000662271/vo/cover")
        conn = http.client.HTTPConnection("127.0.0.1", self.port, timeout=5)
        conn.request("GET", data["cover_url"], headers={"Host": f"127.0.0.1:{self.port}"})
        resp = conn.getresponse()
        self.assertEqual((resp.status, resp.read()[:2]), (200, b"\xff\xd8"))
        conn.close()

        status, data = self.call("POST", "/api/jobs", {"kind": "fetch", "input": GS_URL})
        self.assertEqual(status, 201, data)
        self.assertEqual((data["job"]["provider"], data["job"]["ref"]), ("goodshort", "goodshort:31000662271"))
        job = self.wait_job(data["job"]["id"], "done", "failed")
        self.assertEqual(job["status"], "done", job)
        status, lib = self.call("GET", "/api/library")
        group = lib["groups"][0]
        self.assertEqual((group["ref"], group["versions"][0]["state"]), ("goodshort:31000662271", "complete"))
        status, data = self.call("POST", "/api/jobs", {"kind": "fetch", "input": "goodshort:31000662271"})
        self.assertEqual(status, 201, data)  # a finished job does not block a new one on the same series


class JobRefTest(unittest.TestCase):
    def test_the_typed_link_gives_back_the_slug(self):
        job = Job("j1", "fetch", {"input": GS_URL}, book_id="31000662271", provider="goodshort")
        self.assertEqual(job.book_ref(), BookRef("31000662271", provider="goodshort", slug="perfect-love"))
        self.assertEqual(job.to_dict()["ref"], "goodshort:31000662271")
        old = Job.restore({"id": "j2", "kind": "fetch", "params": {"input": "41000105199"}, "book_id": "41000105199"})
        self.assertEqual((old.provider, old.book_ref()), ("dramabox", BookRef("41000105199")))


if __name__ == "__main__":
    unittest.main()
