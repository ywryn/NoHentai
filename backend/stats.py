from datetime import datetime, timedelta, timezone
import re
from threading import Lock
from .validation import CATEGORIES
from .db import now


# A shared, bounded SQLite cache works across API workers and process restarts.
# Include UTC day because the rolling heatmap changes even without data edits.
CACHE_PREFIX = 'statistics:v1:'
_BUILD_LOCK = Lock()
TAG_KINDS = ('artist', 'other', 'female', 'male', 'character', 'parody')


def utc_today():
    return datetime.now(timezone.utc).date()


def _posted_quarter(value):
    try:
        date = datetime.fromtimestamp(int(value), timezone.utc)
        return f'{date.year}-Q{(date.month-1)//3+1}'
    except (ValueError, OverflowError, OSError, TypeError):
        return None


def _favorite_date(value):
    match = re.search(r'(\d{4})-(\d{2})-(\d{2})', str(value or ''))
    return match[0] if match else None


def _favorite_quarter(value):
    date = _favorite_date(value)
    return f'{int(date[:4])}-Q{(int(date[5:7])-1)//3+1}' if date else None


def aggregate(con, today):
    """Aggregate the effective catalog in SQL; never deserialize all galleries."""
    from . import catalog
    con.execute('PRAGMA temp_store=MEMORY')
    for name, function in (('stats_posted_quarter', _posted_quarter), ('stats_favorite_date', _favorite_date), ('stats_favorite_quarter', _favorite_quarter)):
        con.create_function(name, 1, function, deterministic=True)
    # Materialize only the columns needed by statistics once, inside the same
    # read snapshot as the revision. No main-database write lock is held.
    con.execute('CREATE TEMP TABLE stats_input AS ' + catalog.VISIBLE + """
        SELECT position,json_extract(data,'$.category') AS category,
            CASE WHEN json_type(data,'$.tags')='array' THEN json_extract(data,'$.tags') ELSE '[]' END AS tags,
            stats_posted_quarter(json_extract(data,'$.posted')) AS posted_quarter,
            stats_favorite_date(json_extract(data,'$.favTime')) AS favorite_date,
            stats_favorite_quarter(json_extract(data,'$.favTime')) AS favorite_quarter
        FROM visible""")
    categories = dict(con.execute('SELECT category,COUNT(*) FROM stats_input GROUP BY category'))
    ranked = con.execute("""
        WITH counts AS (
            SELECT t.value AS tag,substr(t.value,1,instr(t.value,':')-1) AS namespace,
                COUNT(*) AS count,MIN(printf('%020d:%010d',s.position,t.key)) AS first_seen
            FROM stats_input s,json_each(s.tags) t WHERE t.type='text'
            GROUP BY t.value
        ), ranked AS (
            SELECT *,ROW_NUMBER() OVER(PARTITION BY namespace ORDER BY count DESC,first_seen,tag) AS rank
            FROM counts WHERE namespace IN ('artist','other','female','male','character','parody')
        ) SELECT tag,namespace,count FROM ranked WHERE rank<=20 ORDER BY namespace,rank
    """).fetchall()
    index = catalog.translations(con)
    tags = {kind: [] for kind in TAG_KINDS}
    for row in ranked:
        tag, namespace, count = row
        value = tag.split(':', 1)[1]
        detail = index.get(tag, {})
        tags[namespace].append({'tag': tag, 'namespace': namespace, 'value': value, 'count': count,
                                'tag_cn': detail.get('name', ''), 'intro': detail.get('intro', ''), 'links': detail.get('links', '')})
    quarters = [dict(row) for row in con.execute("""
        SELECT quarter,SUM(postedCount) AS postedCount,SUM(favTimeCount) AS favTimeCount FROM (
            SELECT posted_quarter AS quarter,COUNT(*) AS postedCount,0 AS favTimeCount
                FROM stats_input WHERE posted_quarter IS NOT NULL GROUP BY posted_quarter
            UNION ALL
            SELECT favorite_quarter AS quarter,0 AS postedCount,COUNT(*) AS favTimeCount
                FROM stats_input WHERE favorite_quarter IS NOT NULL GROUP BY favorite_quarter
        ) GROUP BY quarter ORDER BY quarter""")]
    days = dict(con.execute('SELECT favorite_date,COUNT(*) FROM stats_input WHERE favorite_date IS NOT NULL GROUP BY favorite_date'))
    try:
        start = today.replace(year=today.year-1)
    except ValueError:
        start = today.replace(year=today.year-1, day=28)
    start -= timedelta(days=(start.weekday()+1) % 7)
    matrix = []
    date = start
    while date <= today:
        matrix.append({'x': (date-start).days//7, 'y': (date.weekday()+1)%7, 'v': days.get(date.isoformat(), 0), 'd': date.isoformat()})
        date += timedelta(days=1)
    return {'generatedAt': now(), 'stats': {'total_count': sum(categories.values()), 'categories': {c: categories.get(c, 0) for c in CATEGORIES}},
            'tags': tags, 'quarterly': quarters, 'heatmap': {'data': matrix, 'maxValue': max([1]+[d['v'] for d in matrix])}}


def _build_current():
    import json
    import time
    from . import db
    today = utc_today()
    stamp = time.time()
    with db.connect() as con:
        con.execute('BEGIN')
        revision = db.snapshot(con, 'catalog-revision')
        key = CACHE_PREFIX + today.isoformat() + ':' + str(revision)
        cached = con.execute('SELECT data FROM cache WHERE key=? AND expires>?', (key, stamp)).fetchone()
        if cached:
            return json.loads(cached[0])
        result = aggregate(con, today)
        result['revision'] = revision
    # Another worker may have built this same snapshot concurrently. Keep the
    # first complete result; never label newer data with an older revision.
    with db.connect() as con:
        con.execute('BEGIN IMMEDIATE')
        con.execute('INSERT INTO cache(key,data,expires) VALUES (?,?,?) ON CONFLICT(key) DO UPDATE SET data=excluded.data,expires=excluded.expires WHERE cache.expires<=?',
                    (key, db.dumps(result), stamp+2*86400, stamp))
        con.execute('DELETE FROM cache WHERE key LIKE ? AND key NOT IN (SELECT key FROM cache WHERE key LIKE ? ORDER BY expires DESC,key DESC LIMIT 4)',
                    (CACHE_PREFIX+'%', CACHE_PREFIX+'%'))
        # Return the first writer's generatedAt consistently across workers.
        cached = con.execute('SELECT data FROM cache WHERE key=?', (key,)).fetchone()
    return json.loads(cached[0]) if cached else result


def current():
    import json
    import time
    from . import db
    # Fast path stays lock-free. Serialize cold builds inside each API process
    # so a burst of thread-pool requests cannot all aggregate the same version.
    with db.connect() as con:
        con.execute('BEGIN')
        revision=db.snapshot(con,'catalog-revision')
        key=CACHE_PREFIX+utc_today().isoformat()+':'+str(revision)
        cached=con.execute('SELECT data FROM cache WHERE key=? AND expires>?',(key,time.time())).fetchone()
        if cached:return json.loads(cached[0])
    with _BUILD_LOCK:
        # Recheck the shared cache and revision after waiting for another build.
        return _build_current()
