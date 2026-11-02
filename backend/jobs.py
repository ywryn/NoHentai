"""Durable worker, immutable job configuration, checkpoints and cooperative cancellation."""
import html
import json
import logging
import subprocess
import sys
import time
import fcntl
import threading
import re
import uuid
from contextlib import contextmanager
from datetime import datetime, timedelta, timezone
from cryptography.fernet import Fernet
from . import db, settings, security
from .security import credential, fail

class JobFailure(Exception):
    """A locally authored error safe to show in admin."""

class JobCancelled(JobFailure):
    pass

KINDS = {'all': '全量同步', 'favorites': '同步收藏', 'translations': '同步标签翻译', 'daily': '同步每日搜索'}


def freeze(con, rule_id=None, kind='all'):
    groups, version = db.resource(con, 'daily')
    rows = con.execute('SELECT id,data,version FROM daily_rules ORDER BY position').fetchall()
    if rule_id:
        rows = [r for r in rows if r['id'] == rule_id]
        if not rows:
            fail(404, '每日分组不存在')
        groups = [json.loads(r['data']) for r in rows]
    config = {'sourceRevision': db.snapshot(con, 'favorites-revision'), 'daily': groups, 'dailyVersion': version, 'ruleId': rule_id,
              'ruleVersions': {r['id']: r['version'] for r in rows},
              'ruleIds': {json.loads(r['data'])['name']: r['id'] for r in rows}}
    names = ('EXHENTAI_BASE_URL','EXHENTAI_COOKIE_MEMBER_ID','EXHENTAI_COOKIE_PASS_HASH','EXHENTAI_COOKIE_IGNEOUS','MAX_RETRIES','RETRY_DELAY_SECONDS') if kind!='translations' else ()
    values = {name: credential(name, con) for name in names}
    return db.dumps(config), Fernet(settings.encryption_key()).encrypt(db.dumps(values).encode()).decode()


def enqueue_in(con, kind, rule_id=None, parent=None, original=False):
    if not isinstance(kind, str) or kind not in KINDS:
        fail(400, '不允许的任务')
    if rule_id and kind != 'daily':
        fail(400, '仅每日任务可以选择分组')
    existing = con.execute("SELECT id FROM jobs WHERE kind=? AND status IN ('queued','in_progress') AND json_extract(config_json,'$.ruleId') IS ?", (kind, rule_id)).fetchone()
    if existing:
        return existing[0]
    if con.execute("SELECT COUNT(*) FROM jobs WHERE status='queued'").fetchone()[0] >= 20:
        fail(409, '任务队列已满')
    if original:
        config, ciphertext = parent['config_json'], parent['config_ciphertext']
        if not config or not ciphertext:
            fail(400, '旧任务未保存配置，无法重试原配置')
    else:
        config, ciphertext = freeze(con, rule_id, kind)
    stamp = db.now()
    job_id = con.execute("INSERT INTO jobs(kind,status,created_at,updated_at,config_json,config_ciphertext,parent_id) VALUES (?,'queued',?,?,?,?,?)",
                         (kind, stamp, stamp, config, ciphertext, parent['id'] if parent else None)).lastrowid
    if original:
        for step in con.execute("SELECT * FROM job_steps WHERE job_id=? AND status='success' AND result_json IS NOT NULL", (parent['id'],)).fetchall():
            con.execute("INSERT INTO job_steps(job_id,name,status,finished_at,progress_json,result_json,summary) VALUES (?,?,'success',?,?,?,?)",
                        (job_id, step['name'], step['finished_at'], step['progress_json'], step['result_json'], '复用原任务已成功步骤'))
    return job_id


def enqueue(kind, rule_id=None):
    with db.connect() as con:
        con.execute('BEGIN IMMEDIATE')
        return enqueue_in(con, kind, rule_id)


def runs():
    with db.connect() as con:
        items = []
        for r in con.execute('SELECT * FROM jobs ORDER BY id DESC LIMIT 50').fetchall():
            steps = [{k: step[k] for k in ('name','status','started_at','finished_at','summary')} | {'progress': json.loads(step['progress_json'])}
                     for step in con.execute('SELECT * FROM job_steps WHERE job_id=? ORDER BY rowid', (r['id'],))]
            config = json.loads(r['config_json']) if r['config_json'] else {}
            items.append({'id': r['id'], 'kind': r['kind'], 'name': KINDS[r['kind']], 'status': r['status'], 'conclusion': r['conclusion'],
                          'createdAt': r['created_at'], 'updatedAt': r['updated_at'], 'summary': r['summary'], 'steps': steps,
                          'cancelRequested': bool(r['cancel_requested']), 'parentId': r['parent_id'], 'ruleId': config.get('ruleId'),
                          'config': config})
        return items


