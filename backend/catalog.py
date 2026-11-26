"""Public catalog: SQL filtering/counting/pagination, bounded list payloads."""
import json
import math
import re
from functools import lru_cache
from . import cover_cache, db, settings
from .security import fail

ALIASES = {'f': 'female', 'm': 'male', 'a': 'artist', 'p': 'parody', 'c': 'character', 'l': 'language',
           'g': 'group', 'o': 'other', 'cos': 'cosplayer', 'x': 'mixed', 'r': 'reclass'}
FIELDS = {'title', 'uploader', 'category', 'gid', 'tag'}
LIST_FIELDS = ('gid', 'title', 'title_jpn', 'thumb', 'category', 'filecount', 'posted', 'rating', 'favCategory')
# Keep source and overrides separate; apply the same merge and visibility rules
# inside SQLite before ANY filtering, counts, ordering or LIMIT/OFFSET.
VISIBLE = """WITH effective AS MATERIALIZED (
 SELECT g.gid,g.position,CASE WHEN p.data IS NULL THEN g.data ELSE json_patch(g.data,p.data) END AS data
 FROM galleries g LEFT JOIN gallery_overrides p ON p.gid=g.gid
), visible AS MATERIALIZED (
 SELECT * FROM effective WHERE COALESCE(json_extract(data,'$.hidden'),0)=0
)"""


HOME_VISIBLE = VISIBLE.replace(
    "\n), visible AS MATERIALIZED",
    """
 UNION ALL
 SELECT 'local-' || id, -rowid,
        json_set(data,'$.gid','local-' || id,'$.hidden',json(json_extract(data,'$.published') IS NOT 1))
 FROM manual_galleries
), visible AS MATERIALIZED""",
)


def source_link(value):
    return re.fullmatch(r'https://(?:e-hentai|exhentai)\.org/g/([1-9][0-9]{0,14})/([a-zA-Z0-9]{1,40})/?', value)


def gallery_lookup(query):
    value = query.strip()
    if re.fullmatch(r'[0-9]+|local-[a-f0-9]{32}', value):
        return value
    link = re.fullmatch(r'https?://(?:e-hentai|exhentai)\.org/g/([0-9]+)/[a-zA-Z0-9]+/?(?:[?#].*)?', value, re.I)
    return link[1] if link else None


def parse_query(query, extra_fields=()):
    tokens, buffer, quoted = [], '', False
    for ch in query:
        if ch == '"':
            quoted = not quoted
        elif not quoted and ch in (' ', ','):
            if buffer:
                tokens.append(buffer)
                buffer = ''
        else:
            buffer += ch
    if buffer:
        tokens.append(buffer)
    terms = []
    lookup = gallery_lookup(query) if not extra_fields else None
    for raw in tokens:
        raw = raw.strip()
        mode = 'exclude' if raw.startswith('-') else 'or' if raw.startswith('~') else 'include'
        if mode != 'include':
            raw = raw[1:]
        raw = raw.replace('_', ' ').strip()
        exact = raw.endswith('$')
        if exact:
            raw = raw[:-1]
        wildcard = raw.endswith(('*', '%'))
        if wildcard:
            raw = raw[:-1]
        field, namespace, value = 'any', None, raw
        if ':' in raw:
            # Match the existing frontend tokenizer's split(':', 2) semantics.
            prefix, value = raw.split(':')[:2]
            prefix = prefix.lower()
            if prefix in FIELDS or prefix in extra_fields:
                field = prefix
            else:
                field, namespace = 'tag', ALIASES.get(prefix, prefix)
        if lookup is not None:
            field, namespace, value = 'gid', None, lookup
        value = value.strip().lower()
        if value:
            terms.append({'field': field, 'namespace': namespace, 'value': value,
                          'wildcard': wildcard, 'exact': exact, 'mode': mode})
    if len(terms) > 40:
        fail(400, '搜索条件最多 40 个')
    return terms


SORTS = {
    'default': 'position',
    'posted_desc': "CAST(COALESCE(json_extract(data,'$.posted'),0) AS INTEGER) DESC, position",
    'posted_asc': "CAST(COALESCE(json_extract(data,'$.posted'),0) AS INTEGER) ASC, position",
    'rating_desc': "CAST(COALESCE(json_extract(data,'$.rating'),0) AS REAL) DESC, position",
    'pages_desc': "CAST(COALESCE(json_extract(data,'$.filecount'),0) AS INTEGER) DESC, position",
    'pages_asc': "CAST(COALESCE(json_extract(data,'$.filecount'),0) AS INTEGER) ASC, position",
}


