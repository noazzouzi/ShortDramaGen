"""Step 2: jobs and real time (event bus, queue, pause/resume/cancel, restart, repair, film,
trash, settings, preview, server-sent events). Everything runs offline against FakeHttp."""

import http.client
import io
import json
import tempfile
import threading
import time
import unittest
import urllib.error
from contextlib import contextmanager
from pathlib import Path
from unittest import mock

from shortdramagen import errors, film, jobs, pipeline
from shortdramagen.connectivity import Connectivity
from shortdramagen.events import EventBus
from shortdramagen.jobs import Job, JobStore
from shortdramagen.library import LibraryIndex
from shortdramagen.server import security
from shortdramagen.server.app import App, create_server
from shortdramagen.settings import Settings

from fakes import FakeHttp, fixture_json, official_html, series_http
from test_film import episode_bytes

KEY = "41000105199-one-night-to-forever"
COVER_URL = fixture_json("official_en.json")["bookInfo"]["cover"]


class SlowBody(io.BytesIO):
    def __init__(self, data: bytes, delay: float):
        super().__init__(data)
        self.delay = delay

    def read(self, n=-1):
        time.sleep(self.delay)
        return super().read(n)


class SlowHttp(FakeHttp):
    """Downloads take a while (each 256 KiB block waits), so a job can be paused mid-transfer."""

    delay = 0.08

    @contextmanager
    def stream(self, url, headers=None):
        with super().stream(url, headers) as (status, h, body):
            yield status, h, SlowBody(body.read(), self.delay)


def slow_http(**kwargs) -> SlowHttp:
    fast = series_http(payload=kwargs.pop("payload", 3_000_000), **kwargs)
    return SlowHttp(pages=fast.pages, files=fast.files)


class EventBusTest(unittest.TestCase):
    def test_replay_snapshot_and_progress(self):
        bus = EventBus(buffer_size=3)
        sub, missed = bus.subscribe()
        self.assertIsNone(missed)  # no id: the client needs a snapshot
        for i in range(5):
            bus.publish("job", {"i": i})
        bus.publish("progress", {"p": 1}, replay=False)
        received = [sub.get(0.1) for _ in range(6)]
        self.assertEqual([e.type for e in received], ["job"] * 5 + ["progress"])
        self.assertEqual(received[-1].id, None)
        self.assertEqual(bus.last_id, 5)

        _, missed = bus.subscribe(last_id=3)  # still in the buffer (3, 4, 5 kept)
        self.assertEqual([e.data["i"] for e in missed], [3, 4])
        _, missed = bus.subscribe(last_id=1)  # dropped: snapshot
        self.assertIsNone(missed)
        self.assertIn(b"id: 5\nevent: job\ndata: {\"i\":4}\n\n", received[4].encode())

    def test_slow_subscriber_is_dropped(self):
        bus = EventBus()
        sub, _ = bus.subscribe()
        with mock.patch("shortdramagen.events.SUBSCRIBER_QUEUE", 2):
            slow, _ = bus.subscribe()
        for i in range(4):
            bus.publish("job", {"i": i})
        self.assertTrue(slow.closed and slow.overflowed)
        self.assertFalse(sub.closed)
        self.assertEqual(bus.client_count, 1)


class JobStoreTest(unittest.TestCase):
    def test_restart_puts_interrupted_jobs_back_first(self):
        with tempfile.TemporaryDirectory() as tmp:
            store = JobStore(Path(tmp))
            for i, status in enumerate(["queued", "running", "paused", "cancelling", "done"]):
                job = Job(f"j-00000{i}", "fetch", {}, status=status, book_id=str(i))
                store.jobs[job.id] = job
                store.order.append(job.id)
            store.save()

            again = JobStore(Path(tmp))
            self.assertEqual(again.load(resume=True), ["j-000001"])
            self.assertEqual(again.order[0], "j-000001")
            self.assertEqual({j.id: j.status for j in again.jobs.values()}, {
                "j-000000": "queued", "j-000001": "queued", "j-000002": "paused",
                "j-000003": "cancelled", "j-000004": "done",
            })  # fmt: skip
            no_resume = JobStore(Path(tmp))
            no_resume.load(resume=False)
            self.assertEqual(no_resume.jobs["j-000001"].status, "interrupted")

            store.path.write_text("{broken")
            broken = JobStore(Path(tmp))
            broken.load(resume=True)
            self.assertEqual(broken.jobs, {})
            self.assertTrue(store.path.with_suffix(".bad").exists())


