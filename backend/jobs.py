"""Durable queue. Only the standalone worker executes jobs, never API threads."""
import html
import logging
import subprocess
import sys
import time
import fcntl
import threading
from contextlib import contextmanager
from datetime import datetime, timedelta, timezone
from . import db, settings
from .security import credential, fail

class JobFailure(Exception):
    """Safe, locally authored error suitable for the admin summary."""


KINDS = {'all': '全量同步', 'favorites': '同步收藏', 'translations': '同步标签翻译', 'daily': '同步每日搜索'}


def enqueue(kind):
    if not isinstance(kind, str) or kind not in KINDS:
        fail(400, '不允许的任务')
    with db.connect() as con:
        con.execute('BEGIN IMMEDIATE')
        row = con.execute("SELECT id FROM jobs WHERE kind=? AND status IN ('queued','in_progress')", (kind,)).fetchone()
        if row:
            return row[0]
        if con.execute("SELECT COUNT(*) FROM jobs WHERE status='queued'").fetchone()[0] >= 10:
            fail(409, '任务队列已满')
        stamp = db.now()
        return con.execute("INSERT INTO jobs(kind,status,created_at,updated_at) VALUES (?,'queued',?,?)", (kind, stamp, stamp)).lastrowid


def runs():
    with db.connect() as con:
        return [{'id': r['id'], 'name': KINDS[r['kind']], 'status': r['status'], 'conclusion': r['conclusion'],
                 'sha': str(r['id']), 'createdAt': r['created_at'], 'updatedAt': r['updated_at'], 'summary': r['summary']}
                for r in con.execute('SELECT * FROM jobs ORDER BY id DESC LIMIT 30')]


def rerun(job_id):
    if type(job_id) is not int:
        fail(400, '任务 ID 不正确')
    with db.connect() as con:
        row = con.execute("SELECT kind FROM jobs WHERE id=? AND status='completed'", (job_id,)).fetchone()
    if not row:
        fail(400, '只能重跑已完成的任务')
    return enqueue(row[0])


def collect_favorites():
    from app.sync_script import ExHentaiUtils
    from .upstream import validate_url
    base = credential('EXHENTAI_BASE_URL') or 'https://exhentai.org/favorites.php'
    cookies = {k: credential(v) for k, v in (
        ('ipb_member_id', 'EXHENTAI_COOKIE_MEMBER_ID'), ('ipb_pass_hash', 'EXHENTAI_COOKIE_PASS_HASH'), ('igneous', 'EXHENTAI_COOKIE_IGNEOUS'))}
    if not all(cookies.values()):
        raise JobFailure('请配置完整的 ExHentai Cookie')
    validate_url(base, gallery=True)
    data = ExHentaiUtils(base, cookies, logging.getLogger('favorites')).get_favorites_metadata()
    for g in data:
        for field in ('title', 'title_jpn'):
            if isinstance(g.get(field), str):
                g[field] = html.unescape(g[field])
    return data


def collect_translations():
    from app.sync_translations import download_with_retry, validate_and_parse
    return validate_and_parse(download_with_retry())


def collect_daily(groups):
    from app.exhentai_search import ExHentaiGallerySearch, ExHentaiUrlBuilder
    from .validation import validate
    validate('daily', groups)
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
        row = con.execute("SELECT kind FROM jobs WHERE id=? AND status='in_progress'", (job_id,)).fetchone()
        if not row:
            raise ValueError('任务未被 worker 领取')
        kind = row[0]
        groups, daily_version = db.resource(con, 'daily')
    collected = {}
    stages = [kind] if kind != 'all' else ['favorites', 'translations', 'daily']
    for stage in stages:
        with db.connect() as con:
            con.execute('UPDATE jobs SET summary=?,updated_at=? WHERE id=?', (f'正在执行：{KINDS[stage]}', db.now(), job_id))
        collected[stage] = {'favorites': collect_favorites, 'translations': collect_translations,
                            'daily': lambda: collect_daily(groups)}[stage]()
    # Publish all selected stages together; never hold a write lock while scraping.
    with db.connect() as con:
        con.execute('BEGIN IMMEDIATE')
        if 'daily' in collected and db.resource(con, 'daily')[1] != daily_version:
            raise JobFailure('抓取期间每日规则发生变化，请重新运行')
        if 'favorites' in collected:
            try:
                db.replace_galleries(con, collected['favorites'], allow_shrink=allow_shrink)
            except ValueError as exc:
                raise JobFailure(str(exc)) from None
        for stage in ('translations', 'daily'):
            if stage in collected:
                db.put_snapshot(con, stage, collected[stage])
        db.put_snapshot(con, 'release', {'commit': f'job-{job_id}', 'builtAt': db.now()})
        con.execute("UPDATE jobs SET status='completed',conclusion='success',updated_at=?,summary=? WHERE id=?",
                    (db.now(), '同步完成，数据已在同一事务中发布', job_id))


