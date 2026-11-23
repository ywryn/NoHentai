"""Versioned record-level editing and recoverable audit history."""
import json
import math
import re
import uuid
from fastapi import HTTPException
from . import cover_cache, db, catalog
from .security import fail
from .validation import text, validate
from app.daily_config import without_display_labels

TABLES = {'gallery': 'gallery_overrides', 'manual': 'manual_galleries', 'book': 'books', 'daily': 'daily_rules'}
RESOURCES = {'gallery': 'overrides', 'manual': 'overrides', 'book': 'printed', 'daily': 'daily'}


def check_kind(kind):
    if not isinstance(kind, str) or kind not in TABLES:
        fail(400, '不允许的记录类型')


def key_field(kind):
    return 'gid' if kind == 'gallery' else 'id'


def row(con, kind, record_id):
    return con.execute(f'SELECT * FROM {TABLES[kind]} WHERE {key_field(kind)}=?', (record_id,)).fetchone()


def dto(r, kind=None):
    data = json.loads(r['data'])
    if kind == 'daily':
        data = without_display_labels(data)
    return {'id': r['id'], 'position': r['position'], 'data': data, 'version': r['version'], 'updatedAt': r['updated_at']}


def gallery_dto_data(gid, original, patch, version, updated_at, index):
    if original is None and patch is None:
        fail(404, '画廊不存在')
    source = json.loads(original) if original is not None else {'gid': gid}
    data = json.loads(patch) if patch is not None else {}
    effective = dict(source, **data)
    tag_names = {tag: index.get(tag,{}).get('name','') for tag in effective.get('tags',[])}
    return {'tagNames':tag_names, 'id': gid, 'source': source, 'data': data, 'effective': effective,
            'version': version or '0', 'updatedAt': updated_at}


def gallery_dto(con, gid, index=None):
    original = con.execute('SELECT data FROM galleries WHERE gid=?', (gid,)).fetchone()
    patch = row(con, 'gallery', gid)
    if index is None:index = catalog.translations(con)
    return gallery_dto_data(gid, original[0] if original else None, patch['data'] if patch else None,
                            patch['version'] if patch else None, patch['updated_at'] if patch else None, index)


def manual_dto(con, found, index):
    if not found:
        fail(404, '记录不存在，可能已被删除')
    record_id = found['id']
    data = json.loads(found['data'])
    linked = data.get('linkedGid')
    return {'id': record_id, 'origin': 'manual', 'source': {}, 'data': data,
            'effective': dict(data, gid='local-' + record_id),
            'tagNames': {tag: index.get(tag, {}).get('name', '') for tag in data.get('tags', [])},
            'duplicate': bool(linked and con.execute('SELECT 1 FROM galleries WHERE gid=?', (linked,)).fetchone()),
            'version': found['version'], 'updatedAt': found['updated_at']}


def load(kind, record_id):
    check_kind(kind)
    with db.connect() as con:
        con.execute('BEGIN')
        if kind == 'gallery':
            result = gallery_dto(con, record_id)
            cover_cache.prefer(con, [result['effective']])
            return result
        if kind == 'manual':
            return manual_dto(con, row(con, kind, record_id), catalog.translations(con))
        found = row(con, kind, record_id)
        if not found:
            fail(404, '记录不存在，可能已被删除')
        result=dto(found,kind)
        if kind=='book' and found['gallery_gid']:
            try: result['gallery']=gallery_dto(con,found['gallery_gid'])['effective']
            except HTTPException as exc:
                if exc.status_code!=404:raise
                result['gallery']=None
        return result


BOOK_FIELDS = ('id', 'name', 'jpname', 'sid')