class LiveTest(unittest.TestCase):
    """A real server on a free port, jobs run by the real runner against FakeHttp."""

    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        tmp = Path(self._tmp.name)
        self.state = tmp / "state"
        self.root = tmp / "downloads"
        self.root.mkdir()
        self.online = [True, True]
        patches = [
            mock.patch.object(pipeline, "RETRY_BASE_DELAY", 0),
            mock.patch.object(jobs, "OFFLINE_RECHECK", 0.1),
        ]
        for p in patches:
            p.start()
            self.addCleanup(p.stop)
        self.boot(self.make_http())

    def make_http(self):
        return series_http()

    def boot(self, http):
        self.http = http
        self.settings = Settings(self.state)
        self.settings.update({"downloads_dir": str(self.root)})
        index = LibraryIndex(self.root)
        index.refresh(force=True)
        self.app = App(
            self.settings, index, "s" * 43, http=http, state=self.state,
            connectivity=Connectivity(probe=lambda: tuple(self.online)),
            find_ffmpeg=lambda path: "ffmpeg", limiter=pipeline.RateLimiter(0),
        )  # fmt: skip
        self.app.start()
        self.server = create_server(self.app, 0)
        self.port = self.server.server_address[1]
        threading.Thread(target=self.server.serve_forever, kwargs={"poll_interval": 0.05}, daemon=True).start()

    def halt(self):
        self.server.shutdown()
        self.app.close()
        self.server.server_close()

    def tearDown(self):
        self.halt()
        self._tmp.cleanup()

    def call(self, method, path, data=None, headers=None, raw=None):
        conn = http.client.HTTPConnection("127.0.0.1", self.port, timeout=10)
        h = {"Host": f"127.0.0.1:{self.port}", security.TOKEN_HEADER: self.app.token}
        body = raw
        if data is not None:
            body = json.dumps(data).encode()
            h["Content-Type"] = "application/json"
        h.update(headers or {})
        conn.request(method, path, body=body, headers=h)
        resp = conn.getresponse()
        text = resp.read()
        conn.close()
        return resp.status, json.loads(text) if text else None

    def wait(self, predicate, timeout=15.0, what="condition"):
        deadline = time.monotonic() + timeout
        while time.monotonic() < deadline:
            value = predicate()
            if value:
                return value
            time.sleep(0.02)
        self.fail(f"timeout waiting for {what}")

    def wait_job(self, job_id, *statuses, timeout=15.0) -> dict:
        def done():
            job = self.call("GET", f"/api/jobs/{job_id}")[1]["job"]
            return job if job["status"] in statuses else None

        return self.wait(done, timeout, f"job {job_id} in {statuses}")

    def fetch_job(self, **extra) -> str:
        status, data = self.call("POST", "/api/jobs", {"kind": "fetch", "input": "41000105199", **extra})
        self.assertEqual(status, 201, data)
        return data["job"]["id"]

    def manifest(self, key=KEY) -> dict:
        return json.loads((self.root / key / "manifest.json").read_text(encoding="utf-8"))

    def statuses(self, key=KEY) -> dict:
        return {e["n"]: e["status"] for e in self.call("GET", f"/api/series/{key}")[1]["episodes"]}