def sync_tag_index(con, gid, tags):
    con.execute('DELETE FROM gallery_tags WHERE gid=?', (gid,))
    rows = []
    seen = set()
    for raw in tags or ():
        if not isinstance(raw, str):
            continue
        lower = raw.lower()
        if lower in seen:
            continue
        seen.add(lower)
        ns, val = lower.split(':', 1) if ':' in lower else ('', lower)
        rows.append((gid, lower, ns, val))
    if rows:
        con.executemany('INSERT OR IGNORE INTO gallery_tags(gid,tag,ns,val) VALUES (?,?,?,?)', rows)


def rebuild_tag_index(con):
    con.execute('DELETE FROM gallery_tags')
    rows = con.execute("""SELECT g.gid, CASE WHEN p.data IS NULL THEN g.data ELSE json_patch(g.data,p.data) END AS data
        FROM galleries g LEFT JOIN gallery_overrides p ON p.gid=g.gid
        UNION ALL
        SELECT 'local-' || id AS gid, data FROM manual_galleries""").fetchall()
    batch = []
    for row in rows:
        data = json.loads(row['data'])
        seen = set()
        for raw in data.get('tags') or ():
            if not isinstance(raw, str):
                continue
            lower = raw.lower()
            if lower in seen:
                continue
            seen.add(lower)
            ns, val = lower.split(':', 1) if ':' in lower else ('', lower)
            batch.append((row['gid'], lower, ns, val))
    if batch:
        con.executemany('INSERT OR IGNORE INTO gallery_tags(gid,tag,ns,val) VALUES (?,?,?,?)', batch)


def term_sql(term):
    value, wildcard = term['value'], term['wildcard']
    def text(column):
        expr = f"unicode_lower(COALESCE(json_extract(data, '$.{column}'), ''))"
        return (f'substr({expr},1,length(?))=?', [value, value]) if wildcard else (f'instr({expr},?)>0', [value])
    def tags():
        ns = term['namespace']
        if ns:
            prefix, params, expr = 'gt.ns=? AND ', [ns], 'gt.val'
        else:
            prefix, params = '', []
            expr = 'gt.val' if term['exact'] or wildcard else 'gt.tag'
        if term['exact']:
            match, args = f'{expr}=?', params + [value]
        elif wildcard:
            match, args = f'substr({expr},1,length(?))=?', params + [value, value]
        else:
            match, args = f'instr({expr},?)>0', params + [value]
        return f'EXISTS (SELECT 1 FROM gallery_tags gt WHERE gt.gid=visible.gid AND {prefix}{match})', args
    field = term['field']
    if field == 'gid':
        return 'gid=?', [value]
    if field == 'tag':
        return tags()
    columns = ('title', 'title_jpn') if field == 'title' else (field,) if field != 'any' else ('title', 'title_jpn', 'uploader', 'category')
    parts = [text(column) for column in columns]
    if field == 'any':
        parts.append(tags())
    return '(' + ' OR '.join(p[0] for p in parts) + ')', [v for p in parts for v in p[1]]


def filter_sql(query, extra_fields=(), matcher=None):
    groups = {'include': [], 'exclude': [], 'or': []}
    for term in parse_query(query, extra_fields):
        groups[term['mode']].append((matcher or term_sql)(term))
    clauses, params = [], []
    for expr, args in groups['include']:
        clauses.append(expr)
        params.extend(args)
    for expr, args in groups['exclude']:
        clauses.append(f'NOT ({expr})')
        params.extend(args)
    if groups['or']:
        clauses.append('(' + ' OR '.join(p[0] for p in groups['or']) + ')')
        params.extend(v for p in groups['or'] for v in p[1])
    return ' AND '.join(clauses) or '1', params


def translation_index(serialized):
    return {f'{group["namespace"]}:{value}': {'namespace': group['namespace'], 'value': value, **detail}
            for group in json.loads(serialized).get('data', []) for value, detail in group.get('data', {}).items()}


def list_tag_labels(tags, index):
    return [index.get(tag, {}).get('name') or tag.split(':', 1)[-1] for tag in tags]


_translation_cache = {}


def translations(con):
    # A translated dictionary is several MB. Use the transaction's revision
    # before reading it, so ordinary detail/list requests only fetch a small key.
    key = (str(settings.DB_PATH), db.snapshot(con, 'catalog-revision'))
    cached = _translation_cache.get(key)
    if cached is not None:
        return cached
    row = con.execute("SELECT data FROM snapshots WHERE name='translations'").fetchone()
    index = translation_index(row[0]) if row else {}
    _translation_cache[key] = index
    if len(_translation_cache) > 4:
        _translation_cache.pop(next(iter(_translation_cache)))
    return index


