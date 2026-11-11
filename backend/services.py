"""Business-oriented configuration. Plain settings are distinct from secrets."""
import base64
import hashlib
import json
import os
import secrets
import time
from contextlib import contextmanager
from cryptography.fernet import Fernet
from . import db, security, settings
from .security import fail

GROUPS = {'favorites': '收藏来源', 'translate': '翻译服务', 'ocr': '文字识别'}
# key: group, label, type, default, bounds/choices
FIELDS = {
 'EXHENTAI_BASE_URL': ('favorites', '收藏页地址', 'url', 'https://exhentai.org/favorites.php', None),
 'EXHENTAI_COOKIE_MEMBER_ID': ('favorites', 'Member ID', 'secret', '', None),
 'EXHENTAI_COOKIE_PASS_HASH': ('favorites', 'Pass Hash', 'secret', '', None),
 'EXHENTAI_COOKIE_IGNEOUS': ('favorites', 'Igneous', 'secret', '', None),
 'MAX_RETRIES': ('favorites', '元数据重试次数', 'number', 5, (0, 10)),
 'RETRY_DELAY_SECONDS': ('favorites', '重试间隔（秒）', 'number', 2, (0, 60)),
 'LLM_API_BASE': ('translate', 'API 地址（含 /v1）', 'url', '', None),
 'LLM_API_KEY': ('translate', 'API Key', 'secret', '', None),
 'model': ('translate', '模型', 'text', None, None),
 'jsonMode': ('translate', 'JSON 输出模式', 'select', None, [None, True, False]),
 'TRANS_PASSWORD': ('translate', '工作台密码', 'secret', '', None),
 'LLM_TIMEOUT_SECONDS': ('translate', '请求超时（秒）', 'number', 90, (10, 150)),
 'LLM_CONCURRENCY': ('translate', '同时执行的翻译请求', 'number', 2, (1, 8)),
 'defaultOcr': ('ocr', '默认识别服务', 'select', 'google', ['google', 'paddle', 'ocrspace']),
 'GOOGLE_VISION_API_KEY': ('ocr', 'Google Vision API Key', 'secret', '', None),
 'PADDLEOCR_API_TOKEN': ('ocr', 'PaddleOCR Token', 'secret', '', None),
 'OCR_SPACE_KEY': ('ocr', 'OCR.Space API Key', 'secret', '', None),
 'VISION_MONTHLY_LIMIT': ('ocr', 'Vision 每月调用上限', 'number', 1000, (0, 100000)),
 'OCR_CONCURRENCY': ('ocr', '同时执行的识别请求', 'number', 2, (1, 8)),
}


def version(con, group):
    row = con.execute('SELECT version FROM service_versions WHERE name=?', (group,)).fetchone()
    config = db.resource(con, 'translate')[0] if group in ('translate','ocr') else {}
    related = {key:config[key] for key in (('model','jsonMode') if group=='translate' else ('defaultOcr',)) if key in config}
    effective = {name: security.credential(name, con) for name,field in FIELDS.items() if field[0]==group and name in settings.BUSINESS_NAMES}
    if group=='translate':
        effective['LLM_MODEL']=security.credential('LLM_MODEL',con) or 'gpt-4o-mini'
        effective['LLM_JSON_MODE']=security.credential('LLM_JSON_MODE',con)
    return hashlib.sha256(((row[0] if row else '') + db.dumps(related) + db.dumps(effective)).encode()).hexdigest()


def status():
    with db.connect() as con:
        con.execute('BEGIN')
        config, _ = db.resource(con, 'translate')
        groups = []
        for group, label in GROUPS.items():
            fields = []
            for name, (owner, title, field_type, default, limits) in FIELDS.items():
                if owner != group:
                    continue
                if name in config:
                    value = config[name]
                    inherited = 'LLM_MODEL' if name=='model' else 'LLM_JSON_MODE' if name=='jsonMode' else ''
                    source = 'database' if value is not None else 'environment' if inherited and os.getenv(inherited) else 'default'
                else:
                    raw = security.credential(name, con)
                    stored = con.execute('SELECT 1 FROM service_settings WHERE name=? UNION ALL SELECT 1 FROM credentials WHERE name=?', (name, name)).fetchone()
                    source = 'database' if stored else 'environment' if os.getenv(name) else 'default'
                    if field_type == 'number':
                        try: value = float(raw) if raw else default
                        except ValueError: value = default
                    else:
                        value = raw or default
                fields.append({'key': name, 'label': title, 'type': field_type, 'value': value,
                               'configured': bool(value), 'source': source, 'limits': limits,
                               'effective': (security.credential('LLM_MODEL',con) or 'gpt-4o-mini') if name=='model' and value is None else security.credential('LLM_JSON_MODE',con)=='1' if name=='jsonMode' and value is None else value})
            check = con.execute('SELECT * FROM service_checks WHERE name=?', (group,)).fetchone()
            groups.append({'id': group, 'label': label, 'version': version(con, group), 'fields': fields,
                           'check': dict(check) if check else None})
    return {'groups': groups}


