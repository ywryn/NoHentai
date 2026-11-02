"""Integration tests use a temporary SQLite database and fake upstream services."""
import base64
import copy
import json
import os
import sqlite3
import tempfile
import time
import unittest
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from unittest.mock import patch, Mock
from cryptography.fernet import Fernet
from fastapi.testclient import TestClient
from backend import db, settings, jobs, security, translation
from backend.main import app
from backend.cli import initialize_data, backup
from backend.validation import read_books, books_csv

GALLERY = {'gid': 123, 'token': 'abcdef1234', 'title': 'source', 'title_jpn': '', 'tags': ['artist:test'],
           'category': 'Manga', 'posted': '1770000000', 'favTime': '2026-11-01 12:00'}
BOOK = {'ID': 'test', '书名': '测试', '日文名': '', '收价': '', '原价': '', 'sid': '123', '备注': '', 'cover': ''}


class BackendTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.env = patch.dict(os.environ, {'ADMIN_PASSWORD': 'admin-test-password-123', 'TRANS_PASSWORD': 'trans-test',
                                          'CREDENTIAL_ENCRYPTION_KEY': Fernet.generate_key().decode(),
                                          'ALLOWED_ORIGINS': 'http://localhost:3000', 'NOHENTAI_DATA_DIR': self.tmp.name,
                                          'EXHENTAI_COOKIE_MEMBER_ID': '', 'EXHENTAI_COOKIE_PASS_HASH': '', 'EXHENTAI_COOKIE_IGNEOUS': ''})
        self.env.start()
        self.paths = [patch.object(settings, 'DATA_DIR', Path(self.tmp.name)),
                      patch.object(settings, 'DB_PATH', Path(self.tmp.name) / 'nohentai.sqlite3')]
        for p in self.paths:
            p.start()
        db.initialize()
        self.daily = json.loads((settings.ROOT / 'config/daily.json').read_text())
        with db.connect() as con:
            db.replace_galleries(con, [GALLERY])
            for name, value in [('overrides', {}), ('printed', [BOOK]), ('daily', self.daily),
                                ('translate', {'model': None, 'jsonMode': None, 'defaultOcr': 'google'})]:
                db.put_resource(con, name, value)
            db.put_snapshot(con, 'daily', [{'name': 'test', 'galleries': [GALLERY]}])
            db.put_snapshot(con, 'translations', {'data': []})
        self.client = TestClient(app)
        self.client.__enter__()
        self.token = self.client.post('/api/admin', json={'action': 'verify', 'password': os.environ['ADMIN_PASSWORD']}).json()['session']['token']

    def tearDown(self):
        self.client.__exit__(None, None, None)
        for p in self.paths:
            p.stop()
        self.env.stop()
        self.tmp.cleanup()

    def admin(self, action, **body):
        return self.client.post('/api/admin', json={'action': action, 'password': self.token, **body})

    def save(self, name, data):
        version = self.admin('load', resource=name).json()['sha']
        return self.admin('save', resource=name, sha=version, data=data)

    def claim(self, kind):
        job = jobs.enqueue(kind)
        with db.connect() as con:
            con.execute("UPDATE jobs SET status='in_progress' WHERE id=?", (job,))
        return job

    def test_admin_translation_permissions_are_separate(self):
        self.assertEqual(self.admin('load', resource='daily', password='trans-test').status_code, 401)
        self.assertEqual(self.admin('load', resource='daily', password=os.environ['ADMIN_PASSWORD']).status_code, 401)
        for url in ('/api/trans-verify', '/api/trans-translate', '/api/trans-ocr'):
            self.assertEqual(self.client.post(url, json={'password': self.token}).status_code, 401)
        self.assertEqual(self.client.post('/api/trans-verify', json={'password': 'trans-test'}).status_code, 200)
        self.assertEqual(self.client.post('/api/printed-books', json={'password': 'trans-test'}).status_code, 410)

    def test_session_logout_rotation_and_expiry(self):
        self.assertEqual(self.admin('logout').status_code, 200)
        self.assertEqual(self.admin('runs').status_code, 401)
        token = security.login(os.environ['ADMIN_PASSWORD'], 'another')['token']
        security.change_password(os.environ['ADMIN_PASSWORD'], 'rotated-password-123456')
        os.environ['ADMIN_PASSWORD'] = 'rotated-password-123456'
        self.assertEqual(self.admin('runs', password=token).status_code, 401)
        token = security.login(os.environ['ADMIN_PASSWORD'], 'another')['token']
        with db.connect() as con:
            con.execute('UPDATE sessions SET expires=0')
        self.assertEqual(self.admin('runs', password=token).status_code, 401)

    def test_login_rate_limit_and_remember_duration(self):
        short = security.login(os.environ['ADMIN_PASSWORD'], 'short')
        long = security.login(os.environ['ADMIN_PASSWORD'], 'long', True)
        self.assertLess(short['expiresAt'] - time.time() * 1000, 13 * 3600000)
        self.assertGreater(long['expiresAt'] - time.time() * 1000, 29 * 86400000)
        for _ in range(10):
            result = self.client.post('/api/admin', json={'action': 'verify', 'password': 'bad'})
        self.assertEqual(result.status_code, 429)

    def test_foreign_origin_bad_json_and_unknown_routes(self):
        self.assertEqual(self.client.post('/api/admin', json={'action': 'runs', 'password': self.token}, headers={'Origin': 'https://evil.example'}).status_code, 403)
        self.assertEqual(self.client.post('/api/admin', content='{broken', headers={'Content-Type': 'application/json'}).status_code, 400)
        self.assertEqual(self.client.get('/data/gallery-overrides.json').status_code, 404)
        self.assertEqual(self.client.get('/data/backup_data/secret.json').status_code, 404)
        self.assertEqual(self.admin('dispatch', workflow='../shell').status_code, 400)
        self.assertEqual(self.admin('load', resource='../../.env').status_code, 400)

    def test_body_size_limit(self):
        self.assertEqual(self.client.post('/api/admin', content=b'x' * (16 * 1024 * 1024 + 1)).status_code, 413)

    def test_optimistic_lock_and_immediate_public_data(self):
        version = self.admin('load', resource='overrides').json()['sha']
        response = self.admin('save', resource='overrides', sha=version, data={'123': {'title': '编辑', 'tags': []}})
        self.assertEqual(response.status_code, 200, response.text)
        self.assertEqual(self.client.get('/data/galleries.json').json()[0]['title'], '编辑')
        self.assertEqual(self.client.get('/data/galleries.json').json()[0]['tags'], [])
        self.assertEqual(self.admin('save', resource='overrides', sha=version, data={}).status_code, 409)
        self.assertEqual(self.admin('history', resource='overrides').json()['commits'][0]['sha'], response.json()['sha'])
        self.assertEqual(self.save('overrides', {}).status_code, 200)
        self.assertEqual(self.client.get('/data/galleries.json').json()[0]['title'], 'source')

    def test_hiding_applies_to_daily_and_stats(self):
        self.assertEqual(self.save('overrides', {'123': {'hidden': True}}).status_code, 200)
        self.assertEqual(self.client.get('/data/galleries.json').json(), [])
        self.assertEqual(self.client.get('/data/daily_search.json').json()[0]['galleries'], [])
        self.assertEqual(self.client.get('/data/stats.json').json()['stats']['total_count'], 0)
        self.assertEqual(self.admin('gallery-search').json()['total'], 1)
        self.assertEqual(len(read_books(self.client.get('/data/future_digi.csv').text)), 1)

    def test_printed_duplicate_ids_csv_and_broken_references(self):
        books = [dict(BOOK, **{'书名': '测试,"第一本"', '备注': '多行\r\n第二行'}), dict(BOOK)]
        self.assertEqual(self.save('printed', books).status_code, 200)
        self.assertEqual(read_books(self.client.get('/data/future_digi.csv').text), books)
        self.assertEqual(self.save('printed', [dict(BOOK, sid='999')]).status_code, 400)
        with db.connect() as con:
            db.put_resource(con, 'printed', [dict(BOOK, sid='999')])
        response = self.save('printed', [dict(BOOK, sid='999')])
        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.json()['warnings'])

    def test_validation_rejects_secret_fields_and_unknown_galleries(self):
        for name, data in [('translate', {'apiKey': 'secret'}), ('overrides', {'123': {'token': 'replace'}}),
                           ('overrides', {'999': {'title': 'new'}}), ('daily', [dict(self.daily[0], categories=True)]),
                           ('printed', [dict(BOOK, cover='../.env')])]:
            self.assertEqual(self.save(name, data).status_code, 400, (name, data))

    def test_secrets_encrypted_persistent_and_never_returned(self):
        value = 'test-private-ocr-token'
        response = self.admin('replace-secret', platform='server', name='OCR_SPACE_KEY', value=value)
        self.assertEqual(response.status_code, 200, response.text)
        self.assertEqual(security.credential('OCR_SPACE_KEY'), value)
        with db.connect() as con:
            self.assertNotIn(value, con.execute('SELECT ciphertext FROM credentials').fetchone()[0])
            self.assertNotIn(value, str([tuple(r) for r in con.execute('SELECT * FROM history')]))
        self.assertNotIn(value, self.admin('platforms').text)
        self.assertEqual(self.admin('replace-secret', platform='server', name='ADMIN_PASSWORD', value='bad').status_code, 400)
        self.assertEqual(self.admin('replace-secret', platform='server', name='TRANS_PASSWORD', value=os.environ['ADMIN_PASSWORD']).status_code, 400)

    def test_counters_atomic_cache_and_backup(self):
        with ThreadPoolExecutor(max_workers=10) as pool:
            outcomes = list(pool.map(lambda _: db.reserve('quota', 3, 60), range(20)))
        self.assertEqual(sum(outcomes), 3)
        db.set_cache('test', {'ok': True}, 60)
        self.assertEqual(db.get_cache('test'), {'ok': True})
        db.set_cache('expired', {'ok': True}, -1)
        self.assertIsNone(db.get_cache('expired'))
        path = backup()
        con = sqlite3.connect(path)
        self.assertEqual(con.execute('PRAGMA integrity_check').fetchone()[0], 'ok')
        self.assertEqual(con.execute('SELECT COUNT(*) FROM galleries').fetchone()[0], 1)
        con.close()
        with self.assertRaises(RuntimeError):
            initialize_data()

    def test_queue_dedup_rerun_and_interrupted_jobs(self):
        job = jobs.enqueue('favorites')
        self.assertEqual(jobs.enqueue('favorites'), job)
        self.assertEqual(self.admin('rerun', runId=job).status_code, 400)
        with db.connect() as con:
            con.execute("UPDATE jobs SET status='in_progress' WHERE id=?", (job,))
        jobs.work(once=True)
        result = jobs.runs()[0]
        self.assertEqual(result['conclusion'], 'failure')
        self.assertNotEqual(jobs.rerun(job), job)

    def test_actual_worker_child_failure_is_recorded_without_data_loss(self):
        jobs.enqueue('favorites')
        jobs.work(once=True)
        self.assertEqual(jobs.runs()[0]['conclusion'], 'failure')
        self.assertEqual(self.client.get('/data/galleries.json').json()[0]['title'], 'source')

    def test_local_explicit_shrink_override_and_singleton_lock(self):
        with db.connect() as con:
            db.replace_galleries(con, [dict(GALLERY, gid=i) for i in range(1, 11)])
        with patch.object(jobs, 'collect_favorites', return_value=[GALLERY]):
            job = jobs.run_foreground('favorites', allow_shrink=True)
        self.assertEqual(jobs.runs()[0]['id'], job)
        self.assertEqual(len(self.client.get('/data/galleries.json').json()), 1)
        import fcntl
        with (settings.DATA_DIR / 'worker.lock').open('w') as lock:
            fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
            with self.assertRaises(RuntimeError):
                jobs.work(once=True)

    def test_all_sync_failure_preserves_entire_previous_snapshot(self):
        job = self.claim('all')
        with patch.object(jobs, 'collect_favorites', return_value=[dict(GALLERY, title='updated')]), \
             patch.object(jobs, 'collect_translations', side_effect=RuntimeError('upstream failure')):
            with self.assertRaises(RuntimeError):
                jobs.execute(job)
        self.assertEqual(self.client.get('/data/galleries.json').json()[0]['title'], 'source')

    def test_successful_sync_preserves_overrides_and_printed(self):
        self.save('overrides', {'123': {'title': '人工'}})
        job = self.claim('all')
        with patch.object(jobs, 'collect_favorites', return_value=[dict(GALLERY, title='changed')]), \
             patch.object(jobs, 'collect_translations', return_value={'data': []}), \
             patch.object(jobs, 'collect_daily', return_value=[{'name': 'test', 'galleries': [GALLERY]}]):
            jobs.execute(job)
        self.assertEqual(self.client.get('/data/galleries.json').json()[0]['title'], '人工')
        self.assertEqual(self.client.get('/data/daily_search.json').json()[0]['galleries'][0]['title'], '人工')
        self.assertEqual(len(read_books(self.client.get('/data/future_digi.csv').text)), 1)
        self.assertEqual(jobs.runs()[0]['conclusion'], 'success')

    def test_shrink_guard_rolls_back_and_daily_config_race(self):
        with db.connect() as con:
            db.replace_galleries(con, [dict(GALLERY, gid=i) for i in range(1, 11)])
        job = self.claim('favorites')
        with patch.object(jobs, 'collect_favorites', return_value=[GALLERY]):
            with self.assertRaises(jobs.JobFailure):
                jobs.execute(job)
        self.assertEqual(len(self.client.get('/data/galleries.json').json()), 10)
        job = self.claim('daily')
        def scrape(groups):
            self.save('daily', [dict(self.daily[0], name='changed')])
            return []
        with patch.object(jobs, 'collect_daily', side_effect=scrape):
            with self.assertRaises(jobs.JobFailure):
                jobs.execute(job)
        self.assertEqual(len(self.client.get('/data/daily_search.json').json()), 1)

    def test_media_blocks_ssrf_and_redirect_cookie_leaks(self):
        from backend.upstream import validate_url, fetch
        from fastapi import HTTPException
        for url in ('http://exhentai.org/s/foo/123-1', 'https://localhost/x', 'https://exhentai.org.evil.example/x',
                    'https://user:pass@exhentai.org/x', 'https://exhentai.org:8443/x'):
            with self.assertRaises(HTTPException):
                validate_url(url, gallery=True)
        with patch('socket.getaddrinfo', return_value=[(0, 0, 0, '', ('127.0.0.1', 443))]):
            with self.assertRaises(HTTPException):
                validate_url('https://exhentai.org/x', gallery=True)
        self.assertEqual(self.client.get('/api/image-url', params={'pageUrl': 'https://localhost/.env'}).status_code, 400)

    def test_translation_contract_cache_and_no_upstream_error_leak(self):
        for name, value in [('LLM_API_BASE', 'https://llm.example/v1'), ('LLM_API_KEY', 'fake-key')]:
            with patch('backend.upstream.validate_url'):
                security.replace_credential(name, value)
        body = {'password': 'trans-test', 'texts': ['おはよう'], 'previous': [['名前', '名字']], 'glossary': {'名前': '名字'}}
        with patch.object(translation, 'json_request', return_value={'choices': [{'message': {'content': '{"1":{"t":"早上好","k":"dialogue","a":null}}'}}]}) as upstream:
            response = self.client.post('/api/trans-translate', json=body)
            self.assertEqual(response.status_code, 200, response.text)
            self.assertEqual(response.json()['translations'][0]['t'], '早上好')
            self.assertTrue(self.client.post('/api/trans-translate', json=body).json()['cached'])
            self.assertEqual(upstream.call_count, 1)
        body['texts'] = ['別の言葉']
        with patch.object(translation, 'json_request', side_effect=RuntimeError('private-key-upstream-text')):
            response = self.client.post('/api/trans-translate', json=body)
            self.assertEqual(response.status_code, 502)
            self.assertNotIn('private-key', response.text)

    def test_ocr_sources_and_persistent_quota_fallback(self):
        security.replace_credential('GOOGLE_VISION_API_KEY', 'fake-vision-key')
        body = {'password': 'trans-test', 'imageBase64': base64.b64encode(b'fake-jpg').decode(), 'ocrSource': 'google'}
        with patch.object(translation, 'json_request', return_value={'responses': [{}]}):
            result = self.client.post('/api/trans-ocr', json=body)
            self.assertEqual(result.status_code, 200, result.text)
            self.assertEqual(result.json()['source'], 'vision')
        self.assertTrue(self.client.post('/api/trans-ocr', json=body).json()['cached'])
        month = 'vision:' + time.strftime('%Y-%m', time.gmtime())
        with db.connect() as con:
            con.execute('UPDATE counters SET count=1000 WHERE key=?', (month,))
        body['imageBase64'] = base64.b64encode(b'another-image').decode()
        with patch.object(translation, 'paddle', return_value=[]) as paddle:
            result = self.client.post('/api/trans-ocr', json=body)
            self.assertEqual(result.json()['source'], 'paddle')
            paddle.assert_called_once()

    def test_full_migration_matches_repository_and_refuses_second_import(self):
        # Clear fixture tables, then exercise the real one-time migration.
        with db.connect() as con:
            for table in ('resources','resource_versions','galleries','books','daily_rules','gallery_overrides'):
                con.execute(f'DELETE FROM {table}')
        initialize_data()
        source = json.loads((settings.ROOT / 'web-static/public/data/galleries.json').read_text())
        self.assertEqual(len(self.client.get('/data/galleries.json').json()), len(source))
        with self.assertRaises(RuntimeError):
            initialize_data()


if __name__ == '__main__':
    unittest.main()