class FetchJobTest(LiveTest):
    def test_download_job_to_the_end(self):
        job_id = self.fetch_job()
        job = self.wait_job(job_id, "done")
        self.assertEqual(job["series_key"], KEY)
        self.assertEqual(job["result"]["done"], [1, 2, 28])
        self.assertEqual(job["result"]["failed"], {})
        self.assertTrue(any("Terminé" in line for line in job["log"]))
        self.assertEqual(set(self.statuses().values()), {"done"})
        status, jobs_list = self.call("GET", "/api/jobs")
        self.assertEqual([j["id"] for j in jobs_list["history"]], [job_id])
        self.assertEqual(self.call("DELETE", f"/api/jobs/{job_id}")[0], 204)
        self.assertEqual(self.call("GET", f"/api/jobs/{job_id}")[0], 404)

    def test_validation(self):
        cases = [
            ({"raw": b'{"kind": "fetch"}'}, 415),
            ({"raw": b"{oops", "headers": {"Content-Type": "application/json"}}, 400),
            ({"data": {"kind": "other"}}, 422),
            ({"data": {"kind": "fetch", "input": "https://example.com/nothing"}}, 422),
            ({"data": {"kind": "fetch", "input": "41000105199", "lang": "FR!"}}, 422),
            ({"data": {"kind": "fetch", "input": "41000105199", "quality": "4k"}}, 422),
            ({"data": {"kind": "fetch", "input": "41000105199", "episodes": "abc"}}, 422),
            ({"data": {"kind": "fetch", "input": "41000105199", "film_after": "yes"}}, 422),
            ({"raw": b"x" * 70_000, "headers": {"Content-Type": "application/json"}}, 413),
        ]
        for kwargs, expected in cases:
            with self.subTest(kwargs=str(kwargs)[:80]):
                status, data = self.call("POST", "/api/jobs", **kwargs)
                self.assertEqual(status, expected)
                if expected != 413:
                    self.assertIn("code", data["error"])
        status, data = self.call("POST", "/api/jobs", {"kind": "fetch", "input": "41000105199", "episodes": "abc"})
        self.assertEqual(data["error"]["code"], "invalid_episodes")

    def test_retry_keeps_the_original_request(self):
        self.app.runner.http = series_http({28: {"ok": False, "error": "Video unavailable"}})
        job = self.wait_job(self.fetch_job(), "done")
        self.assertEqual(job["result"]["failed"]["28"]["code"], "ep_unavailable")
        self.assertEqual(self.statuses()[28], "unavailable")

        self.app.runner.http = series_http()  # the source has it now
        status, data = self.call("POST", f"/api/series/{KEY}/retry", {})
        self.assertEqual(status, 201, data)
        self.assertEqual(data["job"]["params"]["episodes"], [[28, 28]])
        retried = self.wait_job(data["job"]["id"], "done")
        self.assertEqual(retried["result"]["done"], [28])
        self.assertIsNone(self.manifest()["requested"]["episodes"])  # still "all": nothing became "not requested"
        self.assertEqual(set(self.statuses().values()), {"done"})
        self.assertEqual(self.call("POST", f"/api/series/{KEY}/retry", {})[1]["error"]["code"], "nothing_to_do")

    def test_redownload_in_another_quality(self):
        self.wait_job(self.fetch_job(), "done")
        status, data = self.call("POST", f"/api/series/{KEY}/redownload", {"episodes": [2], "quality": "720p"})
        self.assertEqual(status, 201, data)
        job = self.wait_job(data["job"]["id"], "done")
        self.assertEqual(job["result"]["done"], [2])
        episodes = {e["number"]: e for e in self.manifest()["episodes"]}
        self.assertEqual((episodes[2]["quality"], episodes[1]["quality"]), ("720p", "1080p"))

    def test_repair_plans_only_safe_actions(self):
        self.app.runner.http = series_http({28: {"ok": False, "error": "Video unavailable"}})
        self.wait_job(self.fetch_job(episodes="1-2,28"), "done")
        (self.root / KEY / "E001.mp4").unlink()  # deleted outside the app
        status, plan = self.call("POST", "/api/repair", {"dry_run": True})
        self.assertEqual(status, 200)
        self.assertEqual([(a["series_key"], a["retry"]) for a in plan["actions"]], [(KEY, [1, 28])])
        self.call("POST", f"/api/series/{KEY}/ignore", {"problem": "failed"})
        self.assertEqual(self.call("POST", "/api/repair", {"dry_run": True})[1]["actions"], [])
        self.call("POST", f"/api/series/{KEY}/ignore", {"problem": "failed", "ignored": False})
        self.app.runner.http = series_http()
        status, done = self.call("POST", "/api/repair", {"dry_run": False})
        self.assertEqual(status, 201)
        self.wait_job(done["jobs"][0]["id"], "done")
        self.assertEqual(set(self.statuses().values()), {"done"})

    def test_ignore(self):
        self.wait_job(self.fetch_job(), "done")
        status, data = self.call("POST", f"/api/series/{KEY}/ignore", {"problem": "incomplete"})
        self.assertEqual((status, data["ignored"]), (200, ["incomplete"]))
        self.assertEqual(self.call("GET", f"/api/series/{KEY}")[1]["ignored"], ["incomplete"])
        self.assertEqual(self.call("POST", f"/api/series/{KEY}/ignore", {"problem": "whatever"})[0], 422)