def book_term_sql(term):
    value = term['value']
    def book_text(key, exact=False, wildcard=True):
        expr = f"unicode_lower(COALESCE(json_extract(books.data,'$.{key}'),''))"
        if exact:
            return f'{expr}=?', [value]
        if wildcard and term['wildcard']:
            return f'substr({expr},1,length(?))=?', [value, value]
        return f'instr({expr},?)>0', [value]
    def gallery():
        condition, params = catalog.term_sql(term)
        return """EXISTS(SELECT 1 FROM (
            SELECT g.gid,CASE WHEN p.data IS NULL THEN g.data ELSE json_patch(g.data,p.data) END AS data
            FROM galleries g LEFT JOIN gallery_overrides p ON p.gid=g.gid
            WHERE g.gid=json_extract(books.data,'$.sid')
        ) linked WHERE """ + condition + ')', params
    field = term['field']
    if field == 'id': return book_text('ID', wildcard=False)
    if field == 'name': return book_text('书名')
    if field == 'jpname': return book_text('日文名')
    if field == 'sid': return book_text('sid', exact=True)
    if field != 'any': return gallery()
    parts = [book_text(key) for key in ('ID','书名','日文名','备注','收价','原价')] + [gallery()]
    return '(' + ' OR '.join(part[0] for part in parts) + ')', [value for part in parts for value in part[1]]


def list_records(kind, query='', page=1, origin='sync'):
    check_kind(kind)
    if origin not in ('all', 'sync', 'manual'):
        fail(400, '来源筛选不正确')
    page = max(1, min(10000, int(page)))
    if len(query) > 2000:
        fail(400, '搜索内容过长')
    with db.connect() as con:
        con.create_function('unicode_lower', 1, lambda v: str(v).lower(), deterministic=True)
        con.execute('PRAGMA temp_store=MEMORY')
        con.execute('BEGIN')
        if kind in ('gallery', 'manual'):
            if kind == 'manual':
                origin = 'manual'
            scope = {'all': '1', 'manual': "gid GLOB 'local-*'", 'sync': "gid NOT GLOB 'local-*'"}[origin]
            condition, params = catalog.filter_sql(query)
            cte = catalog.HOME_VISIBLE.replace("COALESCE(json_extract(data,'$.hidden'),0)=0", '1')
            match = cte + f' SELECT gid FROM visible WHERE {scope} AND ({condition})'
            total = con.execute(f'SELECT COUNT(*) FROM ({match})', params).fetchone()[0]
            page = min(page, max(1, math.ceil(total / 30)))
            ids = [r[0] for r in con.execute(match + ' ORDER BY position,gid LIMIT 30 OFFSET ?', params + [(page-1)*30])]
            index = catalog.translations(con)
            items = [manual_dto(con, row(con, 'manual', gid[6:]), index) if gid.startswith('local-')
                     else gallery_dto(con, gid, index) for gid in ids]
            cover_cache.prefer(con, [item['effective'] for item in items])
        else:
            if kind == 'book':
                condition, params = catalog.filter_sql(query, BOOK_FIELDS, book_term_sql)
            else:
                condition = "EXISTS(SELECT 1 FROM json_each(data) v WHERE instr(unicode_lower(CAST(v.value AS TEXT)),?)>0)" if query else '1'
                params = [query.lower()] if query else []
            total = con.execute(f'SELECT COUNT(*) FROM {TABLES[kind]} WHERE {condition}', params).fetchone()[0]
            page = min(page, max(1, math.ceil(total / 30)))
            order = 'DESC' if kind == 'book' else 'ASC'
            items = [dto(r,kind) for r in con.execute(f'SELECT * FROM {TABLES[kind]} WHERE {condition} ORDER BY position {order} LIMIT 30 OFFSET ?', params + [(page-1)*30])]
        if kind=='book':
            gids = list({item['data'].get('sid') for item in items if item['data'].get('sid')})
            linked = {}
            if gids:
                placeholders = ','.join('?' for _ in gids)
                linked = {r['gid']: r for r in con.execute(f'''SELECT g.gid,g.data AS source_data,p.data AS patch_data
                    FROM galleries g LEFT JOIN gallery_overrides p ON p.gid=g.gid WHERE g.gid IN ({placeholders})''', gids)}
            for item in items:
                gid=item['data'].get('sid')
                source=linked.get(gid)
                item['gallery']=dict(json.loads(source['source_data']),**(json.loads(source['patch_data']) if source['patch_data'] else {})) if source else None
        return {'items': items, 'total': total, 'page': page, 'pages': max(1, math.ceil(total/30))}


