import unittest
from unittest.mock import patch

from backend import cookie_refresh, db, jobs, security, services
import test_backend


class CookieRefreshTests(unittest.TestCase):
    setUp = test_backend.BackendTests.setUp
    tearDown = test_backend.BackendTests.tearDown

    def prepare(self):
        with db.connect() as con:
            version = services.version(con, 'favorites')
        services.save('favorites', version, {
            'EXHENTAI_LOGIN_USERNAME': 'forum-test',
            'EXHENTAI_LOGIN_PASSWORD': 'forum-test-password',
            'EXHENTAI_COOKIE_IGNEOUS': 'old-value',
        })
        job_id = jobs.enqueue(cookie_refresh.KIND)
        self.assertEqual(jobs.enqueue(cookie_refresh.KIND), job_id)
        with db.connect() as con:
            con.execute("UPDATE jobs SET status='in_progress' WHERE id=?", (job_id,))
        return job_id

    def test_verified_candidate_is_published_without_exposing_login_credentials(self):
        job_id = self.prepare()
        candidate = dict.fromkeys(cookie_refresh.COOKIE_FIELDS.values(), 'candidate-value')

        def probe(url):
            self.assertEqual(url, 'https://exhentai.org/favorites.php')
            self.assertEqual(security.credential('EXHENTAI_COOKIE_IGNEOUS'), 'candidate-value')
            return True

        with patch.object(cookie_refresh, 'acquire', return_value=candidate) as acquire, patch.object(services, 'probe_favorites', side_effect=probe):
            cookie_refresh.execute(job_id)
        self.assertEqual(acquire.call_args.args[:2], ('forum-test', 'forum-test-password'))
        self.assertEqual(security.credential('EXHENTAI_COOKIE_IGNEOUS'), 'candidate-value')
        details = jobs.detail(job_id)
        self.assertEqual(details['run']['conclusion'], 'success')
        self.assertNotIn('candidate-value', str(details))
        self.assertNotIn('forum-test', str(services.status()))
        self.assertNotIn(cookie_refresh.KIND, {item['kind'] for item in self.client.post(
            '/api/admin', json={'action': 'schedules', 'password': self.token}).json()['items']})

    def test_failed_probe_preserves_all_cookie_fields(self):
        job_id = self.prepare()
        candidate = dict.fromkeys(cookie_refresh.COOKIE_FIELDS.values(), 'candidate-value')
        previous = {name: security.credential(name) for name in candidate}
        with patch.object(cookie_refresh, 'acquire', return_value=candidate), patch.object(services, 'probe_favorites', return_value=False):
            with self.assertRaisesRegex(jobs.JobFailure, '未通过'):
                cookie_refresh.execute(job_id)
        self.assertEqual({name: security.credential(name) for name in candidate}, previous)

    def test_cancelled_during_probe_preserves_existing_cookie(self):
        job_id = self.prepare()

        def probe(url):
            jobs.cancel(job_id)
            return True

        with patch.object(cookie_refresh, 'acquire', return_value={'EXHENTAI_COOKIE_IGNEOUS': 'candidate'}), patch.object(services, 'probe_favorites', side_effect=probe):
            with self.assertRaises(jobs.JobCancelled):
                cookie_refresh.execute(job_id)
        self.assertEqual(security.credential('EXHENTAI_COOKIE_IGNEOUS'), 'old-value')