def rerun(job_id, original=False):
    if type(job_id) is not int:
        fail(400, '任务 ID 不正确')
    with db.connect() as con:
        con.execute('BEGIN IMMEDIATE')
        parent = con.execute("SELECT * FROM jobs WHERE id=? AND status='completed'", (job_id,)).fetchone()
        if not parent:
            fail(400, '只能重跑已完成的任务')
        config = json.loads(parent['config_json']) if parent['config_json'] else {}
        return enqueue_in(con, parent['kind'], config.get('ruleId'), parent, original)


def cancel(job_id):
    with db.connect() as con:
        con.execute('BEGIN IMMEDIATE')
        row = con.execute('SELECT status FROM jobs WHERE id=?', (job_id,)).fetchone()
        if not row:
            fail(404, '任务不存在')
        if row['status'] == 'queued':
            con.execute("UPDATE jobs SET status='completed',conclusion='cancelled',cancel_requested=1,summary='已取消排队',updated_at=? WHERE id=?", (db.now(), job_id))
        elif row['status'] == 'in_progress':
            con.execute('UPDATE jobs SET cancel_requested=1 WHERE id=?', (job_id,))
    return {'ok': True}


def cancelled(job_id):
    with db.connect() as con:
        row = con.execute('SELECT cancel_requested FROM jobs WHERE id=?', (job_id,)).fetchone()
    return bool(row and row[0])


class Progress(logging.Handler):
    def __init__(self, job_id, step):
        super().__init__()
        self.job_id, self.step, self.updated = job_id, step, 0
    def emit(self, record):
        message = record.getMessage()
        page = re.search(r'第\s*(\d+)\s*页.*累计\s*(\d+)\s*条', message)
        batch = re.search(r'第\s*(\d+)\s*批', message)
        if not (page or batch) or time.monotonic()-self.updated < .2:
            return
        self.updated = time.monotonic()
        progress = {'pages': int(page[1]), 'items': int(page[2])} if page else {'batch': int(batch[1])}
        with db.connect() as con:
            con.execute('UPDATE job_steps SET progress_json=? WHERE job_id=? AND name=?', (db.dumps(progress), self.job_id, self.step))


def collect_favorites():
    from app.sync_script import ExHentaiUtils
    from .upstream import validate_url
    base = credential('EXHENTAI_BASE_URL') or 'https://exhentai.org/favorites.php'
    cookies = {k: credential(v) for k, v in (
        ('ipb_member_id', 'EXHENTAI_COOKIE_MEMBER_ID'), ('ipb_pass_hash', 'EXHENTAI_COOKIE_PASS_HASH'), ('igneous', 'EXHENTAI_COOKIE_IGNEOUS'))}
    if not all(cookies.values()):
        raise JobFailure('请配置完整的 ExHentai Cookie')
    validate_url(base, gallery=True)
    data = ExHentaiUtils(base, cookies, logging.getLogger('favorites')).get_favorites_metadata(max_retries=int(float(credential('MAX_RETRIES') or 5)), retry_delay=float(credential('RETRY_DELAY_SECONDS') or 2))
    for g in data:
        for field in ('title', 'title_jpn'):
            if isinstance(g.get(field), str):
                g[field] = html.unescape(g[field])
    return data


def collect_translations():
    from app.sync_translations import download_with_retry, validate_and_parse
    return validate_and_parse(download_with_retry())


def collect_daily(groups):
    from app.exhentai_search import ExHentaiGallerySearch, ExHentaiUrlBuilder, Config
    from .validation import validate
    validate('daily', groups)
    Config.MAX_RETRIES = int(float(credential('MAX_RETRIES') or 5))
    Config.RETRY_DELAY_SECONDS = float(credential('RETRY_DELAY_SECONDS') or 2)
    search = ExHentaiGallerySearch()
    search.session.session.cookies.clear()
    for key, name in (('ipb_member_id', 'EXHENTAI_COOKIE_MEMBER_ID'), ('ipb_pass_hash', 'EXHENTAI_COOKIE_PASS_HASH'), ('igneous', 'EXHENTAI_COOKIE_IGNEOUS')):
        value = credential(name)
        if not value:
            raise JobFailure('每日搜索需要完整的 ExHentai Cookie')
        search.session.session.cookies.set(key, value, domain='exhentai.org', path='/')
    output = []
    for group in groups:
        builder = ExHentaiUrlBuilder().set_keyword(group['keyword']).set_only_category(group['categories'])
        builder.min_pages, builder.max_pages, builder.min_rating = group['minPages'], group['maxPages'], group['minRating']
        builder.advsearch = any(group[k] is not None for k in ('minPages', 'maxPages', 'minRating'))
        cutoff = (datetime.now(timezone.utc) - timedelta(days=group['cutoffDays'])).strftime('%Y-%m-%d')
        result = search.search_with_builder(builder, fetch_details=True, cutoff_date=cutoff)
        if not result['success']:
            raise JobFailure('每日搜索分组抓取失败，保留上一份完整快照')
        output.append({'name': group['name'], 'filters': group['filters'], 'generatedAt': db.now(),
                       'cutoffDate': cutoff, 'galleries': result['galleries']})
    return output