def audit(con, kind, record_id, version, before, after, message):
    fields = set(before or {}) | set(after or {})
    changes = {k: {'before': (before or {}).get(k), 'after': (after or {}).get(k)} for k in sorted(fields)
               if (before or {}).get(k) != (after or {}).get(k) or ((k in (before or {})) != (k in (after or {})))}
    return con.execute('INSERT INTO record_history(kind,record_id,version,before_json,after_json,changes_json,created_at,message) VALUES (?,?,?,?,?,?,?,?)',
        (kind, record_id, version, db.dumps(before) if before is not None else None, db.dumps(after) if after is not None else None,
         db.dumps(changes), db.now(), message)).lastrowid


def validate_manual(data):
    extra = {'description', 'linkedGid', 'sourceUrl', 'published'}
    if not isinstance(data, dict):
        fail(400, '首页图书格式不正确')
    normalized = dict(data)
    for key in ('title', 'title_jpn', 'description', 'linkedGid', 'sourceUrl'):
        value = normalized.get(key, '')
        if not text(value, 5000 if key == 'description' else 500):
            fail(400, '首页图书文字格式不正确')
        normalized[key] = value.strip()
    if not normalized['title'] and not normalized['title_jpn']:
        fail(400, '请输入图书标题')
    if not normalized.get('category'):
        fail(400, '请选择图书分类')
    if not normalized.get('thumb'):
        normalized.pop('thumb', None)
    validate('overrides', {'1': {k: v for k, v in normalized.items() if k not in extra and k != 'hidden'}})
    if 'hidden' in normalized or type(normalized.get('published', False)) is not bool:
        fail(400, '公开状态不正确')
    normalized.setdefault('published', False)
    link = catalog.source_link(normalized['sourceUrl']) if normalized['sourceUrl'] else None
    if normalized['sourceUrl'] and not link:
        fail(400, '请输入有效的 E 站画廊链接')
    if link:
        normalized['linkedGid'] = link[1]
    if normalized['linkedGid'] and not re.fullmatch(r'[1-9][0-9]{0,14}', normalized['linkedGid']):
        fail(400, '关联画廊 ID 不正确')
    return normalized