class ControlTest(LiveTest):
    def make_http(self):
        return slow_http()

    def running_with_bytes(self, job_id):
        def ready():
            job = self.app.runner.get(job_id)
            last = job.progress.last if job.progress else None
            return job.status == "running" and last and last["bytes_done"] > 0

        self.wait(ready, what="bytes received")

    def test_pause_keeps_parts_and_resume_finishes(self):
        job_id = self.fetch_job()
        self.running_with_bytes(job_id)
        self.assertEqual(self.call("POST", "/api/jobs", {"kind": "fetch", "input": "41000105199"})[0], 409)  # duplicate
        status, data = self.call("POST", f"/api/jobs/{job_id}/pause")
        self.assertEqual((status, data["job"]["status"]), (202, "pausing"))
        self.wait_job(job_id, "paused")
        self.assertNotIn("downloading", {e["status"] for e in self.manifest()["episodes"]})
        self.assertTrue(list((self.root / KEY).glob("*.part")))
        self.assertIn("partial", self.statuses().values())
        self.assertEqual(self.call("DELETE", f"/api/series/{KEY}?scope=all")[0], 409)  # busy

        self.call("POST", f"/api/jobs/{job_id}/resume")
        job = self.wait_job(job_id, "done", timeout=30)
        self.assertEqual(sorted(job["result"]["done"] + job["result"]["skipped"]), [1, 2, 28])
        self.assertEqual(list((self.root / KEY).glob("*.part")), [])

    def test_cancel_deletes_the_parts(self):
        job_id = self.fetch_job()
        self.running_with_bytes(job_id)
        self.call("POST", f"/api/jobs/{job_id}/cancel", {"delete_parts": True})
        self.wait_job(job_id, "cancelled")
        self.assertEqual(list((self.root / KEY).glob("*.part")), [])
        self.assertEqual(self.call("POST", f"/api/jobs/{job_id}/pause")[0], 409)

    def test_episode_states_while_downloading(self):
        job_id = self.fetch_job()
        self.running_with_bytes(job_id)
        detail = self.call("GET", f"/api/series/{KEY}")[1]
        self.assertEqual(detail["job"]["id"], job_id)
        self.assertEqual(detail["state"], "active")
        self.assertTrue({"downloading", "queued", "done"} & set(e["status"] for e in detail["episodes"]))
        self.call("POST", f"/api/jobs/{job_id}/cancel", {"delete_parts": False})
        self.wait_job(job_id, "cancelled")

    def test_repair_after_cancel_takes_the_pending_episodes(self):
        self.app.settings.update({"parallel_downloads": 1})  # one at a time: the others wait in the queue
        job_id = self.fetch_job()
        self.running_with_bytes(job_id)
        self.call("POST", f"/api/jobs/{job_id}/cancel", {"delete_parts": False})
        self.wait_job(job_id, "cancelled")
        statuses = self.statuses()
        self.assertIn("pending", statuses.values())  # requested, never started
        left = sorted(n for n, s in statuses.items() if s != "done")
        status, data = self.call("POST", f"/api/series/{KEY}/retry", {})
        self.assertEqual(status, 201, data)
        job = self.wait_job(data["job"]["id"], "done", timeout=30)
        self.assertEqual(sorted(job["result"]["done"]), left)
        self.assertEqual(set(self.statuses().values()), {"done"})

    def test_settings_folder_cannot_change_during_a_download(self):
        job_id = self.fetch_job()
        self.running_with_bytes(job_id)
        status, data = self.call("PATCH", "/api/settings", {"downloads_dir": str(Path(self._tmp.name) / "other")})
        self.assertEqual((status, data["error"]["code"]), (409, "series_busy"))
        self.call("POST", f"/api/jobs/{job_id}/cancel")
        self.wait_job(job_id, "cancelled")

    def test_restart_resumes_an_interrupted_download(self):
        job_id = self.fetch_job()
        self.running_with_bytes(job_id)
        self.halt()  # like closing the server window
        self.assertEqual(json.loads((self.root / ".sdg" / "jobs.json").read_text())["jobs"][job_id]["status"], "interrupted")
        self.boot(series_http())
        job = self.wait_job(job_id, "done")
        self.assertEqual(sorted(job["result"]["done"] + job["result"]["skipped"]), [1, 2, 28])