def list_galleries(query='', types='', page=1, per_page=30, sort='default', fav=''):
    # Each process checks a shared revision. Source sync, overrides and tag
    # translations bump it in the SAME write transaction as their data.
    with db.connect() as con:
        revision = db.snapshot(con, 'catalog-revision')
        result = cached_page(str(settings.DB_PATH), revision, query, types, page, per_page, sort or 'default', fav or '')
        items = [dict(item) for item in result['items']]
        cover_cache.prefer(con, items)
    return dict(result, items=items)


@lru_cache(maxsize=64)
def cached_page(database_path, revision, query, types, page, per_page, sort='default', fav=''):
    if len(query) > 2000 or len(types) > 1000 or len(fav) > 200:
        fail(400, '搜索条件过长')
    if sort not in SORTS:
        fail(400, '排序方式不正确')
    condition, params = filter_sql(query)
    categories = list(dict.fromkeys(t for t in types.split(',') if t))
    if len(categories) > 30:
        fail(400, '分类条件过多')
    with db.connect() as con:
        con.execute('PRAGMA temp_store=MEMORY')
        con.create_function('unicode_lower', 1, lambda v: str(v).lower(), deterministic=True)
        con.execute('BEGIN')
        matched = HOME_VISIBLE + f', matched AS MATERIALIZED (SELECT * FROM visible WHERE {condition})'
        selected_parts = []
        selected_params = []
        if categories:
            selected_parts.append("json_extract(data,'$.category') IN (" + ','.join('?' for _ in categories) + ')')
            selected_params.extend(categories)
        if fav:
            selected_parts.append("json_extract(data,'$.favCategory')=?")
            selected_params.append(fav)
        selected = ' AND '.join(selected_parts) or '1'
        order_by = SORTS[sort]
        sql = matched + f''', selected AS MATERIALIZED (SELECT * FROM matched WHERE {selected}),
        totals AS (SELECT COUNT(*) AS n FROM selected),
        paged AS (SELECT data FROM selected ORDER BY {order_by} LIMIT ?
                  OFFSET min(?, ((SELECT max(n-1,0) FROM totals) / ?) * ?))
        SELECT
          (SELECT json_group_object(category,n) FROM (
            SELECT COALESCE(json_extract(data,'$.category'),'') AS category,COUNT(*) AS n FROM visible GROUP BY category)) AS counts,
          (SELECT json_group_object(category,n) FROM (
            SELECT COALESCE(json_extract(data,'$.category'),'') AS category,COUNT(*) AS n FROM matched GROUP BY category)) AS matched_counts,
          (SELECT json_group_object(fav,n) FROM (
            SELECT json_extract(data,'$.favCategory') AS fav,COUNT(*) AS n FROM visible WHERE fav IS NOT NULL AND fav!='' GROUP BY fav)) AS fav_counts,
          (SELECT n FROM totals) AS total,
          (SELECT json_group_array(json(data)) FROM paged) AS items
        '''
        row = con.execute(sql, params + selected_params + [per_page, (page-1)*per_page, per_page, per_page]).fetchone()
        counts, category_counts, fav_counts, total = json.loads(row['counts']), json.loads(row['matched_counts']), json.loads(row['fav_counts']), row['total']
        page = min(page, max(1, math.ceil(total / per_page)))
        rows = json.loads(row['items'])
        index = translations(con) if rows else {}
        items = []
        for gallery in rows:
            item = {k: gallery.get(k) for k in LIST_FIELDS}
            tags = [tag for tag in gallery.get('tags', []) if isinstance(tag, str) and ':' in tag][:8]
            item['tagLabels'] = list_tag_labels(tags, index)
            items.append(item)
        return {'items': items, 'total': total, 'totalAll': sum(counts.values()), 'page': page, 'perPage': per_page,
                'categoryCounts': category_counts, 'totalCategoryCounts': counts, 'favCounts': fav_counts}


