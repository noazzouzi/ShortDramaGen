import unittest

from shortdramagen import dramafren, official

from fakes import FakeHttp, fixture_json, official_html


class OfficialTest(unittest.TestCase):
    def test_original_version(self):
        series = official.parse_page_props(fixture_json("official_en.json"), "41000105199")
        self.assertEqual(series.title, "One Night to Forever")
        self.assertEqual(series.source_book_id, "41000105199")
        self.assertEqual(series.slug, "one-night-to-forever")
        self.assertEqual([ep.number for ep in series.episodes], [1, 2, 28])
        ep28 = series.episodes[-1]
        self.assertEqual((ep28.chapter_id, ep28.media_id, ep28.duration_ms), ("577159363", "577159363", 79134))
        self.assertIsNone(ep28.free_url)  # locked episode
        self.assertIn(".720p.", series.episodes[0].free_url)

    def test_dubbed_version_uses_media_ids_from_cdn_paths(self):
        series = official.parse_page_props(fixture_json("official_fr.json"), "41000105199", "fr")
        self.assertEqual(series.title, "Qui Est la Véritable Mme Lafont ?")
        self.assertEqual(series.source_book_id, "41000111625")
        self.assertEqual(series.lang, "fr")
        ep28 = series.episodes[-1]
        self.assertEqual(ep28.chapter_id, "577159363")  # original id
        self.assertEqual(ep28.media_id, "586357960")  # id of the French video

    def test_fetch_series_urls_and_404(self):
        props = fixture_json("official_en.json")
        http = FakeHttp(pages={"https://www.dramaboxdb.com/movie/41000105199/": official_html(props)})
        self.assertEqual(official.fetch_series(http, "41000105199").episode_count, 3)
        self.assertEqual(official.series_url("1", "en"), "https://www.dramaboxdb.com/movie/1/")
        self.assertEqual(official.series_url("1", "fr"), "https://www.dramaboxdb.com/fr/movie/1/")
        with self.assertRaises(official.SeriesNotFound):
            official.fetch_series(FakeHttp(), "41000999999")
        with self.assertRaises(official.SeriesNotFound):  # the site's 404 page is a Next.js page too
            official.parse_series_page(official_html({"locale": "en"}), "41000999999")


class DramafrenTest(unittest.TestCase):
    def test_parse_payload_best_first(self):
        sources = dramafren.parse_video_payload(fixture_json("dramafren_ep28.json"))
        self.assertEqual([s.quality for s in sources], ["1080p", "720p", "540p"])
        self.assertTrue(all(s.origin == "dramafren" for s in sources))

    def test_request_and_fallback_endpoint(self):
        payload = fixture_json("dramafren_ep28.json")
        http = FakeHttp(
            pages={
                dramafren.ENDPOINTS[0]: {"ok": False, "error": "Video unavailable"},
                dramafren.ENDPOINTS[1]: payload,
            }
        )
        sources = dramafren.get_video(http, "41000105199", 28)
        self.assertEqual(sources[0].quality, "1080p")
        first_url, headers = http.calls[0]
        self.assertIn("action=get_video&id=41000105199&ep=28&lang=en&sv=1", first_url)
        self.assertEqual(headers["Origin"], "https://dramabox.dramafren.org")
        self.assertTrue(http.calls[1][0].startswith(dramafren.ENDPOINTS[1]))

    def test_all_endpoints_failing(self):
        http = FakeHttp(pages={dramafren.ENDPOINTS[0]: 403, dramafren.ENDPOINTS[1]: {"ok": False, "error": "Video unavailable"}})
        with self.assertRaises(dramafren.ResolveError) as ctx:
            dramafren.get_video(http, "41000105199", 63)
        self.assertIn("Video unavailable", str(ctx.exception))


if __name__ == "__main__":
    unittest.main()