def work(once=False):
    settings.DATA_DIR.mkdir(parents=True, exist_ok=True)
    with (settings.DATA_DIR / 'worker.lock').open('w') as lock:
        try:
            fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            raise RuntimeError('已有 worker 正在运行')
        # The OS releases the singleton lock on termination. Interrupted jobs are
        # visible as failures; queued jobs survive restarts and continue normally.
        with db.connect() as con:
            con.execute("UPDATE jobs SET status='completed',conclusion='failure',summary='worker 中断，请重跑',updated_at=? WHERE status='in_progress'", (db.now(),))
        with heartbeat():
            while True:
                with db.connect() as con:
                    con.execute('BEGIN IMMEDIATE')
                    row = con.execute("SELECT id FROM jobs WHERE status='queued' ORDER BY id LIMIT 1").fetchone()
                    if row:
                        con.execute("UPDATE jobs SET status='in_progress',updated_at=? WHERE id=?", (db.now(), row[0]))
                if row:
                    conclusion, message = 'failure', '同步失败，原数据已保留；请检查凭证、来源可达性与数据完整性'
                    try:
                        result = subprocess.run([sys.executable, '-m', 'backend.cli', '_execute', str(row[0])],
                                                cwd=settings.ROOT, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                                                timeout=6 * 3600)
                        if result.returncode == 0:
                            conclusion, message = 'success', '同步完成，数据已发布'
                    except subprocess.TimeoutExpired:
                        conclusion, message = 'timed_out', '任务超过 6 小时，已终止并保留原数据'
                    with db.connect() as con:
                        # execute commits data and success together; do not downgrade
                        # a committed job if the child exits abnormally afterward.
                        con.execute("UPDATE jobs SET status='completed',conclusion=?,summary=?,updated_at=? WHERE id=? AND status='in_progress'",
                                    (conclusion, message, db.now(), row[0]))
                if once:
                    return
                if not row:
                    time.sleep(2)


@contextmanager
def heartbeat():
    stop = threading.Event()
    def tick():
        while not stop.is_set():
            try:
                with db.connect() as con:
                    db.put_snapshot(con, 'worker-heartbeat', time.time())
            except Exception:
                pass  # Health reports stale heartbeat if storage is unavailable.
            stop.wait(10)
    thread = threading.Thread(target=tick, daemon=True)
    thread.start()
    try:
        yield
    finally:
        stop.set()
        thread.join(timeout=35)


def run_foreground(kind, allow_shrink=False):
    """Local operator only. The same lock excludes the normal worker."""
    settings.DATA_DIR.mkdir(parents=True, exist_ok=True)
    with (settings.DATA_DIR / 'worker.lock').open('w') as lock:
        try:
            fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            raise RuntimeError('请先停止常驻 worker')
        with db.connect() as con:
            if con.execute("SELECT 1 FROM jobs WHERE status='in_progress'").fetchone():
                raise RuntimeError('存在中断任务，请先重启 worker 完成恢复，再停止 worker 进行维护')
        job_id = enqueue(kind)
        with db.connect() as con:
            con.execute("UPDATE jobs SET status='in_progress' WHERE id=?", (job_id,))
        with heartbeat():
            try:
                execute(job_id, allow_shrink)
            except Exception:
                with db.connect() as con:
                    con.execute("UPDATE jobs SET status='completed',conclusion='failure',summary='本机维护同步失败，数据保留',updated_at=? WHERE id=? AND status='in_progress'", (db.now(), job_id))
                raise
        return job_id


def record_failure(job_id, message):
    with db.connect() as con:
        row = con.execute('SELECT summary FROM jobs WHERE id=?', (job_id,)).fetchone()
        stage = row[0] if row else ''
        con.execute("UPDATE jobs SET status='completed',conclusion='failure',summary=?,updated_at=? WHERE id=? AND status='in_progress'",
                    (f'{stage}。{message}', db.now(), job_id))