def write(con, kind, record_id, expected, data, delete=False, message='保存条目'):
    check_kind(kind)
    if kind != 'gallery' and record_id is not None and (not isinstance(record_id, str) or not re.fullmatch(r'[a-f0-9]{32}', record_id)):
        fail(400, '记录 ID 不正确')
    current = row(con, kind, record_id) if record_id else None
    actual = current['version'] if current else '0'
    if expected != actual:
        fail(409, '该条目已更新，请导出草稿后重新加载并合并')
    before = json.loads(current['data']) if current else None
    if kind == 'daily' and before is not None:
        before = without_display_labels(before)
    warnings = []
    if kind == 'gallery':
        if not re.fullmatch(r'[1-9][0-9]{0,14}', record_id or ''):
            fail(400, '画廊 ID 不正确')
        if not current and not con.execute('SELECT 1 FROM galleries WHERE gid=?', (record_id,)).fetchone():
            fail(400, '不能为不存在的画廊新增覆盖')
        data = validate('overrides', {record_id: {} if delete else data})[record_id]
        if data.get('thumb') and not con.execute('SELECT 1 FROM media WHERE filename=?',(data['thumb'].split('/')[-1],)).fetchone():
            fail(400,'覆盖封面不存在，请先上传')
        delete = False  # Versioned tombstone keeps resetting safe across concurrent editors.
    elif kind == 'manual':
        if not delete:
            data = validate_manual(data)
            if data.get('thumb') and not con.execute('SELECT 1 FROM media WHERE filename=?', (data['thumb'].split('/')[-1],)).fetchone():
                fail(400, '封面不存在，请先上传')
            if data.get('linkedGid') and con.execute('SELECT 1 FROM galleries WHERE gid=?', (data['linkedGid'],)).fetchone():
                warnings.append('此画廊也在 E 站同步条目中，请核对是否重复展示')
    elif not delete:
        data = validate('printed', [data])[0] if kind == 'book' else validate('daily', [data])[0]
        if kind == 'book' and data['sid'] and not con.execute('SELECT 1 FROM galleries WHERE gid=?', (data['sid'],)).fetchone():
            if not before or before.get('sid') != data['sid']:
                fail(400, '新增关联的画廊 ID 不在收藏数据中')
            warnings.append('保留已有的站外画廊关联')
        if kind == 'daily':
            if con.execute("SELECT 1 FROM daily_rules WHERE json_extract(data,'$.name')=? AND id!=?", (data['name'], record_id or '')).fetchone():
                fail(400, '每日分组名称不能重复')
            if not current and con.execute('SELECT COUNT(*) FROM daily_rules').fetchone()[0] >= 20:
                fail(400, '每日分组最多 20 个')
    if delete and not current:
        fail(404, '记录已经不存在')
    if delete and kind == 'daily' and con.execute('SELECT COUNT(*) FROM daily_rules').fetchone()[0] <= 1:
        fail(400, '至少保留一个每日分组；暂停执行请关闭调度')
    if not delete and (current or kind=='gallery'):
        def comparable(value):
            result=dict(value or {})
            if kind=='gallery' and 'tags' in result:result['tags']=sorted(set(result['tags']))
            return result
        if comparable(before)==comparable(data):
            return {'id':record_id,'version':actual,'historyId':None,'warnings':warnings,'deleted':False,'unchanged':True}
    record_id = record_id or uuid.uuid4().hex
    version = uuid.uuid4().hex
    if delete:
        con.execute(f'DELETE FROM {TABLES[kind]} WHERE {key_field(kind)}=?', (record_id,))
    elif kind == 'gallery':
        con.execute('INSERT OR REPLACE INTO gallery_overrides VALUES (?,?,?,?)', (record_id, db.dumps(data), version, db.now()))
    elif kind == 'manual':
        con.execute('INSERT INTO manual_galleries VALUES (?,?,?,?) ON CONFLICT(id) DO UPDATE SET data=excluded.data,version=excluded.version,updated_at=excluded.updated_at', (record_id, db.dumps(data), version, db.now()))
    else:
        position = current['position'] if current else con.execute(f'SELECT COALESCE(MAX(position),-1)+1 FROM {TABLES[kind]}').fetchone()[0]
        if kind == 'book':
            con.execute('INSERT OR REPLACE INTO books VALUES (?,?,?,?,?,?)', (record_id, position, db.dumps(data), data['sid'] or None, version, db.now()))
        else:
            con.execute('INSERT OR REPLACE INTO daily_rules VALUES (?,?,?,?,?)', (record_id, position, db.dumps(data), version, db.now()))
    if not con.execute('SELECT 1 FROM record_history WHERE kind=? AND record_id=?', (kind,record_id)).fetchone() and (current or kind=='gallery'):
        audit(con,kind,record_id,actual,None,before or {},'编辑前版本')
    audit_id = audit(con, kind, record_id, version, before, None if delete else data, message)
    db.bump_resource(con, RESOURCES[kind])
    return {'id': record_id, 'version': version, 'historyId': audit_id, 'warnings': warnings, 'deleted': delete}


