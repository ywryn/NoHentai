"""Short-lived connections; all replacements use one SQLite transaction."""
import json
import os
import sqlite3
import time
import uuid
from contextlib import contextmanager
from datetime import datetime, timezone
from . import settings


def now():
    return datetime.now(timezone.utc).isoformat()


def dumps(data):
    return json.dumps(data, ensure_ascii=False, separators=(',', ':'), allow_nan=False)


@contextmanager
def connect():
    settings.DATA_DIR.mkdir(parents=True, exist_ok=True, mode=0o700)
    con = sqlite3.connect(settings.DB_PATH, timeout=30)
    con.row_factory = sqlite3.Row
    con.execute('PRAGMA foreign_keys=ON')
    con.execute('PRAGMA busy_timeout=30000')
    try:
        with con:
            yield con
    finally:
        con.close()


def initialize():
    with connect() as con:
        con.execute('PRAGMA journal_mode=WAL')
        if con.execute('PRAGMA user_version').fetchone()[0] > 2:
            raise RuntimeError('数据库版本高于此代码版本，拒绝降级启动')
        con.executescript('''
        CREATE TABLE IF NOT EXISTS galleries (gid TEXT PRIMARY KEY, position INTEGER NOT NULL, data TEXT NOT NULL);
        CREATE INDEX IF NOT EXISTS galleries_position ON galleries(position);
        CREATE TABLE IF NOT EXISTS books (position INTEGER PRIMARY KEY, data TEXT NOT NULL);
        CREATE TABLE IF NOT EXISTS resources (name TEXT PRIMARY KEY, data TEXT NOT NULL, version TEXT NOT NULL);
        CREATE TABLE IF NOT EXISTS snapshots (name TEXT PRIMARY KEY, data TEXT NOT NULL, updated_at TEXT NOT NULL);
        CREATE TABLE IF NOT EXISTS history (id INTEGER PRIMARY KEY, resource TEXT NOT NULL, version TEXT NOT NULL,
            data TEXT NOT NULL, created_at TEXT NOT NULL, message TEXT NOT NULL);
        CREATE TABLE IF NOT EXISTS credentials (name TEXT PRIMARY KEY, ciphertext TEXT NOT NULL, updated_at TEXT NOT NULL);
        CREATE TABLE IF NOT EXISTS sessions (digest TEXT PRIMARY KEY, expires REAL NOT NULL, fingerprint TEXT NOT NULL);
        CREATE TABLE IF NOT EXISTS cache (key TEXT PRIMARY KEY, data TEXT NOT NULL, expires REAL NOT NULL);
        CREATE TABLE IF NOT EXISTS counters (key TEXT PRIMARY KEY, count INTEGER NOT NULL, expires REAL NOT NULL);
        CREATE TABLE IF NOT EXISTS jobs (id INTEGER PRIMARY KEY, kind TEXT NOT NULL, status TEXT NOT NULL,
            conclusion TEXT, created_at TEXT NOT NULL, updated_at TEXT NOT NULL, summary TEXT NOT NULL DEFAULT '');
        ''')
        from .migrations import upgrade
        upgrade(con, now())
        con.execute("INSERT OR IGNORE INTO snapshots VALUES ('catalog-revision',?,?)", (dumps(uuid.uuid4().hex), now()))
    os.chmod(settings.DB_PATH, 0o600)


def resource(con, name):
    if name in ('overrides', 'printed', 'daily'):
        row = con.execute('SELECT version FROM resource_versions WHERE name=?', (name,)).fetchone()
        if not row:
            raise RuntimeError('数据库尚未导入，请运行 python -m backend.cli init')
        if name == 'overrides':
            data = {r['gid']: json.loads(r['data']) for r in con.execute("SELECT gid,data FROM gallery_overrides WHERE data!='{}'")}
        else:
            table = 'books' if name == 'printed' else 'daily_rules'
            data = [json.loads(r[0]) for r in con.execute(f'SELECT data FROM {table} ORDER BY position')]
        return data, row['version']
    row = con.execute('SELECT * FROM resources WHERE name=?', (name,)).fetchone()
    if not row:
        raise RuntimeError('数据库尚未导入，请运行 python -m backend.cli init')
    return json.loads(row['data']), row['version']


def bump_resource(con, name):
    version = uuid.uuid4().hex
    con.execute('INSERT OR REPLACE INTO resource_versions VALUES (?,?)', (name, version))
    if name == 'overrides':
        put_snapshot(con, 'catalog-revision', uuid.uuid4().hex)
    put_snapshot(con, 'release', {'commit': version, 'builtAt': now()})
    return version


