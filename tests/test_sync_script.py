import importlib.util
import json
import logging
from pathlib import Path
import tempfile
import unittest
from unittest.mock import Mock, patch

import requests

spec = importlib.util.spec_from_file_location('sync_script', Path(__file__).parents[1] / 'app/sync_script.py')
sync = importlib.util.module_from_spec(spec)
spec.loader.exec_module(sync)


def page(gid, next_href=None):
    html = f'<table class="itg"><tr><td><a href="/g/{gid}/abc/">Title</a></td></tr></table>'
    if next_href:
        html += f'<a id="unext" href="{next_href}">Next</a>'
    response = Mock(content=html.encode())
    response.raise_for_status.return_value = None
    return response


class SyncIntegrityTests(unittest.TestCase):
    def setUp(self):
        self.client = sync.ExHentaiUtils('https://exhentai.org/favorites.php', {}, logging.getLogger('test'))
        self.client.session = Mock()

    def test_relative_pagination_outside_old_container_is_followed(self):
        self.client.session.get.side_effect = [page(1, '?next=1'), page(2)]
        self.assertEqual([g['gid'] for g in self.client.extract_favorites()], ['1', '2'])
        self.assertEqual(self.client.session.get.call_args_list[1].args[0], 'https://exhentai.org/favorites.php?next=1')

    def test_later_page_http_failure_does_not_return_partial_results(self):
        failed = Mock()
        failed.raise_for_status.side_effect = requests.HTTPError('503')
        self.client.session.get.side_effect = [page(1, '?next=1'), failed]
        with self.assertRaisesRegex(RuntimeError, '不保存部分结果'):
            self.client.extract_favorites()

    def test_later_page_login_or_empty_html_is_rejected(self):
        response = Mock(content=b'<html>login required</html>')
        response.raise_for_status.return_value = None
        self.client.session.get.side_effect = [page(1, '?next=1'), response]
        with self.assertRaisesRegex(RuntimeError, '未解析到书目'):
            self.client.extract_favorites()

    def test_pagination_loop_is_rejected(self):
        self.client.session.get.return_value = page(1, 'favorites.php')
        with self.assertRaisesRegex(RuntimeError, '循环'):
            self.client.extract_favorites()

    def test_repeated_gallery_on_new_page_is_rejected(self):
        self.client.session.get.side_effect = [page(1, '?next=1'), page(1)]
        with self.assertRaisesRegex(RuntimeError, '重复书目'):
            self.client.extract_favorites()

    def test_exact_4214_to_2000_regression_keeps_original_file(self):
        with tempfile.TemporaryDirectory() as temp:
            target = Path(temp) / 'galleries.json'
            original = json.dumps([{'gid': i} for i in range(4214)])
            target.write_text(original)
            with patch.dict('os.environ', {'ALLOW_FAVORITES_SHRINK': ''}):
                with self.assertRaisesRegex(RuntimeError, '4214 → 2000'):
                    sync.validate_snapshot([{'gid': i} for i in range(2000)], target)
            self.assertEqual(target.read_text(), original)
            sync.validate_snapshot([{'gid': i} for i in range(4215)], target)
            with patch.dict('os.environ', {'ALLOW_FAVORITES_SHRINK': '1'}):
                sync.validate_snapshot([{'gid': i} for i in range(2000)], target)

    def test_partial_metadata_batch_is_not_success(self):
        response = Mock()
        response.json.return_value = {'gmetadata': [{'gid': 1}]}
        with patch.object(sync.requests, 'post', return_value=response):
            ok, data = self.client._fetch_single_batch_with_result('https://example.com', [{'gid': '1', 'token': 'a'}, {'gid': '2', 'token': 'b'}], 1)
        self.assertFalse(ok)
        self.assertEqual(data, [])


if __name__ == '__main__':
    unittest.main()
