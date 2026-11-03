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
from app.daily_config import conditions
from .security import credential, fail

class JobFailure(Exception):
    """A locally authored error safe to show in admin."""

class JobCancelled(JobFailure):
    pass

KINDS = {'all': '全量同步', 'favorites': '同步收藏', 'translations': '同步标签翻译', 'daily': '同步每日搜索'}


def event(job_id, stage, message, level='info', data=None, con=None):
    # Only locally authored messages enter this journal. Never persist raw logs.
    if con is None:
        with db.connect() as connection:
            return event(job_id,stage,message,level,data,connection)
    con.execute('INSERT INTO job_events(job_id,stage,level,message,data_json,created_at) VALUES (?,?,?,?,?,?)',
                (job_id,stage,level,message,db.dumps(data or {}),db.now()))
    con.execute('DELETE FROM job_events WHERE job_id=? AND id NOT IN (SELECT id FROM job_events WHERE job_id=? ORDER BY id DESC LIMIT 2000)',(job_id,job_id))


def detail(job_id, after=None):
    if type(job_id) is not int or (after is not None and (type(after) is not int or after<0)):
        fail(400,'任务参数不正确')
    run=next((r for r in runs() if r['id']==job_id),None)
    if not run:
        fail(404,'任务不存在或已不在最近运行列表中')
    with db.connect() as con:
        rows=con.execute('SELECT * FROM (SELECT * FROM job_events WHERE job_id=? AND id>? ORDER BY id DESC LIMIT 2000) ORDER BY id',(job_id,after or 0)).fetchall()
        first=con.execute('SELECT MIN(id) FROM job_events WHERE job_id=?',(job_id,)).fetchone()[0]
    return {'run':run,'events':[{'id':r['id'],'stage':r['stage'],'level':r['level'],'message':r['message'],'data':json.loads(r['data_json']),'at':r['created_at']} for r in rows], 'retainedFrom':first}


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
    event(job_id,'queue','任务已排队，等待 worker 领取',con=con)
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
            event(job_id,'queue','已取消排队',con=con)
        elif row['status'] == 'in_progress':
            con.execute('UPDATE jobs SET cancel_requested=1 WHERE id=?', (job_id,))
            event(job_id,'queue','已请求取消，正在等待抓取进程终止','warning',con=con)
    return {'ok': True}


def cancelled(job_id):
    with db.connect() as con:
        row = con.execute('SELECT cancel_requested FROM jobs WHERE id=?', (job_id,)).fetchone()
    return bool(row and row[0])


