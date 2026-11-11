"""Regression contracts from the 2026-11-04 review; no live upstream calls."""
import json
import unittest
from datetime import datetime, timezone
from unittest.mock import patch
from fastapi import HTTPException
import test_backend as fixtures
from backend import db, jobs, media, operations, security, services
from app.sync_translations import validate_dictionary, validate_and_parse


class ReviewRegressionTests(unittest.TestCase):
    setUp = fixtures.BackendTests.setUp
    tearDown = fixtures.BackendTests.tearDown
    admin = fixtures.BackendTests.admin
    claim = fixtures.BackendTests.claim

    def test_retired_bulk_writers_preserve_record_identity_and_audit(self):
        for resource, kind in [('printed', 'book'), ('daily', 'daily')]:
            before = self.admin('records', kind=kind).json()
            old = self.admin('load', resource=resource).json()
            response = self.admin('save', resource=resource, sha=old['sha'], data=list(reversed(old['data'])))
            self.assertEqual(response.status_code, 410)
            self.assertEqual(self.admin('records', kind=kind).json(), before)
            self.assertEqual(self.admin('load', resource=resource).json(), old)

    def test_retired_credential_writer_cannot_shadow_current_settings(self):
        with patch('backend.upstream.validate_url'):
            group = next(g for g in services.status()['groups'] if g['id'] == 'translate')
            services.save('translate', group['version'], {'LLM_API_BASE':'https://first.example/v1'})
        response = self.admin('replace-secret', platform='server', name='LLM_API_BASE', value='https://second.example/v1')
        self.assertEqual(response.status_code, 410)
        self.assertEqual(security.credential('LLM_API_BASE'), 'https://first.example/v1')
        with db.connect() as con:
            self.assertIsNone(con.execute("SELECT 1 FROM credentials WHERE name='LLM_API_BASE'").fetchone())

    def test_legacy_override_write_uses_record_history(self):
        old = self.admin('load', resource='overrides').json()
        response = self.admin('save', resource='overrides', sha=old['sha'], data={'123':{'title':'audited'}})
        self.assertEqual(response.status_code, 200, response.text)
        history = self.admin('record-history', kind='gallery', id='123').json()['items']
        self.assertEqual(history[0]['after']['title'], 'audited')

    def test_dictionary_schema_rejects_corrupt_and_empty_snapshots(self):
        for data in ({}, {'data':[]}, {'data':{}}, {'data':[{'namespace':'female','data':['bad']}]},
                     {'data':[{'namespace':'female','data':{'tag':{'name':12}}}]},
                     {'data':[{'namespace':'female','data':{}},{'namespace':'female','data':{}}]}):
            with self.subTest(data=data), self.assertRaises(ValueError):
                validate_and_parse(json.dumps(data).encode())
        self.assertEqual(validate_dictionary(fixtures.DICTIONARY), fixtures.DICTIONARY)
        self.assertEqual(validate_dictionary(fixtures.DICTIONARY, {'data':['old corruption']}), fixtures.DICTIONARY)

    def test_bad_dictionary_never_publishes_or_invalidates_public_catalog(self):
        with db.connect() as con:
            before = db.snapshot(con, 'translations')
            revision = db.snapshot(con, 'catalog-revision')
        job = self.claim('translations')
        for invalid in ({'data':[]}, {'data':[{'namespace':'artist','data':['bad']}]}):
            with patch.object(jobs, 'collect_translations', return_value=invalid), self.assertRaises(jobs.JobFailure):
                jobs.execute(job)
            with db.connect() as con:
                self.assertEqual(db.snapshot(con, 'translations'), before)
                self.assertEqual(db.snapshot(con, 'catalog-revision'), revision)
                self.assertNotEqual(con.execute('SELECT conclusion FROM jobs WHERE id=?',(job,)).fetchone()[0], 'success')
        self.assertEqual(self.client.get('/api/galleries').status_code, 200)

    def test_dictionary_drop_guard_preserves_previous_snapshot(self):
        previous = {'data':[{'namespace':'artist','data':{str(i):{'name':'test'} for i in range(10)}}]}
        with db.connect() as con: db.put_snapshot(con, 'translations', previous)
        job = self.claim('translations')
        with patch.object(jobs, 'collect_translations', return_value=fixtures.DICTIONARY), self.assertRaises(jobs.JobFailure):
            jobs.execute(job)
        with db.connect() as con: self.assertEqual(db.snapshot(con,'translations'), previous)

    def test_gallery_incomplete_duplicate_and_missing_pages_are_not_cached(self):
        for numbers in ([1,2], [1,1,3], [1,2,4]):
            parsed = (3, [{'pageNum':n,'pageUrl':str(n)} for n in numbers], 1)
            with self.subTest(numbers=numbers), patch.object(media,'gallery_page',return_value=parsed), patch.object(db,'get_cache',return_value=None), patch.object(db,'set_cache') as cache:
                with self.assertRaises(HTTPException): media.gallery_images('123','abcdef1234')
                cache.assert_not_called()

    def test_image_refresh_bypasses_stale_server_cache_even_without_nl(self):
        url = 'https://e-hentai.org/s/abcde/123-1'
        stale = {'imageUrl':'https://ehgt.org/expired.jpg','nlParam':None}
        with patch.object(media,'validate_url'), patch.object(db,'get_cache',return_value=stale), patch.object(db,'set_cache'), patch.object(media,'fetch',return_value=(b'<img id="img" src="https://ehgt.org/fresh.jpg">','text/html')) as fetch:
            self.assertEqual(media.image_url(url), stale)
            self.assertEqual(media.image_url(url, refresh=True)['imageUrl'], 'https://ehgt.org/fresh.jpg')
            fetch.assert_called_once()

    def test_workbench_password_length_matches_authentication(self):
        group = next(g for g in services.status()['groups'] if g['id']=='translate')
        response = self.admin('service-save', service='translate', version=group['version'], values={'TRANS_PASSWORD':'x'*1025})
        self.assertEqual(response.status_code,400)
        self.assertEqual(security.credential('TRANS_PASSWORD'),'trans-test')
        response = self.admin('service-save', service='translate', version=group['version'], values={'TRANS_PASSWORD':'x'*1024})
        self.assertEqual(response.status_code,200,response.text)
        self.assertIsNone(security.trans_auth('x'*1024,'test'))

    def test_overview_reports_current_utc_month_only(self):
        month = 'vision:'+datetime.now(timezone.utc).strftime('%Y-%m')
        db.reserve('vision:2000-01',1000,35*86400)
        db.reserve(month,1000,35*86400)
        self.assertEqual(operations.overview()['usage'],[{'name':month,'count':1}])