def execute(job_id, allow_shrink=False):
    from .cli import backup
    backup()
    with db.connect() as con:
        row = con.execute("SELECT * FROM jobs WHERE id=? AND status='in_progress'", (job_id,)).fetchone()
        if not row:
            raise JobFailure('任务未被 worker 领取')
        config = json.loads(row['config_json']) if row['config_json'] else json.loads(freeze(con)[0])
        secrets_snapshot = json.loads(Fernet(settings.encryption_key()).decrypt(row['config_ciphertext'].encode())) if row['config_ciphertext'] else None
        kind = row['kind']
    collected = {}
    reused_favorites = False
    stages = [kind] if kind != 'all' else ['favorites', 'translations', 'daily']
    with security.use_credentials(secrets_snapshot):
        for stage in stages:
            if cancelled(job_id):
                raise JobCancelled('任务已取消，数据保留')
            with db.connect() as con:
                checkpoint = con.execute("SELECT result_json FROM job_steps WHERE job_id=? AND name=? AND status='success'", (job_id, stage)).fetchone()
                con.execute('UPDATE jobs SET summary=?,updated_at=? WHERE id=?', (f'正在执行：{KINDS[stage]}', db.now(), job_id))
                if not checkpoint:
                    con.execute("INSERT OR REPLACE INTO job_steps(job_id,name,status,started_at) VALUES (?,?,'in_progress',?)", (job_id, stage, db.now()))
            if checkpoint and checkpoint[0]:
                collected[stage] = json.loads(checkpoint[0])
                reused_favorites = reused_favorites or stage=='favorites'
                continue
            handler = Progress(job_id, stage)
            logging.getLogger().setLevel(logging.INFO)
            logging.getLogger().addHandler(handler)
            try:
                collected[stage] = {'favorites': collect_favorites, 'translations': collect_translations,
                                    'daily': lambda: collect_daily(config['daily'])}[stage]()
                if stage == 'daily':
                    for group in collected[stage]:
                        if group['name'] in config['ruleIds']:
                            group['groupId'] = config['ruleIds'][group['name']]
                count = len(collected[stage]) if stage == 'favorites' else sum(len(g.get('galleries', [])) for g in collected[stage]) if stage == 'daily' else sum(len(g.get('data', {})) for g in collected[stage].get('data', []))
                with db.connect() as con:
                    con.execute("UPDATE job_steps SET status='success',finished_at=?,result_json=?,summary=? WHERE job_id=? AND name=?",
                                (db.now(), db.dumps(collected[stage]), f'已获取 {count} 条记录', job_id, stage))
            except Exception:
                with db.connect() as con:
                    con.execute("UPDATE job_steps SET status='failure',finished_at=?,summary='步骤失败，保留先前数据' WHERE job_id=? AND name=?", (db.now(), job_id, stage))
                raise
            finally:
                logging.getLogger().removeHandler(handler)
    with db.connect() as con:
        con.execute('BEGIN IMMEDIATE')
        if con.execute('SELECT cancel_requested FROM jobs WHERE id=?', (job_id,)).fetchone()[0]:
            raise JobCancelled('任务已取消，数据保留')
        if 'daily' in collected:
            if config.get('ruleId'):
                current = con.execute('SELECT version FROM daily_rules WHERE id=?', (config['ruleId'],)).fetchone()
                if not current or current[0] != config['ruleVersions'].get(config['ruleId']):
                    raise JobFailure('抓取期间分组规则发生变化，请按当前配置重新运行')
            elif db.resource(con, 'daily')[1] != config['dailyVersion']:
                raise JobFailure('抓取期间每日规则发生变化，请重新运行')
        if reused_favorites and db.snapshot(con, 'favorites-revision') != config.get('sourceRevision'):
            raise JobFailure('收藏来源已被其他任务更新，请使用当前配置重新执行')
        if 'favorites' in collected:
            try:
                db.replace_galleries(con, collected['favorites'], allow_shrink=allow_shrink)
            except ValueError as exc:
                raise JobFailure(str(exc)) from None
        for stage in ('translations', 'daily'):
            if stage in collected:
                data = collected[stage]
                if stage == 'daily' and config.get('ruleId'):
                    names = {g['name'] for g in data}
                    previous = db.snapshot(con, 'daily', [])
                    data = [g for g in previous if g.get('groupId') != config['ruleId'] and g.get('name') not in names] + data
                db.put_snapshot(con, stage, data)
        db.put_snapshot(con, 'release', {'commit': f'job-{job_id}', 'builtAt': db.now()})
        con.execute("UPDATE jobs SET status='completed',conclusion='success',updated_at=?,summary=? WHERE id=?", (db.now(), '同步完成，数据已发布', job_id))
        # Bound checkpoint storage; preserve failed jobs so they can be retried.
        con.execute("UPDATE job_steps SET result_json=NULL WHERE job_id IN (SELECT id FROM jobs WHERE conclusion='success' ORDER BY id DESC LIMIT -1 OFFSET 10)")


