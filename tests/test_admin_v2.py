import base64
import io
import json
import os
import sqlite3
import subprocess
import sys
import threading
import time
from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import patch
from cryptography.fernet import Fernet
from fastapi.testclient import TestClient
from PIL import Image
import test_backend as fixtures
from backend import db, settings, records, services, security, jobs, schedules
from backend.main import app

BOOK, GALLERY = fixtures.BOOK, fixtures.GALLERY


class AdminV2Tests(fixtures.BackendTests):
    def test_record_versions_are_independent_and_restore_creates_history(self):
        with db.connect() as con:
            db.replace_galleries(con, [dict(GALLERY,gid=1),dict(GALLERY,gid=2)])
        a = self.admin('record',kind='gallery',id='1').json()
        b = self.admin('record',kind='gallery',id='2').json()
        first = self.admin('record-save',kind='gallery',id='1',version=a['version'],data={'title':'A'})
        second = self.admin('record-save',kind='gallery',id='2',version=b['version'],data={'title':'B'})
        self.assertEqual(first.status_code,200,first.text)
        self.assertEqual(second.status_code,200,second.text)
        self.assertEqual(self.admin('record-save',kind='gallery',id='1',version=a['version'],data={'title':'lost'}).status_code,409)
        history = self.admin('record-history',kind='gallery',id='1').json()['items']
        self.assertEqual(history[0]['changes']['title']['after'],'A')
        restore = self.admin('record-restore',historyId=history[-1]['id'],version=first.json()['version'])
        self.assertEqual(restore.status_code,200,restore.text)
        self.assertEqual(self.client.get('/api/galleries/1').json()['gallery']['title'],'source')
        self.assertEqual(self.client.get('/api/galleries/2').json()['gallery']['title'],'B')
        self.assertEqual(self.admin('record-restore',historyId=history[-1]['id'],version=first.json()['version']).status_code,409)

    def test_books_have_stable_ids_no_duplicate_storage_and_delete_restore(self):
        original=self.admin('records',kind='book').json()['items'][0]
        created=self.admin('record-save',kind='book',version='0',data=dict(BOOK)).json()
        self.assertNotEqual(created['id'],original['id'])
        changed=self.admin('record-save',kind='book',id=original['id'],version=original['version'],data=dict(BOOK,**{'书名':'updated'}))
        self.assertEqual(changed.status_code,200,changed.text)
        with db.connect() as con:
            self.assertIsNone(con.execute("SELECT 1 FROM resources WHERE name='printed'").fetchone())
            self.assertEqual(con.execute('SELECT COUNT(*) FROM books').fetchone()[0],2)
        self.assertEqual(self.client.get('/api/books').json()['items'][0]['book']['书名'],'updated')
        deleted=self.admin('record-delete',kind='book',id=original['id'],version=changed.json()['version'])
        self.assertEqual(deleted.status_code,200)
        restored=self.admin('record-restore',historyId=deleted.json()['historyId'],version='0')
        self.assertEqual(restored.status_code,200,restored.text)
        self.assertEqual(restored.json()['id'],original['id'])
        self.assertEqual(self.admin('record',kind='book',id=original['id']).json()['data']['书名'],'updated')
        self.assertEqual(self.admin('record-save',kind='book',version='0',data=dict(BOOK,sid='99999')).status_code,400)

    def test_daily_save_and_scoped_sync_preserve_other_groups(self):
        rules=self.admin('records',kind='daily').json()['items']
        selected=rules[0]
        self.assertEqual(self.admin('record-save',kind='daily',version='0',data=rules[0]['data']).status_code,400)
        job=self.admin('dispatch',workflow='daily',ruleId=selected['id']).json()['id']
        with db.connect() as con:con.execute("UPDATE jobs SET status='in_progress' WHERE id=?",(job,))
        payload=[{'name':selected['data']['name'],'galleries':[GALLERY]}]
        with patch.object(jobs,'collect_daily',return_value=payload): jobs.execute(job)
        groups=self.client.get('/api/daily').json()['groups']
        self.assertEqual(len(groups),2)
        self.assertTrue(any(g.get('groupId')==selected['id'] for g in groups))
        self.assertEqual(self.admin('record-reorder',kind='daily',id=selected['id'],version=selected['version'],direction=1).status_code,200)
        self.assertEqual(self.admin('record-save',kind='daily',id=selected['id'],version=selected['version'],data=selected['data']).status_code,409)

    def test_cookie_login_csrf_secure_flags_and_session_revocation(self):
        with TestClient(app,base_url='https://testserver') as client:
            login=client.post('/api/admin',json={'action':'verify','mode':'cookie','password':os.environ['ADMIN_PASSWORD'],'remember':True})
            self.assertEqual(login.status_code,200,login.text)
            cookie=login.headers['set-cookie'].lower()
            self.assertIn('httponly',cookie);self.assertIn('secure',cookie);self.assertIn('samesite=strict',cookie)
            self.assertNotIn('token',login.json()['session'])
            csrf=login.json()['session']['csrf']
            self.assertEqual(client.post('/api/admin',json={'action':'overview'}).status_code,403)
            response=client.post('/api/admin',json={'action':'overview'},headers={'X-CSRF-Token':csrf})
            self.assertEqual(response.status_code,200,response.text)
            current=client.get('/api/admin/session').json()
            self.assertEqual(current['session']['csrf'],csrf)
            self.assertNotIn('token',current['session'])
            self.assertEqual(client.post('/api/admin',json={'action':'overview'},headers={'X-CSRF-Token':csrf,'Origin':'https://evil.example'}).status_code,403)
            client.post('/api/admin',json={'action':'logout'},headers={'X-CSRF-Token':csrf})
            self.assertEqual(client.get('/api/admin/session').status_code,401)

    def test_password_is_hashed_and_change_revokes_all_sessions(self):
        password=os.environ['ADMIN_PASSWORD']
        with db.connect() as con:
            encoded=con.execute('SELECT password_hash FROM accounts').fetchone()[0]
            self.assertTrue(encoded.startswith('scrypt$'))
            self.assertNotIn(password,encoded)
        self.assertEqual(self.admin('change-password',currentPassword='wrong',newPassword='a-new-long-password').status_code,401)
        self.assertEqual(self.admin('change-password',currentPassword=password,newPassword='a-new-long-password').status_code,200)
        self.assertEqual(self.admin('overview').status_code,401)
        self.assertFalse(security.verify_password(password))
        self.assertTrue(security.verify_password('a-new-long-password'))

    def test_service_groups_separate_public_settings_and_encrypted_secrets(self):
        status=self.admin('services').json()['groups']
        favorites=next(s for s in status if s['id']=='favorites')
        result=self.admin('service-save',service='favorites',version=favorites['version'],values={'MAX_RETRIES':3,'EXHENTAI_COOKIE_MEMBER_ID':'private-cookie'})
        self.assertEqual(result.status_code,200,result.text)
        self.assertEqual(security.credential('MAX_RETRIES'),'3')
        self.assertEqual(security.credential('EXHENTAI_COOKIE_MEMBER_ID'),'private-cookie')
        response=self.admin('services')
        self.assertNotIn('private-cookie',response.text)
        with db.connect() as con:
            self.assertEqual(json.loads(con.execute("SELECT value_json FROM service_settings WHERE name='MAX_RETRIES'").fetchone()[0]),3)
            self.assertNotIn('private-cookie',con.execute("SELECT ciphertext FROM credentials WHERE name='EXHENTAI_COOKIE_MEMBER_ID'").fetchone()[0])
            self.assertNotIn('private-cookie',str([tuple(r) for r in con.execute('SELECT * FROM history')]))
        self.assertEqual(self.admin('service-save',service='favorites',version=favorites['version'],values={'MAX_RETRIES':2}).status_code,409)
        self.assertEqual(self.admin('service-save',service='favorites',version=result.json().get('version'),values={'ADMIN_PASSWORD':'forbidden'}).status_code,400)

    def test_service_group_edits_do_not_conflict_across_groups_and_clear_is_explicit(self):
        groups={s['id']:s for s in self.admin('services').json()['groups']}
        self.assertEqual(self.admin('service-save',service='ocr',version=groups['ocr']['version'],values={'defaultOcr':'paddle'}).status_code,200)
        self.assertEqual(self.admin('service-save',service='translate',version=groups['translate']['version'],values={'model':'custom-model'}).status_code,200)
        self.assertEqual(self.client.get('/data/translate-config.json').json()['defaultOcr'],'paddle')
        self.assertEqual(self.admin('load',resource='translate').json()['data']['model'],'custom-model')
        with patch.dict(os.environ,{'OCR_SPACE_KEY':'env-secret'}):
            group=next(g for g in self.admin('services').json()['groups'] if g['id']=='ocr')
            cleared=self.admin('service-save',service='ocr',version=group['version'],values={},operations={'OCR_SPACE_KEY':'clear'})
            self.assertEqual(cleared.status_code,200,cleared.text)
            self.assertEqual(security.credential('OCR_SPACE_KEY'),'')
            group=next(g for g in self.admin('services').json()['groups'] if g['id']=='ocr')
            self.assertEqual(self.admin('service-save',service='ocr',version=group['version'],values={},operations={'OCR_SPACE_KEY':'inherit'}).status_code,200)
            self.assertEqual(security.credential('OCR_SPACE_KEY'),'env-secret')

    def test_connection_test_records_revision_and_never_leaks_provider_error(self):
        with patch('backend.translation.translate',return_value={'translations':[{'t':'测试'}]}):
            result=self.admin('service-test',service='translate')
        self.assertTrue(result.json()['ok'])
        group=next(g for g in self.admin('services').json()['groups'] if g['id']=='translate')
        self.assertEqual(group['check']['version'],group['version'])
        self.admin('service-save',service='translate',version=group['version'],values={'model':'changed'})
        group=next(g for g in self.admin('services').json()['groups'] if g['id']=='translate')
        self.assertNotEqual(group['check']['version'],group['version'])
        with patch('backend.translation.translate',side_effect=RuntimeError('SECRET-UPSTREAM-ERROR')):
            result=self.admin('service-test',service='translate')
        self.assertFalse(result.json()['ok']);self.assertNotIn('SECRET-UPSTREAM',result.text)

    def test_schedule_timezone_due_occurrence_and_deduplication(self):
        after=datetime(2026,11,2,10,0,tzinfo=timezone.utc)
        self.assertEqual(schedules.next_run(4,0,'Asia/Shanghai',after),'2026-11-02T20:00:00+00:00')
        schedule=next(s for s in self.admin('schedules').json()['items'] if s['kind']=='favorites')
        self.assertEqual(self.admin('schedule-save',kind='favorites',version=schedule['version'],enabled=True,hour=4,minute=0,timezone='Asia/Shanghai').status_code,200)
        with db.connect() as con:con.execute("UPDATE schedules SET next_run_at='2000-01-01T00:00:00+00:00' WHERE kind='favorites'")
        schedules.tick();schedules.tick()
        self.assertEqual(len(jobs.runs()),1)
        self.assertEqual(jobs.runs()[0]['status'],'queued')
        self.assertEqual(self.admin('schedule-save',kind='favorites',version=schedule['version'],enabled=False,hour=4,minute=0,timezone='Asia/Shanghai').status_code,409)

    def test_job_freezes_credentials_and_retry_reuses_successful_checkpoints(self):
        security.replace_credential('EXHENTAI_COOKIE_MEMBER_ID','original')
        job=self.claim('all')
        security.replace_credential('EXHENTAI_COOKIE_MEMBER_ID','new')
        def collect():
            self.assertEqual(security.credential('EXHENTAI_COOKIE_MEMBER_ID'),'original')
            return [dict(GALLERY,title='checkpoint')]
        with patch.object(jobs,'collect_favorites',side_effect=collect),patch.object(jobs,'collect_translations',side_effect=RuntimeError('failed')):
            with self.assertRaises(RuntimeError):jobs.execute(job)
        jobs.record_failure(job,'测试失败')
        self.assertEqual(self.client.get('/api/galleries/123').json()['gallery']['title'],'source')
        retried=jobs.rerun(job,original=True)
        with db.connect() as con:con.execute("UPDATE jobs SET status='in_progress' WHERE id=?",(retried,))
        with patch.object(jobs,'collect_favorites',side_effect=AssertionError('must reuse checkpoint')),patch.object(jobs,'collect_translations',return_value={'data':[]}),patch.object(jobs,'collect_daily',return_value=[]):
            jobs.execute(retried)
        self.assertEqual(self.client.get('/api/galleries/123').json()['gallery']['title'],'checkpoint')
        runs=self.admin('runs')
        self.assertNotIn('original',runs.text);self.assertNotIn('new"',runs.text)
        self.assertEqual(jobs.runs()[0]['parentId'],job)

    def test_old_favorites_checkpoint_cannot_overwrite_a_new_sync(self):
        job=self.claim('all')
        with patch.object(jobs,'collect_favorites',return_value=[dict(GALLERY,title='old checkpoint')]),patch.object(jobs,'collect_translations',side_effect=RuntimeError('failed')):
            with self.assertRaises(RuntimeError):jobs.execute(job)
        jobs.record_failure(job,'测试失败')
        with db.connect() as con:db.replace_galleries(con,[dict(GALLERY,title='new source')])
        retried=jobs.rerun(job,original=True)
        with db.connect() as con:con.execute("UPDATE jobs SET status='in_progress' WHERE id=?",(retried,))
        with patch.object(jobs,'collect_translations',return_value={'data':[]}),patch.object(jobs,'collect_daily',return_value=[]):
            with self.assertRaisesRegex(jobs.JobFailure,'收藏来源已被其他任务更新'):jobs.execute(retried)
        self.assertEqual(self.client.get('/api/galleries/123').json()['gallery']['title'],'new source')

    def test_public_lists_apply_live_overrides_without_full_translation_dictionary(self):
        self.assertEqual(len(self.client.get('/api/books').json()['items']),1)
        self.assertEqual(len(self.client.get('/api/daily').json()['groups']),1)
        self.assertEqual(self.client.get('/api/tags?page=1').status_code,200)
        version=self.admin('record',kind='gallery',id='123').json()['version']
        self.assertEqual(self.admin('record-save',kind='gallery',id='123',version=version,data={'hidden':True}).status_code,200)
        self.assertIsNone(self.client.get('/api/books').json()['items'][0]['gallery'])
        self.assertFalse(any(str(g['gid'])=='123' for group in self.client.get('/api/daily').json()['groups'] for g in group['galleries']))
        self.assertEqual(self.client.get('/api/galleries').json()['total'],0)

    def test_worker_cancellation_terminates_child_without_publication(self):
        job=jobs.enqueue('favorites')
        actual_popen=subprocess.Popen
        def cancel_when_running():
            for _ in range(300):
                with db.connect() as con:status=con.execute('SELECT status FROM jobs WHERE id=?',(job,)).fetchone()[0]
                if status=='in_progress':jobs.cancel(job);return
                time.sleep(.01)
        thread=threading.Thread(target=cancel_when_running);thread.start()
        with patch.object(jobs.subprocess,'Popen',side_effect=lambda *args,**kwargs:actual_popen([sys.executable,'-c','import time;time.sleep(20)'],**kwargs)):
            jobs.work(once=True)
        thread.join(timeout=5)
        self.assertEqual(jobs.runs()[0]['conclusion'],'cancelled')
        self.assertEqual(self.client.get('/api/galleries/123').json()['gallery']['title'],'source')
        other=jobs.enqueue('daily');jobs.cancel(other)
        self.assertEqual(jobs.runs()[0]['conclusion'],'cancelled')

    def test_cover_upload_reencoding_and_authenticated_backup_download(self):
        image=Image.new('RGB',(1800,100),'red');output=io.BytesIO();image.save(output,format='PNG')
        uploaded=self.admin('media-upload',imageBase64=base64.b64encode(output.getvalue()).decode())
        self.assertEqual(uploaded.status_code,200,uploaded.text)
        self.assertEqual(uploaded.json()['width'],1600)
        response=self.client.get(uploaded.json()['url'])
        self.assertEqual(response.headers['content-type'],'image/webp')
        self.assertEqual(Image.open(io.BytesIO(response.content)).format,'WEBP')
        self.assertEqual(self.admin('media-upload',imageBase64=base64.b64encode(b'<script>bad</script>').decode()).status_code,400)
        name=self.admin('backup-create').json()['name']
        self.assertEqual(self.client.get('/api/admin/backups/'+name).status_code,401)
        login=self.client.post('/api/admin',json={'action':'verify','mode':'cookie','password':os.environ['ADMIN_PASSWORD']})
        self.assertEqual(login.status_code,200)
        downloaded=self.client.get('/api/admin/backups/'+name)
        self.assertTrue(downloaded.content.startswith(b'SQLite format 3'))
        backups=self.admin('backups').json()['items']
        self.assertTrue(backups[0]['media'])
        self.assertEqual(self.client.get('/api/admin/backups/not-a-backup.sqlite3').status_code,404)

    def test_migration_is_idempotent_and_preserves_v1_data(self):
        path=Path(self.tmp.name)/'legacy.sqlite3'
        con=sqlite3.connect(path)
        con.executescript('''CREATE TABLE galleries(gid TEXT PRIMARY KEY,position INTEGER NOT NULL,data TEXT NOT NULL);
          CREATE TABLE books(position INTEGER PRIMARY KEY,data TEXT NOT NULL);
          CREATE TABLE resources(name TEXT PRIMARY KEY,data TEXT NOT NULL,version TEXT NOT NULL);
          CREATE TABLE sessions(digest TEXT PRIMARY KEY,expires REAL NOT NULL,fingerprint TEXT NOT NULL);
          CREATE TABLE jobs(id INTEGER PRIMARY KEY,kind TEXT NOT NULL,status TEXT NOT NULL,conclusion TEXT,created_at TEXT NOT NULL,updated_at TEXT NOT NULL,summary TEXT NOT NULL DEFAULT '');
          PRAGMA user_version=1;''')
        con.execute('INSERT INTO galleries VALUES (?,?,?)',('123',0,json.dumps(GALLERY)))
        con.executemany('INSERT INTO books VALUES (?,?)',[(i,json.dumps(BOOK)) for i in range(2)])
        for name,data in [('overrides',{'123':{'title':'manual'}}),('printed',[BOOK,BOOK]),('daily',self.daily),('translate',{'model':None,'defaultOcr':'google','jsonMode':None})]:
            con.execute('INSERT INTO resources VALUES (?,?,?)',(name,json.dumps(data),'original-version'))
        con.commit();con.close()
        with patch.object(settings,'DB_PATH',path):
            db.initialize()
            with db.connect() as con:
                ids=[r[0] for r in con.execute('SELECT id FROM books ORDER BY position')]
                self.assertEqual(len(set(ids)),2)
                self.assertEqual(db.resource(con,'printed')[0],[BOOK,BOOK])
                self.assertEqual(db.resource(con,'daily')[0],self.daily)
                self.assertEqual(db.resource(con,'overrides')[0],{'123':{'title':'manual'}})
                self.assertEqual(con.execute('PRAGMA user_version').fetchone()[0],2)
                self.assertIsNone(con.execute("SELECT 1 FROM resources WHERE name='printed'").fetchone())
                self.assertEqual(con.execute('SELECT title FROM galleries').fetchone()[0],'source')
            db.initialize()
            with db.connect() as con:self.assertEqual([r[0] for r in con.execute('SELECT id FROM books ORDER BY position')],ids)


for name in list(fixtures.BackendTests.__dict__):
    if name.startswith('test_'):setattr(AdminV2Tests,name,None)