def validate_value(name, value):
    owner, _, field_type, default, limits = FIELDS[name]
    if field_type == 'number':
        if type(value) not in (int, float) or not limits[0] <= value <= limits[1] or (name != 'RETRY_DELAY_SECONDS' and int(value) != value):
            fail(400, f'{name} 超出允许范围')
    elif field_type == 'select':
        if not any(type(value) is type(option) and value == option for option in limits):
            fail(400, f'{name} 选项不正确')
    elif field_type == 'secret':
        if not isinstance(value, str) or len(value) > 16000 or '\0' in value:
            fail(400, '密钥格式不正确')
        if name == 'TRANS_PASSWORD' and len(value) > security.TRANS_PASSWORD_MAX_LENGTH:
            fail(400, '工作台密码最多 1024 字符')
        if name == 'TRANS_PASSWORD' and security.verify_password(value):
            fail(400, '翻译密码不能与管理密码相同')
    else:
        if value is None and name == 'model':
            return
        if not isinstance(value, str) or len(value) > 2000 or '\0' in value:
            fail(400, f'{name} 内容不正确')
        if field_type == 'url' and value:
            from .upstream import validate_url
            validate_url(value, gallery=name == 'EXHENTAI_BASE_URL')


def save(group, expected, values, operations=None):
    if group not in GROUPS or not isinstance(values, dict) or not isinstance(operations or {}, dict):
        fail(400, '服务配置格式不正确')
    operations = operations or {}
    for name, value in values.items():
        if name not in FIELDS or FIELDS[name][0] != group:
            fail(400, '不允许修改此配置项')
        validate_value(name, value)
    for name, operation in operations.items():
        if name not in FIELDS or FIELDS[name][0] != group or operation not in ('clear', 'inherit'):
            fail(400, '配置操作不正确')
        if name in ('model','jsonMode','defaultOcr'):
            fail(400, '此项请通过参数输入框修改')
        if name in values:
            fail(400, '不能同时替换与清除同一项')
    with db.connect() as con:
        con.execute('BEGIN IMMEDIATE')
        if expected != version(con, group):
            fail(409, '服务配置已更新，请重新加载后保存')
        config, _ = db.resource(con, 'translate')
        # Preserve versions, test results and audit history for identical writes.
        changed_values={}
        for name,value in values.items():
            if name in config:
                if config[name]!=value:changed_values[name]=value
                continue
            normal=con.execute('SELECT value_json FROM service_settings WHERE name=?',(name,)).fetchone()
            secret=con.execute('SELECT ciphertext FROM credentials WHERE name=?',(name,)).fetchone()
            if FIELDS[name][2]=='secret':
                same=not normal and secret and Fernet(settings.encryption_key()).decrypt(secret[0].encode()).decode()==value
            else:
                same=normal and not secret and json.loads(normal[0])==value
            if not same:changed_values[name]=value
        changed_operations={}
        for name,operation in operations.items():
            normal=con.execute('SELECT value_json FROM service_settings WHERE name=?',(name,)).fetchone()
            secret=con.execute('SELECT ciphertext FROM credentials WHERE name=?',(name,)).fetchone()
            if operation=='inherit' and not normal and not secret:continue
            if operation=='clear':
                if FIELDS[name][2]=='secret' and not normal and secret and Fernet(settings.encryption_key()).decrypt(secret[0].encode())==b'':continue
                if FIELDS[name][2]!='secret' and normal and not secret and json.loads(normal[0])=='':continue
            changed_operations[name]=operation
        values,operations=changed_values,changed_operations
        if not values and not operations:return {'ok':True,'unchanged':True,'message':'内容未发生变化，无需保存'}
        for name, value in values.items():
            if name in config:
                config[name] = value
            elif FIELDS[name][2] == 'secret':
                con.execute('INSERT OR REPLACE INTO credentials VALUES (?,?,?)',
                            (name, Fernet(settings.encryption_key()).encrypt(value.encode()).decode(), db.now()))
            else:
                con.execute('INSERT OR REPLACE INTO service_settings VALUES (?,?,?)', (name, db.dumps(value), db.now()))
                con.execute('DELETE FROM credentials WHERE name=?', (name,))
        for name, operation in operations.items():
            con.execute('DELETE FROM credentials WHERE name=?', (name,))
            con.execute('DELETE FROM service_settings WHERE name=?', (name,))
            if operation == 'clear':
                if FIELDS[name][2] == 'secret':
                    con.execute('INSERT INTO credentials VALUES (?,?,?)', (name, Fernet(settings.encryption_key()).encrypt(b'').decode(), db.now()))
                else:
                    con.execute('INSERT INTO service_settings VALUES (?,?,?)', (name, '""', db.now()))
        if any(name in config for name in values):
            from .validation import validate
            db.put_resource(con, 'translate', validate('translate', config), '保存服务参数')
        con.execute('UPDATE service_versions SET version=? WHERE name=?', (secrets.token_hex(16), group))
        # Audit field names only. Neither old nor new secret values enter history.
        names = sorted(set(values) | set(operations))
        con.execute('INSERT INTO history(resource,version,data,created_at,message) VALUES (?,?,?,?,?)',
                    ('service:' + group, secrets.token_hex(16), db.dumps({'fields': names}), db.now(), '更新服务配置：' + '、'.join(names)))
    return {'ok': True, 'message': '配置已保存，后续请求或任务使用新值'}


