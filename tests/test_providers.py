"""Platforms: link parsing, GoodShort metadata, HLS episodes and free-only downloads (offline)."""

import http.client
import json
import tempfile
import unittest
from datetime import datetime, timezone
from pathlib import Path
from unittest import mock

from fakes import FakeHttp, fixture_json, make_mp4
from test_jobs import LiveTest

from shortdramagen import errors, hls, pipeline
from shortdramagen.download import IntegrityError
from shortdramagen.inputs import InputError, parse_input
from shortdramagen.jobs import Job
from shortdramagen.library import LibraryIndex
from shortdramagen.models import BookRef
from shortdramagen.providers import goodshort, registry

GS_URL = "https://www.goodshort.com/drama/perfect-love-31000662271"


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


def goodshort_http() -> FakeHttp:
    """The fixture series page plus, for each free episode, a playlist of fake segments."""
    state = fixture_json("goodshort_state.json")
    pages: dict = {GS_URL: goodshort_html(state)}
    for ch in state["BookInfoModule"]["chapterVoList"]:
        url = ch.get("m3u8Path")
        if not url:
            continue
        base = url.split("?")[0].rsplit("/", 1)[0]
        parts = [(f"s{i}.ts", 5.0) for i in range(ch["playTime"] // 5)] + [("last.ts", ch["playTime"] % 5 + 0.3)]
        pages[url.split("?")[0]] = media_playlist(parts)
        for name, seconds in parts:
            pages[f"{base}/{name}"] = f"{seconds}|".encode()
    return FakeHttp(pages=pages)


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
        self.assertTrue(series.free_only)
        self.assertEqual(series.free_url_kind, "hls")

    def test_missing_series(self):
        state = fixture_json("goodshort_state.json")
        state["BookInfoModule"]["nullBook"] = True
        for html in (goodshort_html(state), "<html>rien</html>"):
            with self.assertRaises(errors.SeriesNotFound):
                goodshort.parse_series_page(html, "31000662271")

    def test_expiry_from_url(self):
        url = "https://v3.goodshort.com/x/ep.m3u8?expiredTime=1791811371&tul=ab"
        self.assertEqual(registry.get("goodshort").expires_at(url), datetime.fromtimestamp(1791811371, tz=timezone.utc))

    def test_paid_episode_is_unavailable(self):
        series = goodshort.parse_series_page(goodshort_html(fixture_json("goodshort_state.json")), "31000662271")
        with self.assertRaises(errors.ResolveError) as ctx:
            pipeline.resolve_episode(FakeHttp(), series, series.episodes[4])
        self.assertEqual(ctx.exception.code, errors.EP_UNAVAILABLE)


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

    def test_wrong_duration_is_rejected(self):
        url = "https://cdn.test/v/index.m3u8"
        http = FakeHttp(pages={url: media_playlist([("a.ts", 2.0)]), "https://cdn.test/v/a.ts": b"2.0|"})
        with self.assertRaises(IntegrityError) as ctx:
            hls.download_hls(http, url, self.dir / "E001.mp4", 30_000, remux=fake_remux)
        self.assertEqual(ctx.exception.code, errors.DURATION_MISMATCH)


class FreeOnlyFetchTest(unittest.TestCase):
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

    def test_everything_means_the_free_episodes(self):
        result = self.fetch(goodshort_http())
        self.assertEqual((result.done, result.failed), ([1, 2, 3], {}))
        self.assertEqual(result.series_dir.name, "goodshort-31000662271-perfect-love")
        manifest = json.loads((result.series_dir / "manifest.json").read_text(encoding="utf-8"))
        self.assertEqual((manifest["platform"], manifest["free_only"], manifest["episode_count"]), ("goodshort", True, 56))
        self.assertEqual(manifest["requested"]["episodes"], [[1, 3]])
        self.assertEqual(sorted(p.name for p in result.series_dir.glob("E*")), ["E001.mp4", "E002.mp4", "E003.mp4"])

        library = LibraryIndex(self.out)
        library.refresh(force=True)
        group = library.library()["groups"][0]
        self.assertEqual((group["ref"], group["provider_label"]), ("goodshort:31000662271", "GoodShort"))
        self.assertEqual(group["versions"][0]["state"], "complete")  # paid episodes were never requested

    def test_a_paid_episode_asked_for_fails_cleanly(self):
        result = self.fetch(goodshort_http(), episodes=[(3, 4)])
        self.assertEqual(result.done, [3])
        self.assertEqual(result.failed_codes, {4: errors.EP_UNAVAILABLE})


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
        self.assertEqual((data["provider"], data["ref"], data["free_only"]), ("goodshort", "goodshort:31000662271", True))
        self.assertEqual((data["free_episodes"], data["availability"]["source"], data["estimate"]), ([1, 2, 3], "ok", {}))
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