def save(kind, record_id, version, data, delete=False):
    with db.connect() as con:
        con.execute('BEGIN IMMEDIATE')
        return write(con, kind, record_id, version, data, delete)


def history_page(con, source, params, page, focus_id=None):
    if type(page) is not int or page < 1:
        fail(400, '修改记录分页参数不正确')
    size = 20
    con.execute('BEGIN')
    total = con.execute('SELECT COUNT(*) ' + source, params).fetchone()[0]
    pages = max(1, (total + size - 1) // size)
    if focus_id is not None:
        newer = con.execute('SELECT COUNT(*) ' + source + ' AND id > ?', (*params, focus_id)).fetchone()[0]
        page = newer // size + 1
    page = min(page, pages)
    rows = con.execute('SELECT * ' + source + ' ORDER BY id DESC LIMIT ? OFFSET ?',
                       (*params, size, (page - 1) * size)).fetchall()
    return rows, {'page': page, 'pages': pages, 'total': total}


def history(kind=None, record_id=None, page=None, focus_id=None):
    where, params = [], []
    if kind:
        check_kind(kind)
        where.append('kind=?'); params.append(kind)
    if record_id:
        where.append('record_id=?'); params.append(record_id)
    if focus_id is not None and (not kind or not record_id or type(focus_id) is not int or not 0 < focus_id < 2**63):
        fail(400, '修改记录定位参数不正确')
    source = 'FROM record_history' + (' WHERE ' + ' AND '.join(where) if where else '')
    with db.connect() as con:
        if page is None:
            rows = con.execute('SELECT * ' + source + ' ORDER BY id DESC LIMIT 100', params).fetchall()
            pagination = {}
        else:
            rows, pagination = history_page(con, source, params, page, focus_id)
        return {**pagination, 'items': [{'id': r['id'], 'kind': r['kind'], 'recordId': r['record_id'], 'version': r['version'], 'before': json.loads(r['before_json']) if r['before_json'] else None,
                          'after': json.loads(r['after_json']) if r['after_json'] else None, 'changes': json.loads(r['changes_json']), 'date': r['created_at'], 'message': r['message']} for r in rows]}


def restore(history_id, expected):
    with db.connect() as con:
        con.execute('BEGIN IMMEDIATE')
        entry = con.execute('SELECT * FROM record_history WHERE id=?', (history_id,)).fetchone()
        if not entry:
            fail(404, '历史记录不存在')
        # Deletion entries restore the before image; other entries restore after.
        text = entry['after_json'] or entry['before_json']
        if text is None:
            fail(400, '此记录没有可恢复的内容')
        return write(con, entry['kind'], entry['record_id'], expected, json.loads(text), message=f'恢复历史 #{history_id}')


def reorder(kind, record_id, direction, expected):
    if kind not in ('book', 'daily') or direction not in (-1, 1):
        fail(400, '排序参数不正确')
    with db.connect() as con:
        con.execute('BEGIN IMMEDIATE')
        current = row(con, kind, record_id)
        if not current or current['version'] != expected:
            fail(409, '条目已变更，请刷新后重试')
        position_direction = -direction if kind == 'book' else direction
        op, order = ('<', 'DESC') if position_direction < 0 else ('>', 'ASC')
        neighbor = con.execute(f'SELECT * FROM {TABLES[kind]} WHERE position {op} ? ORDER BY position {order} LIMIT 1', (current['position'],)).fetchone()
        if neighbor:
            for item, position in [(current, neighbor['position']), (neighbor, current['position'])]:
                version = uuid.uuid4().hex
                con.execute(f'UPDATE {TABLES[kind]} SET position=?,version=?,updated_at=? WHERE id=?', (position, version, db.now(), item['id']))
                audit(con, kind, item['id'], version, json.loads(item['data']), json.loads(item['data']), '调整顺序')
            db.bump_resource(con, RESOURCES[kind])
    return {'ok': True}
