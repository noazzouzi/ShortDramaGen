import unittest
from argparse import ArgumentTypeError
from datetime import datetime, timezone

from shortdramagen import cdn
from shortdramagen.cli import parse_episodes
from shortdramagen.inputs import InputError, parse_input
from shortdramagen.models import BookRef

# Real URL captured in DevTools (episode 28), used as ground truth.
EP28_URL = (
    "https://hwztakavideoto.dramaboxdb.com/f940aa0c163471fa5ae4deac10afef0d/6ad5b861/"
    "36/9x9/99x1/991x5/99150100014/577159363_1/577159363.720p.narrowv3.mp4"
)


class ParseInputTest(unittest.TestCase):
    def test_supported_formats(self):
        cases = {
            "41000105199": BookRef("41000105199"),
            " 41000105199 ": BookRef("41000105199"),
            "https://www.dramaboxdb.com/movie/41000105199/one-night-to-forever": BookRef("41000105199"),
            "https://www.dramaboxdb.com/fr/movie/41000105199/one-night-to-forever": BookRef("41000105199", "fr"),
            "www.dramaboxdb.com/es/movie/41000105199/": BookRef("41000105199", "es"),
            "https://www.dramaboxdb.com/ep/41000105199_one-night-to-forever/577159363_Episode-28": BookRef("41000105199", episode=28),
            "https://www.dramaboxdb.com/fr/ep/41000105199_one-night-to-forever/577159336_Episode-1": BookRef("41000105199", "fr", 1),
            "https://www.dramabox.com/drama/41000105199/One-Night-to-Forever": BookRef("41000105199"),
            "https://www.dramaboxapp.com/drama/42000021382/Deny-Me-Dragon-King": BookRef("42000021382"),
            # dramafren's lang does not change the video, so it is ignored
            "https://dramabox.dramafren.org/index.php?page=detail&id=41000105199&lang=fr": BookRef("41000105199"),
            "https://dramabox.dramafren.org/index.php?page=watch&id=41000105199&ep=28&lang=fr&slug=x": BookRef("41000105199", episode=28),
            "https://example.app/share?bookId=41000105199&from=app": BookRef("41000105199"),
        }
        for text, expected in cases.items():
            with self.subTest(text=text):
                self.assertEqual(parse_input(text), expected)

    def test_rejects_unknown(self):
        for text in ("", "https://www.dramaboxdb.com/", "hello"):
            with self.subTest(text=text), self.assertRaises(InputError):
                parse_input(text)


class CdnTest(unittest.TestCase):
    def test_expected_path_matches_real_url(self):
        self.assertEqual(
            cdn.expected_path("41000105199", "577159363"),
            "/36/9x9/99x1/991x5/99150100014/577159363_1/",
        )
        self.assertTrue(cdn.matches_episode(EP28_URL, "41000105199", "577159363"))

    def test_mismatch_detected(self):
        self.assertFalse(cdn.matches_episode(EP28_URL, "41000105199", "577159362"))  # episode 27
        self.assertFalse(cdn.matches_episode(EP28_URL, "41000111625", "577159363"))  # other book

    def test_media_id_from_url(self):
        self.assertEqual(cdn.media_id_from_url(EP28_URL), "577159363")
        cover = "https://thwztvideo.dramaboxdb.com/06/5x2/52x6/526x1/52611100014/586357960_1/586357960.mp4.jpg@w=100&h=135"
        self.assertEqual(cdn.media_id_from_url(cover), "586357960")
        hls = "https://hwzthls.dramaboxdb.com/63/9x9/99x1/991x5/99150100014/577159336_1/m3u8/577159336.720p.m3u8?Expires=1"
        self.assertEqual(cdn.media_id_from_url(hls), "577159336")
        self.assertIsNone(cdn.media_id_from_url(None))

    def test_expires_at(self):
        self.assertEqual(cdn.expires_at(EP28_URL), datetime(2026, 10, 19, 6, 27, 45, tzinfo=timezone.utc))
        cloudfront = "https://hwvideoseo.dramaboxdb.com/x/1_1/1.mp4?Expires=1790535600&Signature=a&Key-Pair-Id=b"
        self.assertEqual(cdn.expires_at(cloudfront), datetime.fromtimestamp(1790535600, tz=timezone.utc))
        self.assertIsNone(cdn.expires_at("https://example.com/video.mp4"))


class ParseEpisodesTest(unittest.TestCase):
    def test_ranges(self):
        self.assertIsNone(parse_episodes(None))
        self.assertEqual(parse_episodes("1-3, 28,60-"), [(1, 3), (28, 28), (60, None)])
        for bad in ("a", "3-1", "1--2"):
            with self.subTest(bad=bad), self.assertRaises(ArgumentTypeError):
                parse_episodes(bad)


if __name__ == "__main__":
    unittest.main()
