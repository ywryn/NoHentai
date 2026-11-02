import unittest
from unittest.mock import Mock, patch
from app.exhentai_search import GalleryApiClient, ExHentaiGallerySearch, ExHentaiUrlBuilder, GalleryListParser


class DailyIntegrityTests(unittest.TestCase):
    def test_partial_or_wrong_metadata_batches_fail(self):
        client = GalleryApiClient()
        batch = [{'gid': 1, 'token': 'a'}, {'gid': 2, 'token': 'b'}]
        for data in ([{'gid': 1}], [{'gid': 2}, {'gid': 1}], [{'gid': 1}, {'gid': 2, 'error': 'missing'}]):
            response = Mock()
            response.json.return_value = {'gmetadata': data}
            with patch('app.exhentai_search.requests.post', return_value=response):
                self.assertEqual(client._fetch_batch(batch, 1), (False, []))
        with patch.object(client, '_fetch_batch', return_value=(False, [])):
            with self.assertRaises(RuntimeError):
                client.get_gallery_data(batch, max_retries=0)

    def test_login_html_is_failure_and_explicit_no_hits_is_success(self):
        self.assertTrue(GalleryListParser.parse('<html>login required</html>')['error'])
        self.assertIsNone(GalleryListParser.parse('<html>No hits found.</html>')['error'])
        malformed = '<table class="itg"><tr><td><a href="/g/123/abc/">unknown view</a></td></tr></table>'
        self.assertTrue(GalleryListParser.parse(malformed)['error'])

    def test_pagination_cycle_never_publishes_partial_results(self):
        search = ExHentaiGallerySearch()
        search.session = Mock()
        builder = ExHentaiUrlBuilder().set_keyword('test')
        parsed = {'galleries': [{'gid': 1, 'posted': '2026-11-01'}], 'next_url': builder.build(), 'error': None}
        with patch.object(GalleryListParser, 'parse', return_value=parsed):
            result = search.search_with_builder(builder, cutoff_date='2026-01-01')
        self.assertFalse(result['success'])
        self.assertEqual(result['galleries'], [])


if __name__ == '__main__':
    unittest.main()
