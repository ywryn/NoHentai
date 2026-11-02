import json
import time
from . import db, jobs, security, settings
from .validation import validate, merge
from .security import fail

RESOURCES = {'printed', 'overrides', 'daily', 'translate'}


def handle(body, ip):
    action, name = body.get('action'), body.get('resource')
    token = body.get('password')
    if action == 'verify':
        return {'ok': True, 'session': security.login(token, ip, body.get('remember') is True)}
    security.session(token)
    if action == 'logout':
        with db.connect() as con:
            con.execute('DELETE FROM sessions WHERE digest=?', (security.digest(token),))
        return {'ok': True}
    if action in ('load', 'save', 'history'):
        if not isinstance(name, str) or name not in RESOURCES:
            fail(400, '不允许访问此资源')
        with db.connect() as con:
            if action == 'load':
                data, version = db.resource(con, name)
                return {'data': data, 'sha': version}
            if action == 'history':
                rows = con.execute('SELECT version,message,created_at FROM history WHERE resource=? ORDER BY id DESC LIMIT 15', (name,))
                return {'commits': [{'sha': r[0], 'message': r[1], 'date': r[2]} for r in rows]}
            con.execute('BEGIN IMMEDIATE')
            current, version = db.resource(con, name)
            if not isinstance(body.get('sha'), str) or body['sha'] != version:
                fail(409, '内容已被其他操作修改，请导出草稿后重新加载')
            data = validate(name, body.get('data'))
            warnings = []
            if name in ('printed', 'overrides'):
                ids = {r[0] for r in con.execute('SELECT gid FROM galleries')}
                if name == 'printed':
                    legacy = {b['sid'] for b in current}
                    missing = [b for b in data if b['sid'] and b['sid'] not in ids]
                    if any(b['sid'] not in legacy for b in missing):
                        fail(400, '新增关联的画廊 ID 不在收藏数据中')
                    if missing:
                        warnings.append(f'保留 {len(missing)} 条已有的站外画廊关联')
                elif any(gid not in ids and gid not in current for gid in data):
                    fail(400, '新增覆盖的画廊 ID 不存在')
            version = db.put_resource(con, name, data)
            db.put_snapshot(con, 'release', {'commit': version, 'builtAt': db.now()})
            return {'sha': version, 'commit': version, 'warnings': warnings}
    if action == 'gallery-search':
        query = str(body.get('query') or '').strip().lower()[:200]
        try:
            page = max(1, min(10000, int(body.get('page') or 1)))
        except (ValueError, TypeError):
            fail(400, '分页不正确')
        with db.connect() as con:
            con.execute('BEGIN')
            source = db.galleries(con)
            patches, _ = db.resource(con, 'overrides')
        originals = {str(g['gid']): g for g in source}
        all_items = [g for g in merge(source, patches, True) if not query or any(
            query in str(v or '').lower() for v in [g['gid'], g.get('title'), g.get('title_jpn'), g.get('uploader'), *g.get('tags', [])])]
        return {'total': len(all_items), 'page': page, 'items': [
            {'gallery': g, 'source': originals[str(g['gid'])], 'override': patches.get(str(g['gid']), {})}
            for g in all_items[(page - 1) * 30:page * 30]]}
    if action == 'runs':
        return {'runs': jobs.runs()}
    if action == 'dispatch':
        return {'accepted': True, 'id': jobs.enqueue(body.get('workflow'))}
    if action == 'rerun':
        return {'accepted': True, 'id': jobs.rerun(body.get('runId'))}
    if action == 'platforms':
        return {'server': {'available': True, 'secrets': [
            {'name': name, 'configured': bool(security.credential(name))} for name in settings.SECRET_NAMES]}}
    if action == 'replace-secret':
        if body.get('platform') != 'server':
            fail(400, '仅支持服务器凭证')
        security.replace_credential(body.get('name'), body.get('value'))
        return {'ok': True, 'message': '服务器配置已保存，后续请求或任务立即使用新值'}
    if action == 'health':
        start = time.monotonic()
        with db.connect() as con:
            con.execute('SELECT 1').fetchone()
            row = con.execute("SELECT data FROM snapshots WHERE name='worker-heartbeat'").fetchone()
        alive = bool(row and time.time() - json.loads(row[0]) < 60)
        return {'checks': [
            {'name': 'Python API / SQLite', 'url': '/api/health', 'ok': True, 'status': 200, 'ms': round((time.monotonic() - start) * 1000)},
            {'name': '同步 Worker 心跳', 'url': '本机任务队列', 'ok': alive, 'status': 200 if alive else 503, 'ms': 0}]}
    fail(400, '未知管理操作')