class Progress(logging.Handler):
    def __init__(self, job_id, step):
        super().__init__()
        self.job_id,self.step,self.progress,self.last_message=job_id,step,{},None
        self.completed=set()
    def emit(self, record):
        if record.name not in ('favorites','app.exhentai_search','app.sync_translations'):
            return
        raw=record.getMessage()
        message=None; values={}; level='info'
        if match:=re.match(r'正在处理每日分组 (\d+)/(\d+)',raw):
            self.progress={};self.completed.clear()
            values={'group':int(match[1]),'totalGroups':int(match[2]),'phase':'pages'};message=f'开始每日分组 {match[1]} / {match[2]}'
        elif raw in ('正在下载标签词典','标签词典下载完成，正在解析校验'):
            message=raw
        elif match:=re.match(r'第\s*(\d+)\s*页解析\s*(\d+)\s*条，累计\s*(\d+)\s*条',raw):
            values={'pages':int(match[1]),'items':int(match[3]),'phase':'pages'};message=f'收藏列表第 {match[1]} 页，本页 {match[2]} 条，累计 {match[3]} 条'
        elif match:=re.match(r'第\s*(\d+)\s*页找到\s*(\d+)\s*个画廊',raw):
            values={'pages':int(match[1]),'pageItems':int(match[2]),'phase':'pages'};message=f'每日搜索第 {match[1]} 页，找到 {match[2]} 个画廊'
        elif match:=re.match(r'开始获取元数据，共\s*(\d+)\s*批',raw):
            values={'totalBatches':int(match[1]),'completedBatches':0,'phase':'metadata'};message=f'开始补全元数据，共 {match[1]} 批'
        elif match:=re.match(r'第\s*(\d+)\s*批成功，获取\s*(\d+)\s*条',raw):
            self.completed.add(int(match[1]));done=len(self.completed)
            values={'batch':int(match[1]),'completedBatches':done,'phase':'metadata'};message=f'元数据第 {match[1]} 批完成，获取 {match[2]} 条'
        elif match:=re.match(r'(?:正在请求|请求)第\s*(\d+)\s*批，共\s*(\d+)\s*条',raw):
            values={'batch':int(match[1]),'phase':'metadata'};message=f'正在请求元数据第 {match[1]} 批（{match[2]} 条）'
        elif match:=re.match(r'第\s*(\d+)\s*轮重试，处理\s*(\d+)\s*个失败批次',raw):
            values={'retry':int(match[1])};message=f'第 {match[1]} 轮重试，剩余 {match[2]} 个批次';level='warning'
        elif raw.startswith(('正在爬取:', '获取第 ')):
            message='正在请求下一页列表'
        elif record.levelno>=logging.WARNING:
            message='上游请求异常，正在重试或检查完整性；失败时保留当前数据';level='warning'
        if not message or (message==self.last_message and not values):return
        self.last_message=message;self.progress.update(values)
        with db.connect() as con:
            con.execute('UPDATE job_steps SET progress_json=? WHERE job_id=? AND name=?',(db.dumps(self.progress),self.job_id,self.step))
            event(self.job_id,self.step,message,level,values,con)


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
    logger=logging.getLogger('app.sync_translations')
    logger.info('正在下载标签词典')
    content=download_with_retry()
    logger.info('标签词典下载完成，正在解析校验')
    return validate_and_parse(content)


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
    for index,group in enumerate(groups):
        logging.getLogger('app.exhentai_search').info(f'正在处理每日分组 {index+1}/{len(groups)}')
        builder = ExHentaiUrlBuilder().set_keyword(group['keyword']).set_only_category(group['categories'])
        builder.min_pages, builder.max_pages, builder.min_rating = group['minPages'], group['maxPages'], group['minRating']
        builder.advsearch = any(group[k] is not None for k in ('minPages', 'maxPages', 'minRating'))
        cutoff = (datetime.now(timezone.utc) - timedelta(days=group['cutoffDays'])).strftime('%Y-%m-%d')
        result = search.search_with_builder(builder, fetch_details=True, cutoff_date=cutoff)
        if not result['success']:
            raise JobFailure('每日搜索分组抓取失败，保留上一份完整快照')
        output.append({'name': group['name'], 'conditions': conditions(group), 'generatedAt': db.now(),
                       'cutoffDate': cutoff, 'galleries': result['galleries']})
    return output


def execute(job_id, allow_shrink=False):
    from .cli import backup
    backup()
    event(job_id,'backup','同步前一致性备份已完成')
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
                event(job_id,stage,'复用原任务已成功的检查点')
                continue
            event(job_id,stage,'开始执行：'+KINDS[stage])
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
                event(job_id,stage,'抓取完成，正在校验结果')
                count = len(collected[stage]) if stage == 'favorites' else sum(len(g.get('galleries', [])) for g in collected[stage]) if stage == 'daily' else sum(len(g.get('data', {})) for g in collected[stage].get('data', []))
                with db.connect() as con:
                    con.execute("UPDATE job_steps SET status='success',finished_at=?,result_json=?,summary=? WHERE job_id=? AND name=?",
                                (db.now(), db.dumps(collected[stage]), f'已获取 {count} 条记录', job_id, stage))
            except Exception:
                event(job_id,stage,'步骤执行失败，尚未发布的数据已保留','error')
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
            frozen = {group['name']: group for group in config['daily']}
            for group in collected['daily']:
                group.pop('filters', None)
                if group['name'] in frozen:
                    group['conditions'] = conditions(frozen[group['name']])
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
        event(job_id,'publish','完整性与版本检查通过，数据已事务发布',con=con)
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
                        event(row[0],'queue','worker 已领取任务',con=con)
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
                        event(row[0],'finish',message,'info' if conclusion=='success' else 'error',con=con)
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
        event(job_id,'finish',message,'error',con=con)
        con.execute("UPDATE jobs SET status='completed',conclusion=?,summary=?,updated_at=? WHERE id=? AND status='in_progress'",
                    (conclusion, f'{stage}。{message}', db.now(), job_id))