def suggest_tags(token):
    if len(token) > 2000:
        fail(400, '标签搜索过长')
    token = token.strip().lower()
    if len(token) < 2 or '$' in token or token.startswith(('-', '~')):
        return {'items': []}
    prefix=token.split(':',1)[0] if ':' in token else None
    if prefix in FIELDS-{'tag'}:return {'items':[]}
    namespace=ALIASES.get(prefix,prefix) if prefix and prefix!='tag' else None
    needle = (token.split(':',1)[1] if ':' in token else token).strip('"')
    if not needle:
        return {'items': []}
    with db.connect() as con:
        index = translations(con)
    results = []
    for tag, detail in index.items():
        value, ns, cn = detail['value'].lower(), detail['namespace'].lower(), detail.get('name', '').lower()
        if namespace and ns!=namespace:continue
        score = 0 if value == needle else 1 if value.startswith(needle) else 2 if cn.startswith(needle) else 3 if ns.startswith(needle) else 4 if needle in value else 5 if needle in cn else -1
        if score >= 0:
            results.append({'tag': tag, 'namespace': detail['namespace'], 'value': detail['value'], 'tag_cn': detail.get('name', ''), 'score': score})
    return {'items': sorted(results, key=lambda d: (d['score'], d['namespace'], d['value']))[:8]}


def gallery_detail(gid, source='favorites'):
    manual = re.fullmatch(r'local-([a-f0-9]{32})', gid)
    if not manual and not re.fullmatch(r'[1-9][0-9]{0,14}', gid):
        fail(400, '画廊 ID 不正确')
    with db.connect() as con:
        con.execute('BEGIN')
        if manual:
            row = con.execute('SELECT data FROM manual_galleries WHERE id=?', (manual[1],)).fetchone()
            gallery = json.loads(row[0]) if row else {}
            if source == 'daily' or not gallery.get('published'):
                fail(404, '未找到此画廊')
            gallery.update(gid=gid)
            linked = gallery.get('linkedGid')
            if linked:
                row = con.execute('SELECT data FROM galleries WHERE gid=?', (linked,)).fetchone()
                if row:
                    gallery['token'] = json.loads(row[0]).get('token')
            if gallery.get('sourceUrl'):
                link = source_link(gallery['sourceUrl'])
                gallery.update(linkedGid=link[1], token=link[2])
        else:
            patch = con.execute('SELECT data FROM gallery_overrides WHERE gid=?', (gid,)).fetchone()
            row = con.execute('SELECT data FROM galleries WHERE gid=?', (gid,)).fetchone() if source != 'daily' else None
            gallery = json.loads(row[0]) if row else next(
                (g for group in db.snapshot(con, 'daily', []) for g in group.get('galleries', []) if str(g.get('gid')) == gid), None)
            if gallery is None:
                fail(404, '未找到此画廊')
            gallery = dict(gallery, **(json.loads(patch[0]) if patch else {}))
            if gallery.get('hidden'):
                fail(404, '未找到此画廊')
        cover_cache.prefer(con, [gallery])
        index = translations(con)
        details = []
        for tag in gallery.get('tags', []):
            if not isinstance(tag, str) or ':' not in tag:
                continue
            namespace, value = tag.split(':', 1)
            detail = index.get(tag, {})
            details.append({'tag': tag, 'namespace': namespace, 'value': value, 'tag_cn': detail.get('name', ''),
                            'intro': detail.get('intro', ''), 'links': detail.get('links', '')})
        return {'gallery': gallery, 'tagDetails': details}


def tags_page(namespace='all', query='', page=1):
    with db.connect() as con:
        revision = db.snapshot(con, 'catalog-revision')
    return cached_tags(str(settings.DB_PATH), revision, namespace, query.lower().strip(), page)


@lru_cache(maxsize=32)
def cached_tags(database_path, revision, namespace, query, page):
    from collections import Counter
    with db.connect() as con:
        con.execute('PRAGMA temp_store=MEMORY')
        con.execute('BEGIN')
        index = translations(con)
        freq = dict(con.execute(VISIBLE + " SELECT t.value,COUNT(*) FROM visible,json_each(json_extract(data,'$.tags')) t GROUP BY t.value"))
    counts = Counter()
    items = []
    for tag, detail in index.items():
        ns = detail['namespace']
        if ns in ('rows','reclass'):
            continue
        counts[ns] += 1
        if namespace != 'all' and namespace != ns:
            continue
        if query and query not in detail['value'].lower() and query not in detail.get('name','').lower():
            continue
        items.append({'ns':ns,'key':detail['value'],'name':detail.get('name',''),'intro':detail.get('intro',''),'freq':freq.get(tag,0)})
    items.sort(key=lambda item:(-item['freq'],item['key']))
    total = len(items)
    page = min(page, max(1,math.ceil(total/200)))
    return {'items':items[(page-1)*200:page*200],'page':page,'total':total,'namespaces':list(counts), 'counts':{'all':sum(counts.values()),**counts}}