def work(once=False):
    settings.DATA_DIR.mkdir(parents=True, exist_ok=True)
    with (settings.DATA_DIR / 'worker.lock').open('w') as lock:
        try:
            fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            raise RuntimeError('已有 worker 正在运行')
        with db.connect() as con:
            con.execute("UPDATE jobs SET status='completed',conclusion='failure',summary='worker 中断，可重试失败步骤',updated_at=? WHERE status='in_progress'", (db.now(),))
            con.execute("UPDATE job_steps SET status='failure',summary='worker 中断' WHERE status='in_progress'")
        with heartbeat():
            while True:
                with db.connect() as con:
                    con.execute('BEGIN IMMEDIATE')
                    row = con.execute("SELECT id,kind,config_json FROM jobs WHERE status='queued' ORDER BY id LIMIT 1").fetchone()
                    if row:
                        if not row['config_json']:
                            config,ciphertext=freeze(con,kind=row['kind'])
                            con.execute('UPDATE jobs SET config_json=?,config_ciphertext=? WHERE id=?',(config,ciphertext,row['id']))
                        con.execute("UPDATE jobs SET status='in_progress',updated_at=? WHERE id=?", (db.now(), row[0]))
                if row:
                    conclusion, message = 'failure', '同步进程异常，原数据已保留'
                    process = subprocess.Popen([sys.executable, '-m', 'backend.cli', '_execute', str(row[0])], cwd=settings.ROOT,
                                               stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
                    started = time.monotonic()
                    while process.poll() is None:
                        if cancelled(row[0]):
                            process.kill(); process.wait()
                            conclusion, message = 'cancelled', '任务已取消，原数据保留'
                            break
                        if time.monotonic()-started > 6*3600:
                            process.kill(); process.wait()
                            conclusion, message = 'timed_out', '任务超过六小时，已终止'
                            break
                        try:
                            process.wait(timeout=1)
                        except subprocess.TimeoutExpired:
                            pass
                    if process.returncode == 0:
                        conclusion, message = 'success', '同步完成'
                    with db.connect() as con:
                        con.execute("UPDATE jobs SET status='completed',conclusion=?,summary=?,updated_at=? WHERE id=? AND status='in_progress'",
                                    (conclusion, message, db.now(), row[0]))
                        con.execute("UPDATE job_steps SET status=?,finished_at=? WHERE job_id=? AND status='in_progress'", (conclusion, db.now(), row[0]))
                if once:
                    return
                if not row:
                    time.sleep(2)


@contextmanager
def heartbeat():
    stop = threading.Event()
    def tick():
        from . import schedules
        while not stop.is_set():
            try:
                with db.connect() as con:
                    db.put_snapshot(con, 'worker-heartbeat', time.time())
                schedules.tick()
            except Exception:
                pass
            stop.wait(10)
    thread = threading.Thread(target=tick, daemon=True)
    thread.start()
    try:
        yield
    finally:
        stop.set(); thread.join(timeout=35)


def run_foreground(kind, allow_shrink=False):
    settings.DATA_DIR.mkdir(parents=True, exist_ok=True)
    with (settings.DATA_DIR / 'worker.lock').open('w') as lock:
        try:
            fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            raise RuntimeError('请先停止常驻 worker')
        with db.connect() as con:
            if con.execute("SELECT 1 FROM jobs WHERE status='in_progress'").fetchone():
                raise RuntimeError('存在中断任务，请先重启 worker 完成恢复')
        job_id = enqueue(kind)
        with db.connect() as con:
            con.execute("UPDATE jobs SET status='in_progress' WHERE id=?", (job_id,))
        with heartbeat():
            try:
                execute(job_id, allow_shrink)
            except Exception:
                record_failure(job_id, '本机维护同步失败，数据保留')
                raise
        return job_id


def record_failure(job_id, message, conclusion='failure'):
    with db.connect() as con:
        row = con.execute('SELECT summary FROM jobs WHERE id=?', (job_id,)).fetchone()
        stage = row[0] if row else ''
        con.execute("UPDATE jobs SET status='completed',conclusion=?,summary=?,updated_at=? WHERE id=? AND status='in_progress'",
                    (conclusion, f'{stage}。{message}', db.now(), job_id))