class OfflineTest(LiveTest):
    def test_network_down_waits_then_resumes(self):
        self.online[:] = [False, False]

        def down(url):
            raise urllib.error.URLError("network is unreachable")

        broken = series_http()
        official_url = next(u for u in broken.pages if "dramaboxdb" in u)
        broken.pages[official_url] = down
        self.app.runner.http = broken
        job_id = self.fetch_job()
        job = self.wait_job(job_id, "interrupted")
        self.assertEqual((job["reason"], job["error"]), ("offline", None))

        self.app.runner.http = series_http()
        self.online[:] = [True, True]  # the recheck sees the network back and requeues the job
        self.wait_job(job_id, "done")


class FilmJobTest(LiveTest):
    def make_http(self):
        """Episodes with real tracks, so that plan_film can check their format."""
        http = series_http()
        for ch in fixture_json("official_en.json")["chapterList"]:
            data = episode_bytes(ch["duration"] / 1000)
            for url in http.files:
                if f"/{ch['id']}_1/" in url or url == ch.get("mp4"):
                    http.files[url] = data
        return http

    def fake_film(self, calls):
        def make_film(series_dir, ffmpeg, log=print, output=None, replace=False, **options):
            calls.append({"dir": series_dir, "replace": replace, **options})
            path = output or series_dir / "One Night to Forever.mp4"
            path.write_bytes(b"film")
            return film.FilmResult(path, 12.5, 4, "copy", 3)

        return mock.patch("shortdramagen.film.make_film", side_effect=make_film)

    def test_film_after_download(self):
        calls = []
        with self.fake_film(calls):
            fetch = self.wait_job(self.fetch_job(film_after=True), "done")
            self.assertIsNotNone(fetch["then"])
            made = self.wait_job(fetch["then"], "done")
        self.assertEqual((made["kind"], made["parent"], made["result"]["file"]), ("film", fetch["id"], "One Night to Forever.mp4"))
        self.assertEqual(calls[0]["dir"], self.root / KEY)

    def test_film_endpoint_checks_first(self):
        self.wait_job(self.fetch_job(), "done")
        status, plan = self.call("GET", f"/api/series/{KEY}/film/plan")
        self.assertEqual(status, 200)
        self.assertIn("can_build", plan)
        calls = []
        with self.fake_film(calls):
            status, data = self.call("POST", f"/api/series/{KEY}/film", {"output_name": "Mon film"})
            self.assertEqual(status, 201, data)
            job = self.wait_job(data["job"]["id"], "done")
        self.assertEqual(job["result"]["file"], "Mon film.mp4")
        status, data = self.call("POST", f"/api/series/{KEY}/film", {"output_name": "Mon film"})
        self.assertEqual((status, data["error"]["code"]), (409, "film_exists"))
        self.assertEqual(self.call("POST", f"/api/series/{KEY}/film", {"output_name": "../x"})[0], 422)

        def missing(path):
            raise film.FilmError("ffmpeg absent", errors.FFMPEG_MISSING)

        self.app.runner.find_ffmpeg = missing
        status, data = self.call("POST", f"/api/series/{KEY}/film", {"replace": True})
        self.assertEqual((status, data["error"]["code"]), (422, "ffmpeg_missing"))


