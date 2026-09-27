"""Step 1: the read-only server (security checks, API, media with Range, launch, settings)."""

import http.client
import json
import os
import tempfile
import threading
import unittest
from pathlib import Path
from unittest import mock

from shortdramagen import settings as settings_mod
from shortdramagen.library import LibraryIndex
from shortdramagen.server import launch, media, security
from shortdramagen.server.app import App, create_server
from shortdramagen.settings import Settings, SettingsError

from test_library import FR, VO, ep, write_version

EPISODE = bytes(range(256)) * 40  # 10 240 bytes, every offset recognisable


class ServerTest(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        tmp = Path(self._tmp.name)
        self.state = tmp / "state"
        self.root = tmp / "downloads"
        self.folder = write_version(
            self.root, VO, [ep(1, quality="1080p", url="https://cdn.example/signed?t=1"), ep(2), ep(3, "pending")],
            {"E001.mp4": EPISODE, "E002.mp4": b"two", "cover.jpg": b"\xff\xd8cover", "Qui Est la Véritable Mme Lafont.mp4": b"film" * 100},
            film={"file": "Qui Est la Véritable Mme Lafont.mp4", "episodes": [1, 2], "chapters": 2,
                  "chapter_times": [[1, 0, 60.001], [2, 60.001, 120.003]]},
        )  # fmt: skip
        write_version(self.root, FR, [ep(1)], {"E001.mp4": b"1"}, source_book_id="41000111625", lang="fr", title="Qui Est")
        self.settings = Settings(self.state)
        self.settings.update({"downloads_dir": str(self.root)})
        self.index = LibraryIndex(self.root)
        self.index.refresh(force=True)
        self.app = App(self.settings, self.index, "s" * 43)
        self.server = create_server(self.app, 0)
        self.port = self.server.server_address[1]
        self.thread = threading.Thread(target=self.server.serve_forever, kwargs={"poll_interval": 0.05}, daemon=True)
        self.thread.start()

    def tearDown(self):
        self.server.shutdown()
        self.server.server_close()
        self._tmp.cleanup()

    def request(self, method, path, headers=None, token=True, host=None, body=None, conn=None):
        own = conn is None
        conn = conn or http.client.HTTPConnection("127.0.0.1", self.port, timeout=5)
        h = {"Host": host or f"127.0.0.1:{self.port}"}
        if token and path.startswith("/api/"):
            h[security.TOKEN_HEADER] = self.app.token
        h.update(headers or {})
        conn.request(method, path, body=body, headers=h)
        resp = conn.getresponse()
        data = resp.read()
        if own:
            conn.close()
        return resp, data

    def json(self, path, **kw):
        resp, data = self.request("GET", path, **kw)
        return resp.status, json.loads(data) if data else None


class SecurityTest(ServerTest):
    def test_index_carries_the_token_and_strict_headers(self):
        resp, body = self.request("GET", "/")
        self.assertEqual(resp.status, 200)
        self.assertIn(f'content="{self.app.token}"'.encode(), body)
        self.assertNotIn(b"{{SDG_TOKEN}}", body)
        self.assertIn("script-src 'self'", resp.getheader("Content-Security-Policy"))
        self.assertEqual(resp.getheader("X-Content-Type-Options"), "nosniff")
        self.assertEqual(resp.getheader("Cache-Control"), "no-store")
        self.assertEqual(resp.getheader("Server"), "ShortDramaGen")

    def test_host_fetch_site_and_token(self):
        cases = [
            ({"host": "evil.example"}, "/", 421),
            ({"host": f"attacker.test:{self.port}"}, "/api/health", 421),
            ({"headers": {"Sec-Fetch-Site": "cross-site"}}, "/", 403),
            ({"headers": {"Sec-Fetch-Site": "same-site"}}, f"/media/series/{VO}/cover", 403),  # another local port
            ({"token": False}, "/api/health", 403),
            ({"token": False, "headers": {security.TOKEN_HEADER: "0" * 64}}, "/api/library", 403),
            ({"headers": {"Sec-Fetch-Site": "same-origin"}}, "/api/health", 200),
            ({"headers": {"Sec-Fetch-Site": "none"}}, "/", 200),
            ({"host": f"localhost:{self.port}"}, "/api/health", 200),
        ]
        for kwargs, path, expected in cases:
            with self.subTest(kwargs=kwargs, path=path):
                resp, _ = self.request("GET", path, **kwargs)
                self.assertEqual(resp.status, expected)

    def test_mutations_and_unknown_paths(self):
        conn = http.client.HTTPConnection("127.0.0.1", self.port, timeout=5)
        resp, data = self.request("POST", "/api/library", body=b'{"x": 1}', headers={"Content-Type": "application/json"}, conn=conn)
        self.assertEqual(resp.status, 405)
        self.assertEqual(json.loads(data)["error"]["code"], "not_found")
        resp, _ = self.request("GET", "/api/health", conn=conn)  # the body was drained: keep-alive still works
        self.assertEqual(resp.status, 200)
        conn.close()
        resp, _ = self.request("POST", "/api/health", headers={"Origin": "http://evil.example"})
        self.assertEqual(resp.status, 403)
        for path in ("/api/nope", "/nope.js", "/media/series/../../etc/passwd", "/media/series/%2e%2e/cover",
                     f"/media/series/{VO}/episodes/3", f"/media/series/{VO}/episodes/99", "/api/series/..%2F..%2Fetc"):  # fmt: skip
            with self.subTest(path=path):
                self.assertEqual(self.request("GET", path)[0].status, 404)

    def test_static_files(self):
        resp, body = self.request("GET", "/js/main.js")
        self.assertEqual((resp.status, resp.getheader("Content-Type")), (200, "text/javascript; charset=utf-8"))
        resp2, _ = self.request("GET", "/js/main.js", headers={"If-None-Match": resp.getheader("ETag")})
        self.assertEqual(resp2.status, 304)
        self.assertEqual(self.request("GET", "/app.css")[0].status, 200)

    @unittest.skipIf(os.name == "nt", "symlinks need privileges on Windows")
    def test_symlink_escape_is_forbidden(self):
        secret = Path(self._tmp.name) / "secret.mp4"
        secret.write_bytes(b"secret")
        (self.folder / "E002.mp4").unlink()
        os.symlink(secret, self.folder / "E002.mp4")
        resp, data = self.request("GET", f"/media/series/{VO}/episodes/2")
        self.assertEqual(resp.status, 403)
        self.assertNotIn(b"secret", data.replace(b"secret.mp4", b""))


class ApiTest(ServerTest):
    def test_health_and_settings(self):
        status, health = self.json("/api/health")
        self.assertEqual(status, 200)
        self.assertEqual((health["api"], health["read_only"], health["downloads_dir"]), (1, False, str(self.root)))
        self.assertIn("found", health["ffmpeg"])
        status, data = self.json("/api/settings")
        self.assertEqual((data["downloads_dir"], data["default_quality"], data["version"]), (str(self.root), "best", 1))

    def test_library_with_etag(self):
        resp, body = self.request("GET", "/api/library")
        data = json.loads(body)
        self.assertEqual(data["stats"]["versions"], 2)
        self.assertEqual(len(data["groups"]), 1)
        etag = resp.getheader("ETag")
        resp2, body2 = self.request("GET", "/api/library", headers={"If-None-Match": etag})
        self.assertEqual((resp2.status, body2), (304, b""))

    def test_series_detail(self):
        status, detail = self.json(f"/api/series/{VO}")
        self.assertEqual(status, 200)
        self.assertEqual([e["status"] for e in detail["episodes"]], ["done", "done", "pending"])
        self.assertEqual(detail["film"]["state"], "partial")  # episode 3 is not downloaded
        self.assertNotIn("cdn.example", json.dumps(detail))
        self.assertEqual(self.json("/api/series/41000105199-absent")[0], 404)


class MediaTest(ServerTest):
    def get(self, path, **headers):
        return self.request("GET", path, headers=headers)

    def test_ranges(self):
        url = f"/media/series/{VO}/episodes/1"
        size = len(EPISODE)
        resp, body = self.get(url)
        self.assertEqual((resp.status, body), (200, EPISODE))
        self.assertEqual(resp.getheader("Accept-Ranges"), "bytes")
        self.assertEqual(resp.getheader("Cross-Origin-Resource-Policy"), "same-origin")
        resp, body = self.get(url, Range="bytes=100-199")
        self.assertEqual((resp.status, body, resp.getheader("Content-Range")), (206, EPISODE[100:200], f"bytes 100-199/{size}"))
        resp, body = self.get(url, Range="bytes=-10")
        self.assertEqual((resp.status, body), (206, EPISODE[-10:]))
        resp, body = self.get(url, Range="bytes=10000-")
        self.assertEqual((resp.status, body), (206, EPISODE[10000:]))
        resp, _ = self.get(url, Range=f"bytes={size}-")
        self.assertEqual((resp.status, resp.getheader("Content-Range")), (416, f"bytes */{size}"))
        resp, body = self.get(url, Range="bytes=abc")  # invalid: ignored
        self.assertEqual((resp.status, len(body)), (200, size))
        resp, body = self.get(url, Range="bytes=0-9", **{"If-Range": '"old"'})  # the file changed: whole file
        self.assertEqual((resp.status, len(body)), (200, size))
        etag = resp.getheader("ETag")
        resp, body = self.get(url, Range="bytes=0-9", **{"If-Range": etag})
        self.assertEqual((resp.status, body), (206, EPISODE[:10]))

    def test_open_ranges_are_capped(self):
        with mock.patch.object(media, "MAX_OPEN_RANGE", 1000):
            resp, body = self.get(f"/media/series/{VO}/episodes/1", Range="bytes=500-")
        self.assertEqual((resp.status, body, resp.getheader("Content-Range")), (206, EPISODE[500:1500], f"bytes 500-1499/{len(EPISODE)}"))

    def test_head_download_cover_and_chapters(self):
        resp, body = self.request("HEAD", f"/media/series/{VO}/film")
        self.assertEqual((resp.status, body, resp.getheader("Content-Length")), (200, b"", "400"))
        resp, _ = self.get(f"/media/series/{VO}/film?download=1")
        disposition = resp.getheader("Content-Disposition")
        self.assertTrue(disposition.startswith('attachment; filename="Qui Est la V'))
        self.assertIn("filename*=UTF-8''Qui%20Est%20la%20V%C3%A9ritable%20Mme%20Lafont.mp4", disposition)
        resp, body = self.get(f"/media/series/{VO}/cover")
        self.assertEqual((resp.status, resp.getheader("Content-Type"), resp.getheader("Cache-Control")), (200, "image/jpeg", "private, max-age=86400"))
        resp, body = self.get(f"/media/series/{VO}/film/chapters.vtt")
        self.assertEqual(resp.getheader("Content-Type"), "text/vtt; charset=utf-8")
        self.assertIn("00:01:00.001 --> 00:02:00.003\nÉpisode 2", body.decode())
        self.assertEqual(self.get(f"/media/series/{FR}/film")[0].status, 404)

    def test_parse_range(self):
        self.assertIsNone(media.parse_range(None, 100))
        self.assertEqual(media.parse_range("bytes=0-", 100), (0, 99))
        self.assertEqual(media.parse_range("bytes=90-200", 100), (90, 99))
        self.assertEqual(media.parse_range("bytes=-500", 100), (0, 99))
        self.assertEqual(media.parse_range("bytes=0-9, 20-29", 100), (0, 9))
        self.assertIsNone(media.parse_range("bytes=9-0", 100))
        for bad in ("bytes=100-", "bytes=-0"):
            with self.subTest(bad=bad), self.assertRaises(media.RangeNotSatisfiable):
                media.parse_range(bad, 100)


class LaunchTest(ServerTest):
    def test_running_instance_is_found_by_its_health(self):
        with mock.patch.object(launch, "load_secret", return_value="s" * 43):
            settings_mod.write_server_info({"pid": 1, "port": self.port}, self.state)
            self.assertEqual(launch.running_instance(self.state)["downloads_dir"], str(self.root))
            settings_mod.write_server_info({"pid": 1, "port": 1}, self.state)
            self.assertIsNone(launch.running_instance(self.state))

    def test_second_launch_reuses_the_running_server(self):
        settings_mod.write_server_info({"pid": 1, "port": self.port}, self.state)
        lines = []
        with mock.patch.dict(os.environ, {"SDG_HOME": str(self.state)}), \
             mock.patch.object(launch, "load_secret", return_value="s" * 43), \
             mock.patch.object(launch, "open_interface") as opened:  # fmt: skip
            code = launch.run_ui(Path(self._tmp.name) / "other", open_browser=True, log=lines.append)
        self.assertEqual(code, 0)
        opened.assert_called_once_with(f"http://127.0.0.1:{self.port}/", False)
        self.assertIn("déjà lancé", lines[0])
        self.assertIn("-o ignoré", lines[1])

    def test_only_loopback(self):
        with self.assertRaises(ValueError):
            create_server(self.app, 0, host="0.0.0.0")


class SettingsTest(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.dir = Path(self._tmp.name)

    def tearDown(self):
        self._tmp.cleanup()

    def test_validation(self):
        bad = [
            {"default_quality": "4k"},
            {"parallel_downloads": 0},
            {"parallel_downloads": True},
            {"preferred_langs": ["FR"]},
            {"theme": "pink"},
            {"unknown": 1},
            {"downloads_dir": "relative/path"},
            {"downloads_dir": str(Path(self.dir.anchor))},
            {"ffmpeg_path": str(self.dir / "notffmpeg")},
        ]
        for patch in bad:
            with self.subTest(patch=patch), self.assertRaises(SettingsError):
                settings_mod.validate(patch)
        a_file = self.dir / "file"
        a_file.write_text("x")
        with self.assertRaises(SettingsError):
            settings_mod.validate({"downloads_dir": str(a_file)})
        clean = settings_mod.validate({"downloads_dir": str(self.dir / "new" / "lib"), "preferred_langs": ["fr", "fr", "es"]})
        self.assertTrue((self.dir / "new" / "lib").is_dir())  # created and writable
        self.assertEqual(clean["preferred_langs"], ["fr", "es"])

    def test_store_keeps_valid_values_and_counts_versions(self):
        (self.dir / "settings.json").write_text(json.dumps({"theme": "light", "parallel_downloads": 99, "version": 4}))
        s = Settings(self.dir)
        self.assertEqual((s["theme"], s["parallel_downloads"], s.version), ("light", 3, 4))
        self.assertEqual(s.update({"theme": "light"}), {})  # no change, no new version
        self.assertEqual(s.update({"default_quality": "720p"}), {"default_quality": "720p"})
        again = Settings(self.dir)
        self.assertEqual((again["default_quality"], again.version), ("720p", 5))

    def test_secret_is_kept(self):
        first = settings_mod.load_secret(self.dir)
        self.assertGreaterEqual(len(first), 32)
        self.assertEqual(settings_mod.load_secret(self.dir), first)
        self.assertEqual(len(security.page_token(first)), 64)

    def test_state_dir(self):
        with mock.patch.dict(os.environ, {"SDG_HOME": str(self.dir)}):
            self.assertEqual(settings_mod.state_dir(), self.dir)


if __name__ == "__main__":
    unittest.main()
