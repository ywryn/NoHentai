from datetime import datetime, timedelta, timezone
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError
import uuid
from . import db
from .security import fail

KINDS = ('favorites', 'daily', 'translations')


def next_run(hour, minute, zone, after=None):
    local = (after or datetime.now(timezone.utc)).astimezone(ZoneInfo(zone))
    target = local.replace(hour=hour, minute=minute, second=0, microsecond=0)
    if target <= local:
        target += timedelta(days=1)
    return target.astimezone(timezone.utc).isoformat()


def listing():
    with db.connect() as con:
        return {'items': [dict(r) for r in con.execute('SELECT * FROM schedules ORDER BY kind')]}


def save(kind, expected, enabled, hour, minute, zone):
    if kind not in KINDS or type(enabled) is not bool or type(hour) is not int or not 0 <= hour <= 23 or type(minute) is not int or not 0 <= minute <= 59:
        fail(400, '调度参数不正确')
    try:
        ZoneInfo(zone)
    except (ZoneInfoNotFoundError, TypeError, ValueError):
        fail(400, '时区无效')
    with db.connect() as con:
        con.execute('BEGIN IMMEDIATE')
        row = con.execute('SELECT version FROM schedules WHERE kind=?', (kind,)).fetchone()
        if not row or row[0] != expected:
            fail(409, '调度已更新，请重新加载')
        con.execute('UPDATE schedules SET enabled=?,hour=?,minute=?,timezone=?,next_run_at=?,version=? WHERE kind=?',
                    (int(enabled), hour, minute, zone, next_run(hour, minute, zone) if enabled else None, uuid.uuid4().hex, kind))
        con.execute('INSERT INTO history(resource,version,data,created_at,message) VALUES (?,?,?,?,?)',
                    ('schedule:'+kind, uuid.uuid4().hex, db.dumps({'enabled':enabled,'hour':hour,'minute':minute,'timezone':zone}), db.now(), '更新每日调度'))
    return {'ok': True}


def tick():
    from . import jobs
    # enqueue and next_run update share one transaction. Worker restart cannot
    # double enqueue a due occurrence; a missed run queues once on recovery.
    with db.connect() as con:
        con.execute('BEGIN IMMEDIATE')
        due = con.execute('SELECT * FROM schedules WHERE enabled=1 AND next_run_at<=?', (db.now(),)).fetchall()
        for row in due:
            jobs.enqueue_in(con, row['kind'])
            con.execute('UPDATE schedules SET last_enqueued_at=?,next_run_at=? WHERE kind=?',
                        (db.now(), next_run(row['hour'], row['minute'], row['timezone']), row['kind']))