class TrashTest(LiveTest):
    def setUp(self):
        super().setUp()
        self.wait_job(self.fetch_job(), "done")

    def test_episodes_film_all_and_restore(self):
        (self.root / KEY / "Film.mp4").write_bytes(b"film")
        manifest = self.manifest()
        manifest["film"] = {"file": "Film.mp4", "episodes": [1, 2, 28], "chapters": 3}
        (self.root / KEY / "manifest.json").write_text(json.dumps(manifest))

        status, data = self.call("DELETE", f"/api/series/{KEY}?scope=episodes")
        self.assertEqual(status, 200, data)
        self.assertGreater(data["freed_bytes"], 0)
        self.assertEqual(set(self.statuses().values()), {"removed"})
        self.assertEqual(self.call("GET", f"/api/series/{KEY}")[1]["film"]["state"], "ready")  # the film stays
        self.assertEqual(self.call("POST", f"/api/trash/{data['trash_id']}/restore")[0], 200)
        self.assertEqual(set(self.statuses().values()), {"done"})

        status, data = self.call("DELETE", f"/api/series/{KEY}?scope=film")
        self.assertEqual(status, 200)
        self.assertIsNone(self.call("GET", f"/api/series/{KEY}")[1]["film"])
        self.call("POST", f"/api/trash/{data['trash_id']}/restore")
        self.assertEqual(self.call("GET", f"/api/series/{KEY}")[1]["film"]["file"], "Film.mp4")

        status, data = self.call("DELETE", f"/api/series/{KEY}?scope=all")
        self.assertEqual(status, 200)
        self.assertFalse((self.root / KEY).exists())
        self.assertEqual(self.call("GET", "/api/library")[1]["groups"], [])
        self.call("POST", f"/api/trash/{data['trash_id']}/restore")
        self.assertEqual(len(self.call("GET", "/api/library")[1]["groups"]), 1)

    def test_parts_scope_and_purge(self):
        (self.root / KEY / "E028.x.part").write_bytes(b"12345")
        status, data = self.call("DELETE", f"/api/series/{KEY}?scope=parts")
        self.assertEqual((status, data["freed_bytes"], data["trash_id"]), (200, 5, None))
        self.assertEqual(self.call("DELETE", f"/api/series/{KEY}")[0], 422)  # the scope is mandatory

        status, data = self.call("DELETE", f"/api/series/{KEY}?scope=episodes")
        box = self.root / ".sdg" / "trash" / data["trash_id"]
        meta = json.loads((box / "meta.json").read_text())
        meta["expires_at"] = "2000-01-01T00:00:00+00:00"
        (box / "meta.json").write_text(json.dumps(meta))
        self.assertEqual(self.app.trash.purge(), 1)
        self.assertFalse(box.exists())
        self.assertEqual(self.call("POST", f"/api/trash/{data['trash_id']}/restore")[0], 404)

    def test_open(self):
        with mock.patch("shortdramagen.desktop.reveal") as reveal, mock.patch("shortdramagen.desktop.play") as play:
            self.assertEqual(self.call("POST", f"/api/series/{KEY}/open", {"target": "folder"})[0], 204)
            reveal.assert_called_with((self.root / KEY).resolve(), False)
            self.call("POST", f"/api/series/{KEY}/open", {"target": "episode", "episode": 2})
            reveal.assert_called_with((self.root / KEY / "E002.mp4").resolve(), True)
            self.call("POST", f"/api/series/{KEY}/open", {"target": "episode", "episode": 2, "play": True})
            play.assert_called_once()
        self.assertEqual(self.call("POST", f"/api/series/{KEY}/open", {"target": "exe"})[0], 422)
        self.assertEqual(self.call("POST", f"/api/series/{KEY}/open", {"target": "episode", "episode": 7})[0], 404)


