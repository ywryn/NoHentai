"""Transactional schema upgrades. Keep v1 content and historical snapshots intact."""
import json
import uuid

SCHEMA_VERSION = 2


def upgrade(con, now):
    version = con.execute('PRAGMA user_version').fetchone()[0]
    if version > SCHEMA_VERSION:
        raise RuntimeError('数据库版本高于此代码版本，拒绝降级启动')
    if version >= SCHEMA_VERSION:
        return
    con.execute('BEGIN IMMEDIATE')
    # Recheck after acquiring the write lock (multiple Uvicorn processes start).
    if con.execute('PRAGMA user_version').fetchone()[0] >= SCHEMA_VERSION:
        return
    statements = [
        'CREATE TABLE resource_versions(name TEXT PRIMARY KEY, version TEXT NOT NULL)',
        'CREATE TABLE gallery_overrides(gid TEXT PRIMARY KEY, data TEXT NOT NULL, version TEXT NOT NULL, updated_at TEXT NOT NULL)',
        'CREATE TABLE daily_rules(id TEXT PRIMARY KEY, position INTEGER NOT NULL, data TEXT NOT NULL, version TEXT NOT NULL, updated_at TEXT NOT NULL)',
        'CREATE TABLE record_history(id INTEGER PRIMARY KEY, kind TEXT NOT NULL, record_id TEXT NOT NULL, version TEXT NOT NULL, before_json TEXT, after_json TEXT, changes_json TEXT NOT NULL, created_at TEXT NOT NULL, message TEXT NOT NULL)',
        'CREATE INDEX record_history_lookup ON record_history(kind,record_id,id DESC)',
        'CREATE TABLE service_settings(name TEXT PRIMARY KEY, value_json TEXT NOT NULL, updated_at TEXT NOT NULL)',
        'CREATE TABLE service_versions(name TEXT PRIMARY KEY, version TEXT NOT NULL)',
        'CREATE TABLE service_checks(name TEXT PRIMARY KEY, version TEXT NOT NULL, ok INTEGER NOT NULL, message TEXT NOT NULL, checked_at TEXT NOT NULL)',
        'CREATE TABLE accounts(id INTEGER PRIMARY KEY CHECK(id=1), password_hash TEXT NOT NULL, updated_at TEXT NOT NULL)',
        'CREATE TABLE schedules(kind TEXT PRIMARY KEY, enabled INTEGER NOT NULL DEFAULT 0, hour INTEGER NOT NULL, minute INTEGER NOT NULL, timezone TEXT NOT NULL, next_run_at TEXT, last_enqueued_at TEXT, version TEXT NOT NULL)',
        'CREATE TABLE job_steps(job_id INTEGER NOT NULL REFERENCES jobs(id) ON DELETE CASCADE, name TEXT NOT NULL, status TEXT NOT NULL, started_at TEXT, finished_at TEXT, progress_json TEXT NOT NULL DEFAULT \'{}\', result_json TEXT, summary TEXT NOT NULL DEFAULT \'\', PRIMARY KEY(job_id,name))',
        'CREATE TABLE media(id TEXT PRIMARY KEY, filename TEXT NOT NULL UNIQUE, mime TEXT NOT NULL, size INTEGER NOT NULL, width INTEGER NOT NULL, height INTEGER NOT NULL, created_at TEXT NOT NULL)',
        'CREATE TABLE service_leases(id TEXT PRIMARY KEY, service TEXT NOT NULL, expires REAL NOT NULL)',
        'ALTER TABLE jobs ADD COLUMN config_json TEXT',
        'ALTER TABLE jobs ADD COLUMN config_ciphertext TEXT',
        'ALTER TABLE jobs ADD COLUMN cancel_requested INTEGER NOT NULL DEFAULT 0',
        'ALTER TABLE jobs ADD COLUMN parent_id INTEGER REFERENCES jobs(id)',
        'ALTER TABLE sessions ADD COLUMN created_at TEXT',
        'ALTER TABLE sessions ADD COLUMN last_seen TEXT',
        'ALTER TABLE sessions ADD COLUMN csrf TEXT',
        'ALTER TABLE sessions ADD COLUMN agent TEXT NOT NULL DEFAULT \'\'',
        'ALTER TABLE books RENAME TO books_v1',
        'CREATE TABLE books(id TEXT PRIMARY KEY, position INTEGER NOT NULL, data TEXT NOT NULL, gallery_gid TEXT, version TEXT NOT NULL, updated_at TEXT NOT NULL)',
        'CREATE INDEX books_position ON books(position)',
        'CREATE INDEX books_gallery ON books(gallery_gid)',
    ]
    for statement in statements:
        con.execute(statement)
    for field in ('title', 'title_jpn', 'category', 'uploader', 'posted'):
        con.execute(f'ALTER TABLE galleries ADD COLUMN {field} TEXT')
        con.execute(f"UPDATE galleries SET {field}=json_extract(data,'$.{field}')")
    con.execute('CREATE INDEX galleries_category ON galleries(category)')
    con.execute('CREATE INDEX galleries_posted ON galleries(posted)')
    for row in con.execute('SELECT position,data FROM books_v1').fetchall():
        book = json.loads(row['data'])
        con.execute('INSERT INTO books VALUES (?,?,?,?,?,?)',
                    (uuid.uuid4().hex, row['position'], row['data'], book.get('sid') or None, uuid.uuid4().hex, now))
    assert con.execute('SELECT COUNT(*) FROM books').fetchone()[0] == con.execute('SELECT COUNT(*) FROM books_v1').fetchone()[0]
    con.execute('DROP TABLE books_v1')
    for name in ('overrides', 'printed', 'daily'):
        row = con.execute('SELECT data,version FROM resources WHERE name=?', (name,)).fetchone()
        if row:
            con.execute('INSERT INTO resource_versions VALUES (?,?)', (name, row['version']))
            value = json.loads(row['data'])
            if name == 'overrides':
                con.executemany('INSERT INTO gallery_overrides VALUES (?,?,?,?)',
                    [(gid, json.dumps(data, ensure_ascii=False), uuid.uuid4().hex, now) for gid, data in value.items()])
            if name == 'daily':
                con.executemany('INSERT INTO daily_rules VALUES (?,?,?,?,?)',
                    [(uuid.uuid4().hex, i, json.dumps(data, ensure_ascii=False), uuid.uuid4().hex, now) for i, data in enumerate(value)])
            con.execute('DELETE FROM resources WHERE name=?', (name,))
    for kind in ('favorites', 'daily', 'translations'):
        con.execute('INSERT INTO schedules(kind,hour,minute,timezone,version) VALUES (?,4,0,?,?)',
                    (kind, 'Asia/Shanghai', uuid.uuid4().hex))
    for group in ('favorites', 'translate', 'ocr'):
        con.execute('INSERT INTO service_versions VALUES (?,?)', (group, uuid.uuid4().hex))
    con.execute('PRAGMA user_version=2')