def put_resource(con, name, data, message='管理后台保存'):
    version, text = uuid.uuid4().hex, dumps(data)
    if name in ('overrides', 'printed', 'daily'):
        if name == 'overrides':
            # Keep versioned empty patches as tombstones for conflict detection.
            previous = {r[0] for r in con.execute('SELECT gid FROM gallery_overrides')}
            for gid in previous | data.keys():
                con.execute('INSERT OR REPLACE INTO gallery_overrides VALUES (?,?,?,?)',
                            (gid, dumps(data.get(gid, {})), uuid.uuid4().hex, now()))
        else:
            table = 'books' if name == 'printed' else 'daily_rules'
            previous = {r['position']: r['id'] for r in con.execute(f'SELECT id,position FROM {table}')}
            con.execute(f'DELETE FROM {table}')
            for i, item in enumerate(data):
                record_id = previous.get(i, uuid.uuid4().hex)
                if name == 'printed':
                    con.execute('INSERT INTO books VALUES (?,?,?,?,?,?)', (record_id, i, dumps(item), item.get('sid') or None, uuid.uuid4().hex, now()))
                else:
                    con.execute('INSERT INTO daily_rules VALUES (?,?,?,?,?)', (record_id, i, dumps(item), uuid.uuid4().hex, now()))
        version = bump_resource(con, name)
    else:
        con.execute('INSERT OR REPLACE INTO resources VALUES (?,?,?)', (name, text, version))
    con.execute('INSERT INTO history(resource,version,data,created_at,message) VALUES (?,?,?,?,?)',
                (name, version, text, now(), message))
    return version


def snapshot(con, name, default=None):
    row = con.execute('SELECT data FROM snapshots WHERE name=?', (name,)).fetchone()
    return json.loads(row[0]) if row else default


def put_snapshot(con, name, data):
    con.execute('INSERT OR REPLACE INTO snapshots VALUES (?,?,?)', (name, dumps(data), now()))
    if name == 'translations':
        put_snapshot(con, 'catalog-revision', uuid.uuid4().hex)


def replace_galleries(con, data, allow_shrink=False):
    if not isinstance(data, list) or not data:
        raise ValueError('收藏结果为空，保留原数据')
    ids = [str(g['gid']) for g in data]
    if any(not i.isdecimal() or int(i) < 1 for i in ids) or len(set(ids)) != len(ids):
        raise ValueError('画廊 ID 缺失或重复')
    previous = con.execute('SELECT COUNT(*) FROM galleries').fetchone()[0]
    if len(data) < previous * .8 and not allow_shrink:
        raise ValueError('收藏数量下降超过 20%，保留原数据；确认主动删除后通过 CLI 显式允许')
    con.execute('DELETE FROM galleries')
    con.executemany('INSERT INTO galleries(gid,position,data,title,title_jpn,category,uploader,posted) VALUES (?,?,?,?,?,?,?,?)',
                    [(str(g['gid']), i, dumps(g), *(g.get(k) for k in ('title','title_jpn','category','uploader','posted'))) for i,g in enumerate(data)])
    put_snapshot(con, 'catalog-revision', uuid.uuid4().hex)
    put_snapshot(con, 'favorites-revision', uuid.uuid4().hex)


def galleries(con):
    return [json.loads(r[0]) for r in con.execute('SELECT data FROM galleries ORDER BY position')]


def get_cache(key):
    with connect() as con:
        row = con.execute('SELECT data FROM cache WHERE key=? AND expires>?', (key, time.time())).fetchone()
        return json.loads(row[0]) if row else None


def set_cache(key, data, ttl):
    with connect() as con:
        con.execute('DELETE FROM cache WHERE expires<?', (time.time(),))
        con.execute('INSERT OR REPLACE INTO cache VALUES (?,?,?)', (key, dumps(data), time.time() + ttl))


def reserve(key, limit, ttl):
    """Atomic counter, shared between API workers and persistent across restart."""
    if limit <= 0:
        return False
    with connect() as con:
        con.execute('BEGIN IMMEDIATE')
        con.execute('DELETE FROM counters WHERE expires<?', (time.time(),))
        row = con.execute('SELECT count FROM counters WHERE key=?', (key,)).fetchone()
        if row and row[0] >= limit:
            return False
        con.execute('INSERT INTO counters VALUES (?,1,?) ON CONFLICT(key) DO UPDATE SET count=count+1',
                    (key, time.time() + ttl))
        return True
