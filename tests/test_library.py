"""Step 1: library index (reconciliation with the disk, film states, groups, safe paths)."""

import json
import os
import shutil
import tempfile
import time
import unittest
from pathlib import Path

from shortdramagen import library
from shortdramagen.library import LibraryError, LibraryIndex

VO = "41000105199-one-night-to-forever"
FR = "41000105199-one-night-to-forever-fr"


def write_version(root: Path, key: str, episodes: list[dict], files: dict | None = None, **fields) -> Path:
    """A series folder: manifest.json plus files ({name: bytes})."""
    folder = root / key
    folder.mkdir(parents=True, exist_ok=True)
    book_id = key.split("-", 1)[0]
    manifest = {
        "schema_version": 2, "platform": "dramabox", "book_id": book_id, "source_book_id": book_id,
        "lang": "en", "title": "One Night to Forever", "title_vo": "One Night to Forever",
        "languages": ["en", "fr", "es"], "from_official": True, "episode_count": len(episodes),
        "episodes": episodes, "updated_at": "2026-09-27T08:00:00+00:00",
        **fields,
    }  # fmt: skip
    (folder / "manifest.json").write_text(json.dumps(manifest, ensure_ascii=False), encoding="utf-8")
    for name, data in (files or {}).items():
        (folder / name).write_bytes(data)
    return folder


def ep(n: int, status: str = "done", **fields) -> dict:
    return {"number": n, "chapter_id": str(n), "media_id": str(n), "duration_ms": 60_000 + n, "status": status, **fields}


