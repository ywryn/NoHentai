import json
import re
import sqlite3
import time
from pathlib import Path
from . import db, settings, security
from .security import fail


def backups():
    directory = settings.DATA_DIR / 'backups'
    items = []
    for path in sorted(directory.glob('nohentai-*.sqlite3'), reverse=True):
        items.append({'name': path.name, 'size': path.stat().st_size, 'modified': path.stat().st_mtime,
                      'media': path.with_suffix('.media.zip').name if path.with_suffix('.media.zip').exists() else None})
    return {'items': items}


def backup_file(name):
    if not re.fullmatch(r'nohentai-[0-9]{8}T[0-9]{12}Z\.(?:sqlite3|media\.zip)', name):
        fail(404, '备份不存在')
    path = settings.DATA_DIR / 'backups' / name
    if not path.is_file():
        fail(404, '备份不存在')
    return path


def overview():
    with db.connect() as con:
        recent = [dict(r) for r in con.execute('SELECT id,kind,status,conclusion,created_at,updated_at,summary FROM jobs ORDER BY id DESC LIMIT 8')]
        successes = {r['kind']: {'at': r['updated_at'], 'id': r['id']} for r in con.execute("SELECT j.* FROM jobs j JOIN (SELECT kind,MAX(id) AS latest FROM jobs WHERE conclusion='success' GROUP BY kind) x ON x.latest=j.id")}
        heartbeat = db.snapshot(con, 'worker-heartbeat', 0)
        counts = {'galleries': con.execute('SELECT COUNT(*) FROM galleries').fetchone()[0],
                  'books': con.execute('SELECT COUNT(*) FROM books').fetchone()[0],
                  'overrides': con.execute("SELECT COUNT(*) FROM gallery_overrides WHERE data!='{}'").fetchone()[0],
                  'rules': con.execute('SELECT COUNT(*) FROM daily_rules').fetchone()[0]}
        from .services import version
        checks = [dict(r) | {'current': r['version']==version(con,r['name'])} for r in con.execute('SELECT * FROM service_checks')]
        counters = [{'name': r['key'], 'count': r['count']} for r in con.execute("SELECT * FROM counters WHERE key LIKE 'vision:%' AND expires>?", (time.time(),))]
        schedule = [dict(r) for r in con.execute('SELECT * FROM schedules')]
    return {'counts': counts, 'successes': successes, 'recent': recent, 'workerAlive': time.time()-heartbeat < 60,
            'checks': checks, 'usage': counters, 'schedules': schedule, 'backup': next(iter(backups()['items']), None),
            'schema': 2}
