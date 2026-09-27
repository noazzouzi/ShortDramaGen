"""Step 0: a controllable engine (events, cancellation, force, strict quality, codes, manifest v2)."""

import errno
import json
import tempfile
import threading
import unittest
import urllib.error
from pathlib import Path
from unittest import mock

from shortdramagen import errors, fsutil, inputs, pipeline
from shortdramagen.http import HttpStatusError
from shortdramagen.manifest import Manifest
from shortdramagen.models import BookRef

from fakes import OFFICIAL_EN_URL, cdn_url, fixture_json, make_mp4, official_html, series_http

BOOK = BookRef("41000105199")
COVER_URL = fixture_json("official_en.json")["bookInfo"]["cover"]


class Recorder:
    """on_event handler that keeps every event (thread-safe)."""

    def __init__(self, on=None):
        self.events = []
        self._lock = threading.Lock()
        self._on = on

    def __call__(self, name, data):
        with self._lock:
            self.events.append((name, data))
        if self._on:
            self._on(name, data)

    def names(self):
        return [n for n, _ in self.events]

    def of(self, name):
        return [d for n, d in self.events if n == name]


class TempDirTest(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.tmp = Path(self._tmp.name)
        patcher = mock.patch.object(pipeline, "RETRY_BASE_DELAY", 0)
        patcher.start()
        self.addCleanup(patcher.stop)

    def tearDown(self):
        self._tmp.cleanup()

    def fetch(self, http, control=None, **options):
        opts = pipeline.FetchOptions(out_dir=self.tmp, api_interval=0, **options)
        return pipeline.fetch(http, BOOK, opts, log=lambda _: None, control=control)

    def manifest(self):
        return json.loads((self.tmp / "41000105199-one-night-to-forever" / "manifest.json").read_text(encoding="utf-8"))

    def status(self):
        return {e["number"]: e["status"] for e in self.manifest()["episodes"]}


class InputsTest(unittest.TestCase):
    def test_parse_episodes(self):
        self.assertEqual(inputs.parse_episodes("1–10 , 28,50 -"), [(1, 10), (28, 28), (50, None)])
        self.assertIsNone(inputs.parse_episodes("  "))
        for bad in ("a", "3-1"):
            with self.subTest(bad=bad), self.assertRaises(inputs.InputError):
                inputs.parse_episodes(bad)


class ErrorCodesTest(unittest.TestCase):
    def test_code_for(self):
        cases = [
            (OSError(errno.ENOSPC, "No space left on device"), errors.DISK_FULL),
            (PermissionError(13, "denied"), errors.FILE_LOCKED),
            (urllib.error.URLError("down"), errors.NETWORK),
            (HttpStatusError("u", 502), errors.NETWORK),
            (ValueError("x"), errors.UNKNOWN),
        ]
        for exc, code in cases:
            with self.subTest(exc=exc):
                self.assertEqual(errors.code_for(exc), code)


def locked_for(times):
    """os.replace that fails like Windows while another program has the file open."""
    real, calls = fsutil.os.replace, []

    def replace(src, dst):
        calls.append((Path(src).name, Path(dst).name))
        if len(calls) <= times:
            raise PermissionError(13, "Access is denied", str(src), None, str(dst))
        real(src, dst)

    return replace, calls


class FsutilTest(TempDirTest):
    def test_replace_waits_for_the_lock(self):
        (self.tmp / "a").write_text("new")
        (self.tmp / "b").write_text("old")
        replace, calls = locked_for(2)
        with mock.patch.object(fsutil.os, "replace", replace), mock.patch.object(fsutil.time, "sleep") as sleep:
            fsutil.replace(self.tmp / "a", self.tmp / "b")
        self.assertEqual((self.tmp / "b").read_text(), "new")
        self.assertEqual(len(calls), 3)
        self.assertEqual([c.args[0] for c in sleep.call_args_list], list(fsutil.DELAYS[:2]))

    def test_replace_gives_up_after_about_3_seconds(self):
        (self.tmp / "a").write_text("new")
        replace, calls = locked_for(100)
        with mock.patch.object(fsutil.os, "replace", replace), mock.patch.object(fsutil.time, "sleep") as sleep:
            with self.assertRaises(PermissionError):
                fsutil.replace(self.tmp / "a", self.tmp / "b")
        self.assertEqual(len(calls), len(fsutil.DELAYS) + 1)
        self.assertAlmostEqual(sum(c.args[0] for c in sleep.call_args_list), 3.0, delta=0.1)


class ManifestTest(TempDirTest):
    def series(self):
        from shortdramagen import official

        return official.parse_page_props(fixture_json("official_en.json"), "41000105199")

    def test_save_survives_a_windows_lock(self):
        # sdg ui reading the manifest, or the antivirus scanning it, at the moment it is replaced
        m = Manifest.open(self.tmp, self.series(), {"quality": "best"})
        replace, calls = locked_for(3)
        with mock.patch.object(fsutil.os, "replace", replace), mock.patch.object(fsutil.time, "sleep"):
            m.update(1, status="done")
        self.assertEqual(calls[-1], ("manifest.json.tmp", "manifest.json"))
        self.assertEqual(Manifest.load(self.tmp).episode(1)["status"], "done")
        self.assertFalse((self.tmp / "manifest.json.tmp").exists())

    def test_v2_fields_listener_and_stale_downloads(self):
        calls = []
        m = Manifest.open(self.tmp, self.series(), {"quality": "best"}, lambda _m, n: calls.append(n))
        created = m.data["created_at"]
        self.assertEqual(m.data["schema_version"], 2)
        self.assertEqual(m.data["title_vo"], "One Night to Forever")
        self.assertEqual(m.data["requested"], {"quality": "best"})
        m.update(2, status="failed", error="boom", error_code="network")
        m.update(28, status="downloading")
        m.count_attempt(28)
        self.assertIn(None, calls)
        self.assertEqual(calls.count(28), 2)

        m.update(2, status="downloading")  # a new try: the old error no longer applies
        self.assertNotIn("error", m.episode(2))
        m.update(2, status="done")
        self.assertIn("finished_at", m.episode(2))

        reopened = Manifest.open(self.tmp, self.series())
        self.assertEqual(reopened.episode(28)["status"], "pending")  # interrupted run
        self.assertEqual(reopened.episode(28)["attempts"], 1)
        self.assertEqual(reopened.data["created_at"], created)
        self.assertEqual(reopened.data["requested"], {"quality": "best"})

    def test_corrupt_manifest_is_set_aside(self):
        (self.tmp / "manifest.json").write_text("{not json", encoding="utf-8")
        m = Manifest.open(self.tmp, self.series())
        self.assertEqual(len(m.data["episodes"]), 3)
        self.assertEqual(len(list(self.tmp.glob("manifest.corrupt-*.json"))), 1)


class FetchControlTest(TempDirTest):
    def test_events_and_cover(self):
        http = series_http()
        http.pages[COVER_URL] = b"\xff\xd8\xff\xe0 fake jpeg"
        rec = Recorder()
        result = self.fetch(http, pipeline.FetchControl(on_event=rec))
        names = rec.names()
        self.assertEqual(names[0], "series_loaded")
        self.assertEqual(names[-1], "fetch_finished")
        self.assertEqual(sorted(d["n"] for d in rec.of("episode_done")), [1, 2, 28])
        self.assertTrue(rec.of("episode_progress"))
        self.assertEqual(rec.of("series_loaded")[0]["series_key"], "41000105199-one-night-to-forever")
        self.assertEqual(rec.of("fetch_finished")[0], {"done": [1, 2, 28], "skipped": [], "failed": {},
                                                       "cancelled": False, "stop_reason": None})
        self.assertEqual((result.series_dir / "cover.jpg").read_bytes()[:2], b"\xff\xd8")
        manifest = self.manifest()
        self.assertEqual(manifest["cover_file"], "cover.jpg")
        self.assertEqual({e["attempts"] for e in manifest["episodes"]}, {1})

    def test_external_stop_leaves_episodes_pending_and_resumable(self):
        http = series_http(payload=700_000)  # several 256 KiB chunks per episode
        control = pipeline.FetchControl()
        control.on_event = Recorder(on=lambda name, _d: name == "episode_progress" and control.stop.set())
        result = self.fetch(http, control, jobs=1)
        self.assertTrue(result.cancelled)
        self.assertEqual(result.done, [])
        self.assertNotIn("downloading", self.status().values())
        self.assertEqual(set(self.status().values()), {"pending"})
        self.assertEqual(len(list(result.series_dir.glob("*.part"))), 1)  # kept for the next run
        self.assertTrue(control.on_event.of("episode_cancelled"))

        again = self.fetch(series_http(payload=700_000))  # a new run resumes and finishes
        self.assertEqual((again.done, again.cancelled), ([1, 2, 28], False))
        self.assertEqual(list(again.series_dir.glob("*.part")), [])

    def test_force_redownloads_a_valid_file(self):
        self.fetch(series_http())
        rec = Recorder()
        result = self.fetch(series_http(), pipeline.FetchControl(force=frozenset({1}), on_event=rec), quality="720p")
        self.assertEqual((result.done, result.skipped), ([1], [2, 28]))
        self.assertEqual(rec.of("episode_done")[0]["quality"], "720p")
        episode = self.manifest()["episodes"][0]
        self.assertEqual((episode["quality"], episode["attempts"]), ("720p", 2))

    def test_strict_quality_and_fallback(self):
        strict = self.fetch(series_http(), pipeline.FetchControl(strict_quality=True), quality="540p")
        self.assertEqual(strict.failed_codes, {1: "quality_unavailable", 2: "quality_unavailable", 28: "quality_unavailable"})
        self.assertIn("proposées : 720p", strict.failed[28])

        rec = Recorder()
        loose = self.fetch(series_http(), pipeline.FetchControl(on_event=rec), quality="540p")
        self.assertEqual(loose.done, [1, 2, 28])
        self.assertEqual({(d["requested"], d["got"]) for d in rec.of("quality_fallback")}, {("540p", "720p")})
        self.assertEqual(self.manifest()["episodes"][2]["quality_requested"], "540p")

    def test_error_codes_in_manifest(self):
        http = series_http({28: {"ok": False, "error": "Video unavailable"}})
        wrong = make_mp4(10, payload=5_000)  # right URL, wrong duration
        for q in ("720p", "1080p"):
            http.files[cdn_url("41000105199", "577159337", q)] = wrong
        result = self.fetch(http)
        self.assertEqual(result.failed_codes, {28: "ep_unavailable"})
        self.assertEqual(result.done, [1, 2])  # episode 2: dramafren files rejected, official free MP4 used
        episodes = {e["number"]: e for e in self.manifest()["episodes"]}
        self.assertEqual((episodes[28]["status"], episodes[28]["error_code"]), ("failed", "ep_unavailable"))
        self.assertEqual(episodes[2]["origin"], "official")

    def test_retries_then_duration_mismatch(self):
        http = series_http()
        wrong = make_mp4(10, payload=5_000)
        for q in ("720p", "1080p"):
            http.files[cdn_url("41000105199", "577159363", q)] = wrong
        rec = Recorder()
        result = self.fetch(http, pipeline.FetchControl(on_event=rec), episodes=[(28, 28)])
        self.assertEqual(result.failed_codes, {28: "duration_mismatch"})
        self.assertEqual(len(rec.of("episode_retry")), pipeline.MAX_ATTEMPTS - 1)
        self.assertEqual(self.manifest()["episodes"][2]["attempts"], pipeline.MAX_ATTEMPTS)

    def test_disk_full_stops_the_run(self):
        http = series_http()
        full = OSError(errno.ENOSPC, "No space left on device")
        rec = Recorder()
        with mock.patch("shortdramagen.pipeline.download", side_effect=full):
            result = self.fetch(http, pipeline.FetchControl(on_event=rec), jobs=1)
        self.assertEqual((result.stop_reason, result.cancelled), ("disk_full", True))
        self.assertEqual(result.failed, {})
        self.assertEqual(set(self.status().values()), {"pending"})
        self.assertEqual(len(rec.of("disk_full")), 1)

    def test_selection_clipped_event(self):
        rec = Recorder()
        self.fetch(series_http(), pipeline.FetchControl(on_event=rec), episodes=[(1, 1), (70, 80)])
        self.assertEqual(rec.of("selection_clipped"), [{"episode_count": 3, "ignored": ["70-80"]}])


class PreviewTest(unittest.TestCase):
    def test_preview_writes_nothing(self):
        http = series_http()
        preview = pipeline.preview_series(http, BookRef("41000105199", episode=28))
        data = preview.to_dict()
        self.assertTrue(preview.available)
        self.assertEqual(data["availability"]["qualities"], ["1080p", "720p"])
        self.assertEqual((data["episode_count"], data["episode_ref"], data["free_episodes"]), (3, 28, [1, 2]))
        self.assertEqual(data["estimate"]["1080p"]["bytes"], 3 * pipeline.BYTES_PER_EPISODE_1080P)
        self.assertFalse(any("hwztakavideoto" in url for url, _ in http.calls))  # no download

    def test_preview_source_unavailable_and_lang_fallback(self):
        http = series_http({28: {"ok": False, "error": "Video unavailable"}})
        props = fixture_json("official_en.json")
        props["locale"] = "de"
        http.pages["https://www.dramaboxdb.com/de/movie/41000105199/"] = official_html(props)
        rec = Recorder()
        preview = pipeline.preview_series(http, BOOK, "de", pipeline.FetchControl(on_event=rec))
        self.assertFalse(preview.available)
        self.assertEqual(preview.source_error_code, "ep_unavailable")
        self.assertEqual(preview.series.lang, "en")  # no German dub: the original version
        self.assertEqual(rec.of("lang_fallback")[0]["requested"], "de")

    def test_preview_never_probes(self):
        from shortdramagen import official

        http = series_http()
        del http.pages[OFFICIAL_EN_URL]
        with self.assertRaises(official.SeriesNotFound):
            pipeline.preview_series(http, BOOK)


if __name__ == "__main__":
    unittest.main()