class TempRootTest(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.root = Path(self._tmp.name) / "downloads"
        self.root.mkdir()

    def tearDown(self):
        self._tmp.cleanup()

    def index(self) -> LibraryIndex:
        index = LibraryIndex(self.root)
        index.refresh(force=True)
        return index


class ReconciliationTest(TempRootTest):
    def test_statuses_follow_the_disk(self):
        write_version(
            self.root,
            VO,
            [
                ep(1, bytes=4, quality="1080p", origin="dramafren", url="https://cdn.example/signed?x=1"),
                ep(2, bytes=999, quality="1080p"),  # size changed since verified
                ep(3),  # file deleted outside the app
                ep(4, "downloading"),  # interrupted with a .part
                ep(5, "downloading"),  # interrupted before any byte
                ep(6, "pending"),  # file present but never verified
                ep(7, "failed", error_code="ep_unavailable", error="indisponible"),
                ep(8, "failed", error_code="duration_mismatch", error="HTTP 403 pour https://cdn.example/signed?token=abc"),
                ep(9, "removed"),
                ep(10, "pending"),  # outside the requested episodes
            ],
            {"E001.mp4": b"1234", "E002.mp4": b"12", "E004.577.1080p.mp4.part": b"x" * 10, "E006.mp4": b"123456"},
            requested={"lang": None, "quality": "best", "episodes": [[1, 9]]},
        )
        detail = self.index().series(VO)
        status = {e["n"]: e["status"] for e in detail["episodes"]}
        self.assertEqual(status, {
            1: "done", 2: "done", 3: "missing", 4: "partial", 5: "pending", 6: "done_unverified",
            7: "unavailable", 8: "failed", 9: "removed", 10: "not_requested",
        })  # fmt: skip
        by_n = {e["n"]: e for e in detail["episodes"]}
        self.assertTrue(by_n[2]["suspect"])
        self.assertEqual(by_n[4]["part_bytes"], 10)
        self.assertEqual(by_n[1]["media_url"], f"/media/series/{VO}/episodes/1")
        self.assertNotIn("media_url", by_n[3])
        self.assertEqual(detail["counts"]["suspect"], 1)
        self.assertEqual(detail["state"], "interrupted")  # partial wins over failures
        self.assertEqual(detail["bytes"], 4 + 2 + 6 + 10)
        text = json.dumps(detail)
        self.assertNotIn("cdn.example", text)  # signed URLs never leave the index
        self.assertIn("[lien masqué]", by_n[8]["error"])

    def test_version_states(self):
        cases = {
            "complete": [ep(1), ep(2)],
            "incomplete": [ep(1), ep(2, "pending")],
            "failed": [ep(1), ep(2, "failed", error_code="network")],
        }
        for i, (state, episodes) in enumerate(cases.items()):
            key = f"4100010519{i}-serie"
            write_version(self.root, key, episodes, {"E001.mp4": b"1", "E002.mp4": b"2"} if state == "complete" else {"E001.mp4": b"1"})
            with self.subTest(state=state):
                self.assertEqual(self.index().summary(key)["state"], state)

    def test_probe_and_schema_1_manifests(self):
        folder = self.root / "41000999999-serie"
        folder.mkdir()
        (folder / "manifest.json").write_text(json.dumps({  # schema 1, probe mode: no from_official, title = id
            "platform": "dramabox", "book_id": "41000999999", "source_book_id": "41000999999", "lang": "",
            "title": "41000999999", "slug": "serie", "episode_count": 1,
            "episodes": [{"number": 1, "chapter_id": "1", "media_id": "1", "status": "done"}],
        }))  # fmt: skip
        (folder / "E001.mp4").write_bytes(b"x")
        summary = self.index().summary("41000999999-serie")
        self.assertEqual((summary["title"], summary["from_official"]), ("Série 41000999999", False))
        self.assertEqual(summary["counts"]["done_unverified"], 1)  # durations never checked
        self.assertIsNone(summary["duration_s"])


class FilmStateTest(TempRootTest):
    def film(self, record: dict, files: dict, episodes=None) -> dict:
        """Film summary of a fresh folder; the episode files follow the statuses."""
        shutil.rmtree(self.root / VO, ignore_errors=True)
        episodes = episodes or [ep(1), ep(2)]
        present = {f"E{e['number']:03d}.mp4": b"e" for e in episodes if e["status"] == "done"}
        write_version(self.root, VO, episodes, {**present, **files}, film=record)
        return self.index().summary(VO)["film"]

    def test_ready_partial_stale(self):
        record = {"file": "Film.mp4", "episodes": [1, 2], "chapters": 2, "mode": "copy"}
        film = self.film(record, {"Film.mp4": b"film"})
        self.assertEqual((film["state"], film["bytes"], film["episodes"]), ("ready", 4, "1-2"))
        self.assertEqual(film["chapters_url"], f"/media/series/{VO}/film/chapters.vtt")

        partial = self.film({**record, "episodes": [1]}, {"Film.mp4": b"film"}, [ep(1), ep(2, "pending")])
        self.assertEqual(partial["state"], "partial")

        stale = self.film({**record, "episodes": [1]}, {"Film.mp4": b"film"})
        self.assertEqual((stale["state"], stale["added_since"]), ("stale", [2]))

    def test_stale_when_an_episode_is_newer(self):
        folder = write_version(self.root, VO, [ep(1)], {"E001.mp4": b"1", "Film.mp4": b"f"},
                               film={"file": "Film.mp4", "episodes": [1], "chapters": 1})  # fmt: skip
        old = time.time() - 100
        os.utime(folder / "Film.mp4", (old, old))
        self.assertEqual(self.index().summary(VO)["film"]["state"], "stale")

    def test_missing_and_outside(self):
        self.assertEqual(self.film({"file": "Film.mp4", "episodes": [1, 2]}, {})["state"], "missing_file")
        for name in ("/tmp/Film.mp4", "C:\\Films\\Film.mp4", "../Film.mp4", "E001.mp4", "notes.txt"):
            with self.subTest(name=name):
                film = self.film({"file": name, "episodes": [1, 2]}, {})
                self.assertEqual(film["state"], "outside")
                self.assertNotIn("media_url", film)


class GroupsTest(TempRootTest):
    def setUp(self):
        super().setUp()
        write_version(self.root, VO, [ep(1)], {"E001.mp4": b"1", "cover.jpg": b"\xff\xd8"})
        write_version(
            self.root, FR, [ep(1), ep(2, "pending")], {"E001.mp4": b"1"},
            source_book_id="41000111625", lang="fr", title="Qui Est la Véritable Mme Lafont ?",
            updated_at="2026-09-27T09:00:00+00:00",
        )  # fmt: skip
        write_version(self.root, "41000123401-the-heiress", [ep(1)], {"E001.mp4": b"1"}, title="The Heiress", languages=["en"])

    def test_versions_of_a_book_form_one_group(self):
        data = self.index().library(preferred_langs=["fr"])
        self.assertEqual(data["stats"]["groups"], 2)
        self.assertEqual(data["stats"]["versions"], 3)
        group = next(g for g in data["groups"] if g["book_id"] == "41000105199")
        self.assertEqual([v["series_key"] for v in group["versions"]], [VO, FR])  # VO first
        self.assertEqual(group["display_title"], "Qui Est la Véritable Mme Lafont ?")
        self.assertEqual(group["titles"], {"en": "One Night to Forever", "fr": "Qui Est la Véritable Mme Lafont ?"})
        self.assertTrue(group["cover_url"].startswith(f"/media/series/{VO}/cover?v="))  # the VO's cover
        self.assertEqual(group["updated_at"], "2026-09-27T09:00:00+00:00")
        self.assertEqual(data["groups"][0]["book_id"], "41000105199")  # most recent first

        original = self.index().library(preferred_langs=["fr"], title_lang="original")
        self.assertEqual(next(g for g in original["groups"] if g["book_id"] == "41000105199")["display_title"], "One Night to Forever")

    def test_series_detail_lists_sibling_versions(self):
        detail = self.index().series(FR)
        self.assertEqual([v["series_key"] for v in detail["versions"]], [VO, FR])
        self.assertEqual(detail["versions"][1]["done"], 1)
        self.assertFalse(detail["is_original"])
        with self.assertRaises(LibraryError):
            self.index().series("41000105199-unknown")


class ScanTest(TempRootTest):
    def test_problems_hidden_folders_and_cache(self):
        write_version(self.root, VO, [ep(1)], {"E001.mp4": b"1"})
        (self.root / ".sdg").mkdir()
        (self.root / ".sdg" / "manifest.json").write_text("{}")
        broken = self.root / "41000888888-broken"
        broken.mkdir()
        (broken / "manifest.json").write_text("{not json")
        odd = self.root / "My Series"
        odd.mkdir()
        (odd / "manifest.json").write_text("{}")
        (self.root / "no-manifest").mkdir()

        index = self.index()
        self.assertEqual(index.keys(), [VO])
        self.assertEqual(sorted(p["code"] for p in index.library()["problems"]), ["invalid_name", "manifest_unreadable"])

        version = index.version
        cached = index._versions[VO]
        self.assertFalse(index.refresh(force=True))  # nothing changed: same objects, same version
        self.assertIs(index._versions[VO], cached)
        self.assertEqual(index.version, version)

        (self.root / VO / "E002.mp4").write_bytes(b"2")  # a new file changes the folder
        os.utime(self.root / VO, None)
        time.sleep(0.01)
        write_version(self.root, VO, [ep(1), ep(2)], {})
        self.assertTrue(index.refresh(force=True))
        self.assertEqual(index.version, version + 1)
        self.assertEqual(index.summary(VO)["counts"]["done"], 2)

        self.assertFalse(index.refresh())  # a GET within 2 s reuses the scan

    def test_missing_root(self):
        index = LibraryIndex(self.root / "absent")
        index.refresh(force=True)
        data = index.library()
        self.assertEqual((data["root_error"], data["groups"]), ("not_found", []))

    @unittest.skipIf(os.name == "nt", "symlinks need privileges on Windows")
    def test_symlinked_folders_are_ignored(self):
        outside = Path(self._tmp.name) / "elsewhere"
        write_version(outside, VO, [ep(1)], {"E001.mp4": b"1"})
        os.symlink(outside / VO, self.root / VO)
        self.assertEqual(self.index().keys(), [])


class SafeFilesTest(TempRootTest):
    def test_files_are_rebuilt_and_confined(self):
        folder = write_version(
            self.root, VO, [ep(1), ep(2), ep(3)], {"E001.mp4": b"1", "cover.jpg": b"\xff\xd8"},
            film={"file": "Film.mp4", "episodes": [1], "chapters": 1, "chapter_times": [[1, 0.0, 60.001]]},
        )  # fmt: skip
        (folder / "Film.mp4").write_bytes(b"film")
        index = self.index()
        self.assertEqual(index.episode_file(VO, 1), (folder / "E001.mp4").resolve())
        self.assertEqual(index.cover_file(VO).name, "cover.jpg")
        self.assertEqual(index.film_file(VO).name, "Film.mp4")
        for bad in ((VO, 2), (VO, 99), ("../etc", 1), ("41000105199-x", 1)):
            with self.subTest(bad=bad), self.assertRaises(LibraryError) as ctx:
                index.episode_file(*bad)
            self.assertEqual(ctx.exception.code, "not_found")

    @unittest.skipIf(os.name == "nt", "symlinks need privileges on Windows")
    def test_symlink_escaping_the_folder_is_refused(self):
        secret = Path(self._tmp.name) / "secret.txt"
        secret.write_text("secret")
        folder = write_version(self.root, VO, [ep(1)], {})
        os.symlink(secret, folder / "E001.mp4")
        index = self.index()
        with self.assertRaises(LibraryError) as ctx:
            index.episode_file(VO, 1)
        self.assertEqual(ctx.exception.code, "outside_library")

    def test_film_outside_is_never_served(self):
        write_version(self.root, VO, [ep(1)], {"E001.mp4": b"1"}, film={"file": "/etc/passwd.mp4", "episodes": [1]})
        with self.assertRaises(LibraryError) as ctx:
            self.index().film_file(VO)
        self.assertEqual(ctx.exception.code, "outside_library")

    def test_chapters_vtt(self):
        write_version(
            self.root, VO, [ep(1), ep(2)], {"E001.mp4": b"1", "E002.mp4": b"2", "Film.mp4": b"f"},
            film={"file": "Film.mp4", "episodes": [1, 2], "chapters": 2, "chapter_times": [[1, 0, 153.118], [2, 153.118, 263.249]]},
        )  # fmt: skip
        vtt = self.index().chapters_vtt(VO)
        self.assertTrue(vtt.startswith("WEBVTT\n\n1\n00:00:00.000 --> 00:02:33.118\nÉpisode 1\n"))
        self.assertIn("00:02:33.118 --> 00:04:23.249\nÉpisode 2", vtt)

    def test_chapters_of_an_older_film_come_from_the_durations(self):
        write_version(self.root, VO, [ep(1), ep(2)], {"E001.mp4": b"1", "E002.mp4": b"2", "Film.mp4": b"f"},
                      film={"file": "Film.mp4", "episodes": [1, 2], "chapters": 2})  # fmt: skip
        marks = library.chapter_marks(self.index()._versions[VO], self.index()._versions[VO].data["film"])
        self.assertEqual([(n, round(s, 3), round(e, 3)) for n, s, e in marks], [(1, 0.0, 60.001), (2, 60.001, 120.003)])

    def test_clean_text(self):
        self.assertEqual(library.clean_text("HTTP 403 pour https://a.b/c?d=e fin"), "HTTP 403 pour [lien masqué] fin")
        self.assertIsNone(library.clean_text(None))


if __name__ == "__main__":
    unittest.main()
