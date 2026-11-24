"""First-party aggregate page views and browser-level unique visitors."""
import hmac
import re
import secrets
from datetime import datetime
from hashlib import sha256
from zoneinfo import ZoneInfo

from . import db, settings

COOKIE = 'nh_visit'
COOKIE_PATH = '/api/visits'
COOKIE_MAX_AGE = 365 * 86400
SITE_TIMEZONE = ZoneInfo('Asia/Shanghai')


def today():
    return datetime.now(SITE_TIMEZONE).date().isoformat()


def sign(visitor):
    return hmac.new(settings.encryption_key(), ('traffic:' + visitor).encode(), 'sha256').hexdigest()


def record_visit(cookie):
    if cookie and re.fullmatch(r'[0-9a-f]{32}\.[0-9a-f]{64}', cookie):
        visitor, signature = cookie.split('.')
        if not hmac.compare_digest(signature, sign(visitor)):
            cookie = None
    else:
        cookie = None

    if not cookie:
        visitor = secrets.token_hex(16)
        cookie = visitor + '.' + sign(visitor)

    digest = sha256(visitor.encode()).digest()
    with db.connect() as con:
        con.execute('BEGIN IMMEDIATE')
        day = today()
        first_visit = con.execute(
            'INSERT OR IGNORE INTO traffic_visitors VALUES (?, ?)', (digest, day)).rowcount
        first_today = first_visit or con.execute(
            'UPDATE traffic_visitors SET last_day=? WHERE visitor=? AND last_day<?', (day, digest, day)).rowcount
        con.execute('''INSERT INTO traffic_daily(day, views, visitors, new_visitors) VALUES (?, 1, ?, ?)
            ON CONFLICT(day) DO UPDATE SET views=views+1, visitors=visitors+excluded.visitors,
            new_visitors=new_visitors+excluded.new_visitors''', (day, first_today, first_visit))
    return cookie if first_today else None


def overview(con):
    day = today()
    row = con.execute('''SELECT
        COALESCE(MAX(CASE WHEN day=? THEN views END), 0) AS todayViews,
        COALESCE(MAX(CASE WHEN day=? THEN visitors END), 0) AS todayVisitors,
        COALESCE(SUM(views), 0) AS totalViews,
        COALESCE(SUM(new_visitors), 0) AS totalVisitors
        FROM traffic_daily''', (day, day)).fetchone()
    return {'date': day, 'timezone': SITE_TIMEZONE.key, **dict(row)}