def test(group):
    if group not in GROUPS:
        fail(400, '未知服务')
    with db.connect() as con:
        tested_version = version(con, group)
    ok, message = False, '连接失败，请检查地址、凭证或服务状态'
    try:
        if group == 'favorites':
            from .upstream import fetch
            content, _ = fetch(security.credential('EXHENTAI_BASE_URL') or 'https://exhentai.org/favorites.php', gallery=True)
            from bs4 import BeautifulSoup
            ok = BeautifulSoup(content, 'html.parser').select_one('table.itg') is not None
            message = '已通过收藏页访问验证' if ok else '未读取到收藏列表，请检查 Cookie 与来源访问状态'
        elif group == 'translate':
            from .translation import translate
            result = translate({'texts': ['接続テスト ' + secrets.token_hex(3)]})
            ok = bool(result.get('translations') and result['translations'][0])
            message = '翻译服务请求成功' if ok else '服务已响应，但没有返回有效译文'
        else:
            from .media_store import test_image
            from .translation import ocr
            result = ocr({'imageBase64': test_image()})
            ok = 'results' in result
            message = 'OCR 服务请求成功，使用服务：' + result.get('source', '')
    except Exception:
        pass  # Never forward URLs, response bodies, credentials or provider traces.
    with db.connect() as con:
        con.execute('INSERT OR REPLACE INTO service_checks VALUES (?,?,?,?,?)', (group, tested_version, int(ok), message, db.now()))
    return {'ok': ok, 'message': message}


@contextmanager
def slot(service):
    key = 'LLM_CONCURRENCY' if service == 'translate' else 'OCR_CONCURRENCY'
    limit = int(float(security.credential(key) or 2))
    lease = secrets.token_hex(16)
    with db.connect() as con:
        con.execute('BEGIN IMMEDIATE')
        con.execute('DELETE FROM service_leases WHERE expires<?', (time.time(),))
        if con.execute('SELECT COUNT(*) FROM service_leases WHERE service=?', (service,)).fetchone()[0] >= limit:
            fail(429, '服务正在处理其他请求，请稍后重试')
        con.execute('INSERT INTO service_leases VALUES (?,?,?)', (lease, service, time.time()+300))
    try:
        yield
    finally:
        with db.connect() as con:
            con.execute('DELETE FROM service_leases WHERE id=?', (lease,))