class PreviewSettingsEventsTest(LiveTest):
    def test_preview_and_its_cover(self):
        self.http.pages[COVER_URL] = b"\xff\xd8\xff\xe0 jpeg"
        url = "https://www.dramaboxdb.com/movie/41000105199/one-night-to-forever"
        status, data = self.call("POST", "/api/preview", {"input": url})
        self.assertEqual(status, 200, data)
        self.assertEqual((data["title"], data["lang_source"], data["local"]), ("One Night to Forever", "default", []))
        self.assertEqual(data["availability"]["source"], "ok")
        self.assertEqual(data["cover_url"], "/media/preview/41000105199/vo/cover")
        conn = http.client.HTTPConnection("127.0.0.1", self.port, timeout=5)
        conn.request("GET", data["cover_url"], headers={"Host": f"127.0.0.1:{self.port}"})
        resp = conn.getresponse()
        self.assertEqual((resp.status, resp.read()[:2]), (200, b"\xff\xd8"))
        self.assertEqual(self.call("POST", "/api/preview", {"input": "pas un lien"})[0], 422)

    def test_preview_language_fallback_and_probe(self):
        props = fixture_json("official_en.json")
        props["locale"] = "de"
        self.http.pages["https://www.dramaboxdb.com/de/movie/41000105199/"] = official_html(props)
        status, data = self.call("POST", "/api/preview", {"input": "41000105199", "lang": "de"})
        self.assertEqual((status, data["lang_source"]), (200, "fallback"))
        self.assertEqual(data["warnings"][0]["code"], "lang_unavailable")

        status, data = self.call("POST", "/api/preview", {"input": "41000999999"})  # not on the official site
        self.assertEqual((status, data["from_official"], data["warnings"][0]["code"]), (200, False, "probe_mode"))

        self.app.http = FakeHttp()  # neither official nor source
        status, data = self.call("POST", "/api/preview", {"input": "41000777777"})
        self.assertEqual((status, data["error"]["code"]), (404, "series_not_found"))

    def test_settings_patch(self):
        status, data = self.call("PATCH", "/api/settings", {"theme": "light", "preferred_langs": ["fr"]})
        self.assertEqual((status, data["theme"], data["version"]), (200, "light", 2))
        status, data = self.call("PATCH", "/api/settings", {"parallel_downloads": 9})
        self.assertEqual((status, data["error"]["details"]["field"]), (422, "parallel_downloads"))
        other = Path(self._tmp.name) / "other"
        status, data = self.call("PATCH", "/api/settings", {"downloads_dir": str(other)})
        self.assertEqual((status, data["downloads_dir"]), (200, str(other.resolve())))
        self.assertEqual(self.app.library.root, other.resolve())
        self.assertEqual(self.call("GET", "/api/health")[1]["downloads_dir"], str(other.resolve()))

    def read_event(self, resp, wanted):
        event, data = None, None
        while True:
            line = resp.readline().decode().rstrip("\n")
            if line.startswith("event: "):
                event = line[7:]
            elif line.startswith("data: "):
                data = json.loads(line[6:])
            elif line == "" and event:
                if event == wanted:
                    return data
                event = None

    def test_event_stream(self):
        conn = http.client.HTTPConnection("127.0.0.1", self.port, timeout=10)
        conn.request("GET", "/api/events", headers={"Host": f"127.0.0.1:{self.port}"})  # no token: EventSource
        resp = conn.getresponse()
        self.assertEqual(resp.getheader("Content-Type"), "text/event-stream; charset=utf-8")
        snapshot = self.read_event(resp, "snapshot")
        self.assertEqual(snapshot["jobs"], {"active": [], "history": []})
        job_id = self.fetch_job()
        created = self.read_event(resp, "job")
        self.assertEqual((created["op"], created["job"]["id"]), ("created", job_id))
        episode = self.read_event(resp, "episode")
        self.assertEqual(episode["series_key"], KEY)
        library = self.read_event(resp, "library")
        self.assertEqual(library["series_key"], KEY)
        conn.close()
        self.wait_job(job_id, "done")

        conn = http.client.HTTPConnection("127.0.0.1", self.port, timeout=10)  # reconnection: replay, no snapshot
        conn.request("GET", "/api/events", headers={"Host": f"127.0.0.1:{self.port}", "Last-Event-ID": "1"})
        replayed = self.read_event(conn.getresponse(), "job")
        self.assertEqual(replayed["job"]["id"], job_id)
        conn.close()

        conn = http.client.HTTPConnection("127.0.0.1", self.port, timeout=10)
        conn.request("GET", "/api/events", headers={"Host": f"127.0.0.1:{self.port}", "Sec-Fetch-Site": "cross-site"})
        self.assertEqual(conn.getresponse().status, 403)
        conn.close()

    def test_shutdown_and_idle(self):
        self.assertEqual(self.call("POST", "/api/shutdown")[0], 409)  # not started by sdg ui
        stopped = threading.Event()
        self.app.on_shutdown = stopped.set
        self.assertEqual(self.call("POST", "/api/shutdown")[0], 202)
        self.assertTrue(stopped.wait(2))
        self.app.last_activity -= 1000
        self.assertGreaterEqual(self.app.idle_seconds(), 1000)


if __name__ == "__main__":
    unittest.main()
