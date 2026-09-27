import io
import tempfile
import unittest
import urllib.error
from contextlib import redirect_stderr, redirect_stdout
from pathlib import Path
from unittest import mock

from shortdramagen import cli, pipeline

from fakes import series_http


def run(argv):
    out, err = io.StringIO(), io.StringIO()
    with redirect_stdout(out), redirect_stderr(err):
        code = cli.main(argv)
    return code, out.getvalue(), err.getvalue()


class FetchFilmOptionsTest(unittest.TestCase):
    """fetch --film forwards the film options (they used to be dropped)."""

    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.tmp = Path(self._tmp.name)
        mock.patch("shortdramagen.film.find_ffmpeg", return_value="ffmpeg").start()
        self.make_film = mock.patch("shortdramagen.film.make_film").start()
        self.addCleanup(mock.patch.stopall)

    def tearDown(self):
        self._tmp.cleanup()

    def result(self, done=(1, 2), skipped=(), failed=None, stop_reason=None):
        r = pipeline.FetchResult(series=None, series_dir=self.tmp, done=list(done), skipped=list(skipped))
        r.failed = failed or {}
        r.stop_reason = stop_reason
        return r

    def fetch(self, result, *extra):
        with mock.patch("shortdramagen.pipeline.fetch", return_value=result):
            return run(["fetch", "41000105199", "--film", "-o", str(self.tmp), *extra])

    def test_failures_block_the_film_unless_allowed(self):
        code, _, err = self.fetch(self.result(failed={3: "x"}))
        self.assertEqual(code, 1)
        self.make_film.assert_not_called()
        self.assertIn("--allow-missing", err)

        code, _, _ = self.fetch(self.result(failed={3: "x"}), "--allow-missing", "--reencode", "--no-chapters", "--replace")
        self.assertEqual(code, 1)  # the run still had failures
        kwargs = self.make_film.call_args.kwargs
        self.assertEqual(
            (kwargs["allow_missing"], kwargs["reencode"], kwargs["chapters"], kwargs["replace"], kwargs["only"]),
            (True, True, False, True, None),
        )

    def test_selection_makes_a_film_of_the_requested_episodes(self):
        code, _, _ = self.fetch(self.result(done=[2], skipped=[1]), "-e", "1-2")
        self.assertEqual(code, 0)
        self.assertEqual(self.make_film.call_args.kwargs["only"], {1, 2})

    def test_disk_full_stops_before_the_film(self):
        code, _, err = self.fetch(self.result(stop_reason="disk_full"))
        self.assertEqual(code, 1)
        self.make_film.assert_not_called()
        self.assertIn("libère de la place", err)

    def test_film_replace_flag(self):
        (self.tmp / "serie").mkdir()
        code, _, _ = run(["film", str(self.tmp / "serie"), "--replace"])
        self.assertEqual(code, 0)
        self.assertTrue(self.make_film.call_args.kwargs["replace"])


class InfoAndErrorsTest(unittest.TestCase):
    def test_info_uses_the_preview(self):
        with mock.patch("shortdramagen.cli.Http", return_value=series_http()):
            code, out, _ = run(["info", "41000105199"])
        self.assertEqual(code, 0)
        self.assertIn("One Night to Forever", out)
        self.assertIn("dramafren    : OK (dernier épisode dispo en 1080p, 720p)", out)

    def test_network_errors_are_readable(self):
        with mock.patch("shortdramagen.pipeline.preview_series", side_effect=urllib.error.URLError("hors ligne")):
            code, _, err = run(["info", "41000105199"])
        self.assertEqual(code, 1)
        self.assertIn("Erreur réseau", err)
        self.assertNotIn("Traceback", err)

    def test_bad_episode_range_is_an_argparse_error(self):
        with self.assertRaises(SystemExit) as ctx:
            run(["fetch", "41000105199", "-e", "3-1"])
        self.assertEqual(ctx.exception.code, 2)


if __name__ == "__main__":
    unittest.main()
