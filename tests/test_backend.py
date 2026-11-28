"""Integration tests use a temporary SQLite database and fake upstream services."""
import base64
import asyncio
import copy
import gzip
import json
import os
import socket
import sqlite3
import tempfile
import time
import unittest
import httpx
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from unittest.mock import patch, Mock
from cryptography.fernet import Fernet
from fastapi.testclient import TestClient
from backend import db, settings, operations, jobs, security, translation, services, upstream, media
from backend.main import app, load_page_image
from backend.cli import initialize_data, backup
from backend.validation import read_books, books_csv

GALLERY = {'gid': 123, 'token': 'abcdef1234', 'title': 'source', 'title_jpn': '', 'tags': ['artist:test'],
           'category': 'Manga', 'posted': '1770000000', 'favTime': '2026-11-01 12:00'}
DICTIONARY = {'data': [{'namespace': 'artist', 'data': {'test': {'name': '测试'}}}]}
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

    def test_atomic_rate_limit_under_concurrent_requests_and_expiry(self):
        with ThreadPoolExecutor(max_workers=20) as pool:
            allowed = list(pool.map(lambda _: db.reserve('concurrent-test', 10, 60), range(50)))
        self.assertEqual(sum(allowed), 10)
        self.assertFalse(db.reserve('concurrent-test', 10, 60))
        with db.connect() as con:
            con.execute('UPDATE counters SET expires=0 WHERE key=?', ('concurrent-test',))
        self.assertTrue(db.reserve('concurrent-test', 10, 60))
        with db.connect() as con:
            row = con.execute('SELECT count FROM counters WHERE key=?', ('concurrent-test',)).fetchone()
            self.assertEqual(row['count'], 1)

    def test_request_id_and_safe_failure_log(self):
        with patch('backend.main.catalog.list_galleries', side_effect=RuntimeError('secret-key=TOPSECRET')):
            with self.assertLogs('nohentai.api', level='ERROR') as logs:
                response = self.client.get('/api/galleries')
        self.assertEqual(response.status_code, 502)
        request_id = response.headers['X-Request-ID']
        self.assertEqual(len(request_id), 32)
        self.assertIn(request_id, logs.output[0])
        self.assertNotIn('TOPSECRET', '\n'.join(logs.output))

    def test_preview_disables_external_calls_before_transport(self):
        with patch.dict(os.environ, {'NOHENTAI_DISABLE_UPSTREAM': '1'}), patch('backend.upstream.httpx.Client') as transport:
            for action in (lambda: upstream.fetch('https://e-hentai.org/'),
                           lambda: upstream.json_request('GET', 'https://jisho.org/')):
                with self.assertRaises(Exception) as error:
                    action()
                self.assertEqual(error.exception.status_code, 503)
            transport.assert_not_called()

    def test_upstream_json_response_is_bounded(self):
        client_type = httpx.Client
        with patch('backend.upstream.validate_url', side_effect=lambda url: url):
            for payload, expected_status in ((b'{"ok":true}', None), (b' ' * (upstream.MAX_JSON + 1), 502)):
                transport = httpx.MockTransport(lambda request: httpx.Response(200, content=payload))
                with patch('backend.upstream.httpx.Client', side_effect=lambda **kwargs: client_type(transport=transport)):
                    if expected_status is None:
                        self.assertEqual(upstream.json_request('GET', 'https://jisho.org/api'), {'ok': True})
                    else:
                        with self.assertRaises(Exception) as error:
                            upstream.json_request('GET', 'https://jisho.org/api')
                        self.assertEqual(error.exception.status_code, expected_status)

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
        existing = self.admin('records', kind='book').json()['items'][0]
        book = dict(BOOK, **{'书名': '测试,"第一本"', '备注': '多行\r\n第二行'})
        self.assertEqual(self.admin('record-save', kind='book', id=existing['id'], version=existing['version'], data=book).status_code, 200)
        self.assertEqual(self.admin('record-save', kind='book', version='0', data=BOOK).status_code, 200)
        self.assertEqual(read_books(self.client.get('/data/future_digi.csv').text), [book, BOOK])
        self.assertEqual(self.admin('record-save', kind='book', version='0', data=dict(BOOK, sid='999')).status_code, 400)
        with db.connect() as con:
            db.put_resource(con, 'printed', [dict(BOOK, sid='999')])
        existing = self.admin('records', kind='book').json()['items'][0]
        response = self.admin('record-save', kind='book', id=existing['id'], version=existing['version'], data=dict(BOOK, sid='999'))
        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.json()['warnings'])

    def test_validation_rejects_secret_fields_and_unknown_galleries(self):
        for name, data in [('translate', {'apiKey': 'secret'}), ('overrides', {'123': {'token': 'replace'}}),
                           ('overrides', {'999': {'title': 'new'}}), ('translate', {'model':'test','jsonMode':False,'defaultOcr':'bad'})]:
            self.assertEqual(self.save(name, data).status_code, 400, (name, data))

    def test_service_secrets_encrypted_and_legacy_writer_retired(self):
        value = 'test-private-ocr-token'
        group = next(g for g in services.status()['groups'] if g['id'] == 'ocr')
        response = self.admin('service-save', service='ocr', version=group['version'], values={'OCR_SPACE_KEY':value})
        self.assertEqual(response.status_code, 200, response.text)
        self.assertEqual(security.credential('OCR_SPACE_KEY'), value)
        with db.connect() as con:
            self.assertNotIn(value, con.execute('SELECT ciphertext FROM credentials').fetchone()[0])
            self.assertNotIn(value, str([tuple(r) for r in con.execute('SELECT * FROM history')]))
        self.assertNotIn(value, self.admin('platforms').text)
        self.assertEqual(self.admin('replace-secret', platform='server', name='OCR_SPACE_KEY', value='bad').status_code, 410)
        group = next(g for g in services.status()['groups'] if g['id'] == 'translate')
        for values in ({'ADMIN_PASSWORD':'bad'}, {'TRANS_PASSWORD':os.environ['ADMIN_PASSWORD']}):
            self.assertEqual(self.admin('service-save', service='translate', version=group['version'], values=values).status_code, 400)

    def test_counters_atomic_cache_and_backup(self):
        with ThreadPoolExecutor(max_workers=10) as pool:
            outcomes = list(pool.map(lambda _: db.reserve('quota', 3, 60), range(20)))
        self.assertEqual(sum(outcomes), 3)
        db.set_cache('test', {'ok': True}, 60)
        self.assertEqual(db.get_cache('test'), {'ok': True})
        db.set_cache('expired', {'ok': True}, -1)
        self.assertIsNone(db.get_cache('expired'))
        path = backup()
        self.assertTrue(path.name.endswith('.sqlite3.gz'))
        restored = path.parent / 'restore.sqlite3'
        restored.write_bytes(gzip.decompress(path.read_bytes()))
        con = sqlite3.connect(restored)
        self.assertEqual(con.execute('PRAGMA integrity_check').fetchone()[0], 'ok')
        self.assertEqual(con.execute('SELECT COUNT(*) FROM galleries').fetchone()[0], 1)
        con.close()
        with self.assertRaises(RuntimeError):
            initialize_data()

    def test_backup_rotation_with_legacy_files_and_failed_compression(self):
        directory = settings.DATA_DIR / 'backups'
        directory.mkdir()
        legacy = []
        for day in range(1, 8):
            path = directory / f'nohentai-202501{day:02}T000000000000Z.sqlite3'
            path.touch()
            path.with_suffix('.media.zip').touch()
            legacy.append(path)
        with patch('backend.cli.shutil.copyfileobj', side_effect=OSError('disk full')):
            with self.assertRaises(OSError):
                backup()
        self.assertEqual(len(list(directory.iterdir())), 14)
        newest = backup()
        items = operations.backups()['items']
        self.assertEqual([item['name'] for item in items], [newest.name] + [p.name for p in reversed(legacy[1:])])
        self.assertEqual(operations.backup_file(legacy[-1].name), legacy[-1])
        self.assertFalse(legacy[0].with_suffix('.media.zip').exists())

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
             patch.object(jobs, 'collect_translations', return_value=DICTIONARY), \
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
            rule = self.admin('records', kind='daily').json()['items'][0]
            self.admin('record-save', kind='daily', id=rule['id'], version=rule['version'], data=dict(self.daily[0], name='changed'))
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
                services.save(services.FIELDS[name][0], next(g for g in services.status()['groups'] if g['id']==services.FIELDS[name][0])['version'], {name:value})
        body = {'password': 'trans-test', 'texts': ['おはよう'],
                'context': {'title': '测试标题', 'tags': ['artist:test-artist']},
                'previous': [['前頁原文', '前页译文']], 'glossary': {'名前': '名字'}}
        with patch.object(translation, 'json_request', return_value={'choices': [{'message': {'content': '{"1":{"t":"早上好","k":"dialogue","a":null}}'}}]}) as upstream:
            response = self.client.post('/api/trans-translate', json=body)
            self.assertEqual(response.status_code, 200, response.text)
            self.assertEqual(response.json()['translations'][0]['t'], '早上好')
            messages = upstream.call_args.kwargs['json']['messages']
            self.assertEqual(messages[1], {'role': 'system', 'content':
                             '本作标题：测试标题\n\n术语表（原文→译文，必须遵守）：\n名前 → 名字'})
            self.assertEqual(json.loads(messages[2]['content']), {'1': 'おはよう'})
            body['context']['tags'] = []
            body.pop('previous')
            self.assertTrue(self.client.post('/api/trans-translate', json=body).json()['cached'])
            self.assertEqual(upstream.call_count, 1)
        body['texts'] = ['別の言葉']
        with patch.object(translation, 'json_request', side_effect=RuntimeError('private-key-upstream-text')):
            response = self.client.post('/api/trans-translate', json=body)
            self.assertEqual(response.status_code, 502)
            self.assertNotIn('private-key', response.text)

    def test_google_fallback_preserves_positions_and_quota(self):
        with patch.dict(os.environ, {'GOOGLE_TRANSLATE_API_KEY':'fixture', 'GOOGLE_TRANSLATE_MONTHLY_CHARS':'4',
                                    'LLM_API_BASE':'https://example.org', 'LLM_API_KEY':'fixture'}):
            google = {'data': {'translations':[{'translatedText':'补译'}]}}
            with patch.object(translation, 'ai_translate', return_value=[None, {'t':'成功'}]), patch.object(
                    translation, 'json_request', return_value=google) as call:
                result = translation.translate({'texts':['第一', '第二']})
                self.assertEqual(result['translations'], [{'t':'补译','source':'google'}, {'t':'成功'}])
                self.assertEqual(call.call_args.kwargs['json']['q'], ['第一'])
                self.assertTrue(translation.translate({'texts':['第一', '第二']})['cached'])
                with patch.object(translation, 'ai_translate', side_effect=ValueError()):
                    self.assertEqual(translation.translate({'texts':['第三']})['translations'][0]['source'], 'google')
                    self.assertEqual(translation.translate({'texts':['第四']})['translations'], [None])
                self.assertEqual(call.call_count, 2)

    def test_explicit_translation_engines_route_and_cache_independently(self):
        body = {'password': 'trans-test', 'texts': ['おはよう']}
        with patch.dict(os.environ, {'GOOGLE_TRANSLATE_API_KEY': 'fixture', 'GOOGLE_TRANSLATE_MONTHLY_CHARS': '5',
                                    'LLM_API_BASE': 'https://example.org', 'LLM_API_KEY': 'fixture'}):
            google = {'data': {'translations': [{'translatedText': '普通译文'}]}}
            with patch.object(translation, 'ai_translate', return_value=[{'t': '模型译文'}]) as model, patch.object(
                    translation, 'json_request', return_value=google) as upstream:
                def request(engine, **changes):
                    return self.client.post('/api/trans-translate', json=dict(body, engine=engine) | changes)

                self.assertEqual(request('google').json()['translations'], [{'t': '普通译文', 'source': 'google'}])
                model.assert_not_called()
                self.assertTrue(request('google').json()['cached'])
                upstream.assert_called_once()
                self.assertEqual(request('model', glossary={'名前': '名字'}).json()['translations'], [{'t': '模型译文'}])
                self.assertIn('名前 → 名字', model.call_args.args[1])
                self.assertFalse(request('model').json().get('cached', False))
                self.assertTrue(request('model').json()['cached'])
                self.assertEqual(request('google', texts=['おやすみ']).status_code, 429)
                self.assertEqual(request('other').status_code, 400)
                model.side_effect = ValueError()
                self.assertGreaterEqual(request('model', texts=['別の言葉']).status_code, 400)
                upstream.assert_called_once()
            with patch.dict(os.environ, {'GOOGLE_TRANSLATE_API_KEY': ''}):
                response = self.client.post('/api/trans-translate', json=dict(body, engine='google'))
                self.assertEqual(response.status_code, 503)

    def test_history_displays_retired_tasks_without_allowing_reruns(self):
        with db.connect() as con:
            run_id = con.execute(
                "INSERT INTO jobs(kind,status,conclusion,created_at,updated_at) VALUES (?,?,?,?,?)",
                ('retired-example', 'completed', 'failure', db.now(), db.now()),
            ).lastrowid
        history = self.client.post('/api/admin', json={'action': 'runs', 'password': self.token, 'page': 1})
        self.assertTrue(history.json()['runs'][0]['retired'])
        detail = self.client.post('/api/admin', json={'action': 'job-detail', 'password': self.token, 'runId': run_id})
        self.assertEqual(detail.json()['run']['name'], '已停用的任务')
        retry = self.client.post('/api/admin', json={'action': 'rerun', 'password': self.token, 'runId': run_id})
        self.assertEqual(retry.status_code, 400)

    def test_page_image_retries_with_nl_and_versions_bytes(self):
        page = 'https://e-hentai.org/s/abc/123-1'
        first = 'https://ehgt.org/old.jpg'
        second = 'https://ehgt.org/new.jpg'
        with patch('backend.media.validate_url'), patch('backend.media.fetch_page') as fetch:
            fetch.side_effect = [
                (b"""<img id="img" src="https://ehgt.org/old.jpg"><a id="loadfail" onclick="nl('next')"></a>""", 'text/html'),
                httpx.HTTPStatusError('gone', request=httpx.Request('GET', first), response=httpx.Response(404)),
                (f'<img id="img" src="{second}">'.encode(), 'text/html'),
                (b'image bytes', 'image/jpeg'),
            ]
            response = self.client.get('/api/page-image', params={'pageUrl': page})
            self.assertEqual(response.status_code, 200)
            self.assertEqual(response.content, b'image bytes')
            self.assertEqual(response.headers['cache-control'], 'private, max-age=900')
            self.assertIn('etag', response.headers)
            self.assertEqual(fetch.call_args_list[2].args[0], page + '?nl=next')
            self.assertEqual(db.get_cache('image-url:' + page)['imageUrl'], second)

        with patch('backend.media.validate_url'), patch('backend.media.fetch_page') as fetch:
            fetch.return_value = (b'<img id="img" src="https://ehgt.org/509.gif">', 'text/html')
            response = self.client.get('/api/page-image', params={'pageUrl': page}, headers={'X-Page-Image-Refresh': '1'})
            self.assertEqual(response.status_code, 509)
            self.assertEqual(response.json()['code'], 'quota_exhausted')
            self.assertEqual(response.headers['cache-control'], 'no-store')
            fetch.assert_called_once()

    def test_page_image_live_requires_session_and_disables_cache(self):
        params = {'site': 'e-hentai.org', 'pageUrl': 'https://e-hentai.org/s/abc/123-1'}
        self.assertEqual(self.client.get('/api/page-image', params=params).status_code, 401)
        self.client.post('/api/trans-verify', json={'password': 'trans-test'})
        with patch('backend.media.page_image', return_value=(b'image', 'image/png')) as load:
            response = self.client.get('/api/page-image', params=params)
            self.assertEqual(response.status_code, 200)
            self.assertEqual(response.headers['cache-control'], 'private, no-store')
            self.assertEqual(load.call_args.args[0], params['pageUrl'])
            self.assertEqual(load.call_args.kwargs, {'persistent': False})

    def test_page_image_budget_includes_in_progress_download(self):
        async def slow_fetch(url, client, *, image=False):
            if image:
                await asyncio.Event().wait()
            return b'<img id="img" src="https://ehgt.org/page.jpg">', 'text/html'

        with patch.object(media, 'PAGE_IMAGE_TIMEOUT', .05), patch.object(media, 'fetch_page', side_effect=slow_fetch):
            result = self.client.get('/api/page-image', params={'pageUrl': 'https://e-hentai.org/s/abc/123-1'},
                                     headers={'X-Page-Image-Refresh': '1'})
        self.assertEqual(result.status_code, 504)
        self.assertEqual(result.json()['code'], 'page_timeout')

    def test_page_image_dns_failure_switches_to_another_node(self):
        requests = []

        def resolve(host, *args, **kwargs):
            if host == 'old.hath.network':
                raise socket.gaierror(socket.EAI_AGAIN, 'temporary DNS failure')
            return [(0, 0, 0, '', ('91.193.7.122', 443))]

        def upstream_response(request):
            requests.append(request)
            if request.url.host == 'e-hentai.org':
                if 'nl' in request.url.params:
                    return httpx.Response(200, text='<img id="img" src="https://new.hath.network/image.jpg">')
                return httpx.Response(200, text=(
                    '<img id="img" src="https://old.hath.network/image.jpg">'
                    '<a id="loadfail" onclick="nl(\'next\')"></a>'
                ))
            return httpx.Response(200, content=b'image', headers={'Content-Type': 'image/jpeg'})

        client = httpx.AsyncClient(transport=httpx.MockTransport(upstream_response))
        try:
            with patch.object(app.state, 'page_client', client), patch('socket.getaddrinfo', side_effect=resolve):
                response = self.client.get('/api/page-image', params={'pageUrl': 'https://e-hentai.org/s/abc/123-1'})
        finally:
            self.client.portal.call(client.aclose)
        self.assertEqual((response.status_code, response.content), (200, b'image'))
        self.assertEqual([request.url.host for request in requests], ['e-hentai.org', 'e-hentai.org', 'new.hath.network'])
        self.assertEqual(requests[1].url.params.get('nl'), 'next')

    def test_page_image_does_not_switch_nodes_when_local_pool_is_busy(self):
        with patch.object(media, 'fetch_page', side_effect=httpx.PoolTimeout('pool busy')) as fetch:
            response = self.client.get('/api/page-image', params={'pageUrl': 'https://e-hentai.org/s/abc/123-1'},
                                       headers={'X-Page-Image-Refresh': '1'})
        self.assertEqual((response.status_code, response.json()['code']), (503, 'pool_busy'))
        fetch.assert_awaited_once()

    def test_concurrent_page_images_share_downloads_within_cache_policy(self):
        async def check():
            release = asyncio.Event()
            entered = 0

            async def download(*args, **kwargs):
                await release.wait()
                return b'image', 'image/jpeg'

            async def record_request(*args, **kwargs):
                nonlocal entered
                entered += 1
                if entered == 3:
                    release.set()
                return await load_page_image(*args, **kwargs)

            async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url='http://testserver') as client:
                async def get(refresh=False):
                    return await client.get('/api/page-image', params={'pageUrl': 'https://e-hentai.org/s/abc/123-1'},
                                            headers={'X-Page-Image-Refresh': str(int(refresh))})

                with patch.object(media, 'page_image', side_effect=download) as load, \
                     patch('backend.main.load_page_image', side_effect=record_request):
                    results = await asyncio.wait_for(asyncio.gather(get(), get(), get(True)), timeout=5)
                    self.assertEqual([result.status_code for result in results], [200, 200, 200])
                    self.assertEqual(load.await_count, 2)

        self.client.portal.call(check)

    def test_page_image_disconnect_only_cancels_after_last_waiter_leaves(self):
        async def check():
            page_url = 'https://e-hentai.org/s/abc/123-1'
            started = asyncio.Event()
            released = asyncio.Event()
            cancelled = asyncio.Event()

            async def download(*args, **kwargs):
                started.set()
                try:
                    await released.wait()
                    return b'image', 'image/jpeg'
                except asyncio.CancelledError:
                    cancelled.set()
                    raise

            async def connect(disconnect):
                request_sent = False
                responses = []

                async def receive():
                    nonlocal request_sent
                    if not request_sent:
                        request_sent = True
                        return {'type': 'http.request', 'body': b''}
                    await disconnect.wait()
                    return {'type': 'http.disconnect'}

                async def send(message):
                    responses.append(message)

                await app({
                    'type': 'http', 'asgi': {'version': '3.0', 'spec_version': '2.4'},
                    'http_version': '1.1', 'scheme': 'http', 'method': 'GET', 'path': '/api/page-image',
                    'query_string': f'pageUrl={page_url}'.encode(), 'headers': [],
                    'client': ('127.0.0.1', 10000), 'server': ('testserver', 80),
                }, receive, send)
                return next(message['status'] for message in responses if message['type'] == 'http.response.start')

            with patch.object(media, 'page_image', side_effect=download) as load:
                first, second = asyncio.Event(), asyncio.Event()
                a = asyncio.create_task(connect(first))
                await asyncio.wait_for(started.wait(), timeout=3)
                b = asyncio.create_task(connect(second))
                key = (page_url, True)
                for _ in range(100):
                    if app.state.page_requests[key].waiters == 2:
                        break
                    await asyncio.sleep(.01)
                self.assertEqual(app.state.page_requests[key].waiters, 2)
                first.set()
                self.assertEqual(await asyncio.wait_for(a, timeout=3), 499)
                self.assertEqual(app.state.page_requests[key].waiters, 1)
                self.assertFalse(cancelled.is_set())
                released.set()
                self.assertEqual(await asyncio.wait_for(b, timeout=3), 200)
                self.assertEqual(load.await_count, 1)

                released.clear()
                started.clear()
                last = asyncio.Event()
                c = asyncio.create_task(connect(last))
                await asyncio.wait_for(started.wait(), timeout=3)
                last.set()
                self.assertEqual(await asyncio.wait_for(c, timeout=3), 499)
                self.assertTrue(cancelled.is_set())
                self.assertNotIn(key, app.state.page_requests)

        self.client.portal.call(check)

    def test_gallery_directory_fetches_only_the_requested_part(self):
        first_url = 'https://exhentai.org/g/123/abcde/'
        params = {'gid': '123', 'token': 'abcde', 'part': 1, 'source': 'exhentai.org'}
        gallery = b"""<table id="gdd"><tr><td class="gdt1">Length:</td><td>21 pages</td></tr></table>
            <div id="gdt"><a href="/s/abc/123-21"></a></div>
            <table class="ptt"><tr><td>1</td><td class="ptds">2</td></tr></table>"""
        db.set_cache('gallery-part:exhentai.org:123:abcde:1', {
            'total': 21, 'images': [{'pageNum': 1}], 'partCount': 2, 'source': 'exhentai.org'
        }, 900)
        with patch('backend.media.fetch', return_value=(gallery, 'text/html')) as fetch:
            response = self.client.get('/api/gallery-images/part', params=params)
            self.assertEqual(response.status_code, 200)
            self.assertEqual(response.json()['images'][0]['pageUrl'], 'https://exhentai.org/s/abc/123-21')
            fetch.assert_called_once_with(first_url + '?p=1', gallery=True)

    def test_gallery_directory_rejects_redirected_part_before_caching(self):
        first = b"""<table id="gdd"><tr><td class="gdt1">Length:</td><td>2 pages</td></tr></table>
            <div id="gdt"><a href="/s/abc/123-1"></a></div>
            <table class="ptt"><tr><td class="ptds">1</td><td>2</td></tr></table>"""
        params = {'gid': '123', 'token': 'abcde', 'part': 1, 'source': 'exhentai.org'}
        with patch('backend.media.fetch', return_value=(first, 'text/html')):
            response = self.client.get('/api/gallery-images/part', params=params)
        self.assertEqual(response.status_code, 502)
        self.assertIn('错误的目录分页', response.json()['error'])
        self.assertIsNone(db.get_cache('gallery-part:v2:exhentai.org:123:abcde:1'))

    def test_live_session_search_read_and_expire(self):
        urls = ['/api/live/search', '/api/live/directory?site=e-hentai.org&gid=2&token=abcde',
                '/api/live/image-url?site=e-hentai.org&pageUrl=https://e-hentai.org/s/abc/2-1',
                '/api/live/image?site=e-hentai.org&imageUrl=https://ehgt.org/p.png']
        for url in urls:
            self.assertEqual(self.client.get(url).status_code, 401)
        response = self.client.post('/api/trans-verify', json={'password':'trans-test'})
        self.assertIn('HttpOnly', response.headers['set-cookie'])
        self.assertIn('Max-Age=259200', response.headers['set-cookie'])
        with patch('time.time', return_value=time.time() + 71 * 3600):
            self.assertEqual(self.client.post('/api/trans-verify', json={}).status_code, 200)
        self.assertEqual(self.client.post('/api/trans-verify', json={}).status_code, 200)
        with patch('backend.live.document', return_value=b'No hits found'), patch('backend.db.set_cache', side_effect=AssertionError):
            self.assertEqual(self.client.get(urls[0]).json()['items'], [])
            with patch.dict(os.environ, {'LIVE_SITE':'exhentai.org'}):
                self.assertEqual(self.client.get(urls[1]).status_code, 409)
                self.assertEqual(self.client.get(urls[0]).json()['site'], 'exhentai.org')
        with db.connect() as con:
            db.put_snapshot(con, 'translations', {'data':[{'namespace':'language','data':{'chinese':{'name':'汉语'}}}]})
        listing = b"""<table class="itg"><tr><td class="gl3c"><a href="/g/2/abcde/">
            <div class="glink">Fixture title</div></a><div class="gt" title="language:chinese"></div>
            <div class="gt" title="other:unlisted"></div></td></tr></table>
            <a id="uprev" href="/?prev=5">Prev</a><a id="unext" href="/?next=2">Next</a>"""
        gallery = b"""<h1 id="gn">Fixture title</h1><div id="gdc">Manga</div><div id="gdn"><a>Fixture author</a></div><table id="gdd"><tr><td class="gdt1">Length:</td>
            <td>2 pages</td></tr></table><div id="gdt"><a href="/s/aa/2-2"></a></div>"""
        with patch('backend.live.document', side_effect=[listing, gallery]) as fetch, patch(
                'backend.db.get_cache', side_effect=AssertionError), patch('backend.db.set_cache', side_effect=AssertionError):
            page = self.client.get(urls[0], params={'q':'sample', 'prev':'7', 'f_cats':1019}).json()
            self.assertEqual((page['items'][0]['title'], page['prev'], page['next']), ('Fixture title','5','2'))
            self.assertEqual(page['items'][0]['tagLabels'], ['汉语', 'unlisted'])
            response = self.client.get(urls[1]+'&part=1&details=true')
            self.assertEqual(response.json()['gallery']['category'], 'Manga')
            self.assertEqual(response.json()['gallery']['uploader'], 'Fixture author')
            self.assertEqual(response.headers['cache-control'], 'no-store')
            self.assertEqual(response.json()['images'][0]['pageUrl'],'https://e-hentai.org/s/aa/2-2')
            self.assertIn('prev=7', fetch.call_args_list[0].args[0])
            self.assertIn('f_cats=1019', fetch.call_args_list[0].args[0])
            self.assertEqual(fetch.call_args_list[1].args[0], 'https://e-hentai.org/g/2/abcde/?p=1')
        with patch('backend.media.fetch', return_value=(b'<img id="img" src="https://ehgt.org/p.png">','text/html')), patch(
                'backend.media.validate_url'), patch('backend.db.set_cache', side_effect=AssertionError):
            self.assertEqual(self.client.get(urls[2]).json()['imageUrl'], 'https://ehgt.org/p.png')
        with patch('time.time', return_value=time.time()+security.COST_TTL+1):
            self.assertEqual(self.client.get(urls[0]).status_code, 401)
        with patch.dict(os.environ, {'TRANS_PASSWORD':'rotated'}):
            self.assertEqual(self.client.post('/api/trans-verify',json={}).status_code, 401)

    def test_ocr_sources_and_persistent_quota_fallback(self):
        services.save('ocr', next(g for g in services.status()['groups'] if g['id']=='ocr')['version'], {'GOOGLE_VISION_API_KEY':'fake-vision-key'})
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
