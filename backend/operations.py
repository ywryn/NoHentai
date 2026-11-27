import json
import re
import sqlite3
import time
from datetime import datetime, timezone
from . import db, settings, security, traffic
from .migrations import SCHEMA_VERSION
from .security import fail


def database_backups(directory):
    return sorted((*directory.glob('nohentai-*.sqlite3'), *directory.glob('nohentai-*.sqlite3.gz')), reverse=True)


def backup_media_path(path):
    return path.with_name(path.name.split('.', 1)[0] + '.media.zip')


def backups():
    items = []
    for path in database_backups(settings.DATA_DIR / 'backups'):
        try:
            stat = path.stat()
        except FileNotFoundError:
            continue
        media = backup_media_path(path)
        items.append({'name': path.name, 'size': stat.st_size, 'modified': stat.st_mtime,
                      'media': media.name if media.exists() else None})
    return {'items': items}


def backup_file(name):
    if not re.fullmatch(r'nohentai-[0-9]{8}T[0-9]{12}Z\.(?:sqlite3(?:\.gz)?|media\.zip)', name):
        fail(404, '备份不存在')
    path = settings.DATA_DIR / 'backups' / name
    if not path.is_file():
        fail(404, '备份不存在')
    return path


def overview():
    month = datetime.now(timezone.utc).strftime('%Y-%m')
    vision_key, translation_key = f'vision:{month}', f'google-translate:{month}'
    with db.connect() as con:
        recent = [dict(r) for r in con.execute('SELECT id,kind,status,conclusion,created_at,updated_at,summary FROM jobs ORDER BY id DESC LIMIT 8')]
        successes = {r['kind']: {'at': r['updated_at'], 'id': r['id']} for r in con.execute("SELECT j.* FROM jobs j JOIN (SELECT kind,MAX(id) AS latest FROM jobs WHERE conclusion='success' GROUP BY kind) x ON x.latest=j.id")}
        if 'all' in successes:
            for kind in ('favorites','translations','daily'):
                if successes['all']['id']>successes.get(kind,{}).get('id',0):successes[kind]=successes['all']
        heartbeat = db.snapshot(con, 'worker-heartbeat', 0)
        counts = {'galleries': con.execute('SELECT COUNT(*) FROM galleries').fetchone()[0],
                  'books': con.execute('SELECT COUNT(*) FROM books').fetchone()[0],
                  'overrides': con.execute("SELECT COUNT(*) FROM gallery_overrides WHERE data!='{}'").fetchone()[0],
                  'rules': con.execute('SELECT COUNT(*) FROM daily_rules').fetchone()[0]}
        from .services import version, status
        checks = [dict(r) | {'current': r['version']==version(con,r['name'])} for r in con.execute('SELECT * FROM service_checks')]
        counters = {r['key']: r['count'] for r in con.execute(
            'SELECT key, count FROM counters WHERE key IN (?, ?) AND expires > ?',
            (vision_key, translation_key, time.time()))}
        schedule = [dict(r) for r in con.execute('SELECT * FROM schedules')]
        visit_totals = traffic.overview(con)
    service_groups = status()['groups']
    service_fields = {field['key']: field for group in service_groups for field in group['fields']}
    local_usage = {'month': month, 'items': [
        {'id': 'vision', 'count': counters.get(vision_key, 0),
         'limit': service_fields['VISION_MONTHLY_LIMIT']['value'],
         'configured': service_fields['GOOGLE_VISION_API_KEY']['configured']},
        {'id': 'google-translate', 'count': counters.get(translation_key, 0),
         'limit': service_fields['GOOGLE_TRANSLATE_MONTHLY_CHARS']['value'],
         'configured': service_fields['GOOGLE_TRANSLATE_API_KEY']['configured']},
    ]}
    return {'counts': counts, 'successes': successes, 'recent': recent, 'workerAlive': time.time()-heartbeat < 60,
            'checks': checks, 'localUsage': local_usage, 'traffic': visit_totals,
            'usage': [{'name': vision_key, 'count': counters[vision_key]}] if vision_key in counters else [],
            'schedules': schedule, 'backup': next(iter(backups()['items']), None),
            'schema': SCHEMA_VERSION, 'workerHeartbeat': heartbeat, 'databaseBytes': settings.DB_PATH.stat().st_size, 'services': service_groups, 'checkedAt':db.now()}
