import copy
import json
import sys
import tempfile
import unittest
from unittest.mock import patch, Mock
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / 'app'))
from daily_config import load_groups
import sync_daily_search


class DailyConfigTests(unittest.TestCase):
    def test_current_rules_preserve_existing_searches(self):
        groups = load_groups()
        self.assertEqual([g['categories'] for g in groups], [4, 2, 6])
        self.assertEqual([g['cutoffDays'] for g in groups], [10, 5, 10])
        self.assertEqual(groups[1]['minPages'], 8)
        self.assertIsNone(groups[1]['maxPages'])

    def test_invalid_rules_fail_before_scraping(self):
        for patch in [{'categories': True}, {'cutoffDays': 0}, {'minPages': 900, 'maxPages': 800}, {'apiKey': 'secret'}]:
            groups = copy.deepcopy(load_groups())
            groups[0].update(patch)
            with tempfile.TemporaryDirectory() as tmp:
                path = Path(tmp) / 'rules.json'
                path.write_text(json.dumps(groups))
                with self.assertRaises(ValueError):
                    load_groups(path)

    def test_group_failure_preserves_previous_daily_snapshot(self):
        with tempfile.TemporaryDirectory() as tmp:
            output = Path(tmp) / 'daily.json'
            output.write_text('[{"previous":"complete snapshot"}]')
            search = Mock()
            search.search_with_builder.return_value = {'success': False, 'error': 'simulated failure'}
            with patch.object(sync_daily_search, 'OUTPUT_PATH', output), patch.object(sync_daily_search, 'ExHentaiGallerySearch', return_value=search):
                self.assertEqual(sync_daily_search.main(), 1)
            self.assertEqual(output.read_text(), '[{"previous":"complete snapshot"}]')

    def test_builder_uses_configured_minimum_without_inventing_maximum(self):
        builder = sync_daily_search.build_group(load_groups()[1])
        self.assertEqual(builder.min_pages, 8)
        self.assertIsNone(builder.max_pages)
        self.assertEqual(builder.min_rating, 4)
        self.assertEqual(builder.f_cats, 1021)


if __name__ == '__main__':
    unittest.main()
