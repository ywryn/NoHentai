import hashlib
import hmac
import os
import secrets
import time
from contextlib import contextmanager
from contextvars import ContextVar
from cryptography.fernet import Fernet
from fastapi import HTTPException
from . import db, settings

COOKIE = 'nohentai_admin'
_job_credentials = ContextVar('job_credentials', default=None)


def fail(status, message):
    raise HTTPException(status, message)


def digest(token):
    return hashlib.sha256(token.encode()).hexdigest()


@contextmanager
def use_credentials(values):
    marker = _job_credentials.set(values)
    try:
        yield
    finally:
        _job_credentials.reset(marker)


def credential(name, con=None):
    if name not in settings.BUSINESS_NAMES:
        raise ValueError('不允许的配置名称')
    frozen = _job_credentials.get()
    if frozen is not None and name in frozen:
        return frozen[name]
    if con is None:
        with db.connect() as connection:
            return credential(name, connection)
    normal = con.execute('SELECT value_json FROM service_settings WHERE name=?', (name,)).fetchone()
    row = con.execute('SELECT ciphertext FROM credentials WHERE name=?', (name,)).fetchone()
    if normal:
        import json
        value = json.loads(normal[0])
        return ('1' if value else '0') if type(value) is bool else str(value)
    return Fernet(settings.encryption_key()).decrypt(row[0].encode()).decode() if row else os.getenv(name, settings.DEFAULTS.get(name, ''))


def replace_credential(name, value):
    if not isinstance(name, str) or name not in settings.SECRET_NAMES or not isinstance(value, str) or not 1 <= len(value) <= 16000 or '\0' in value:
        fail(400, '凭证名称或内容不正确')
    if name == 'TRANS_PASSWORD' and verify_password(value):
        fail(400, '翻译密码不能与管理密码相同')
    if name in ('EXHENTAI_BASE_URL', 'LLM_API_BASE'):
        from .upstream import validate_url
        validate_url(value, gallery=name == 'EXHENTAI_BASE_URL')
    ciphertext = Fernet(settings.encryption_key()).encrypt(value.encode()).decode()
    with db.connect() as con:
        con.execute('INSERT OR REPLACE INTO credentials VALUES (?,?,?)', (name, ciphertext, db.now()))
        con.execute('INSERT INTO history(resource,version,data,created_at,message) VALUES (?,?,?,?,?)',
                    ('credentials', secrets.token_hex(16), '{}', db.now(), f'替换 {name}'))
        group = 'favorites' if name.startswith('EXHENTAI_') else 'ocr' if name in ('GOOGLE_VISION_API_KEY','PADDLEOCR_API_TOKEN','OCR_SPACE_KEY') else 'translate'
        con.execute('UPDATE service_versions SET version=? WHERE name=?', (secrets.token_hex(16), group))


def hash_password(password):
    salt = secrets.token_bytes(16)
    key = hashlib.scrypt(password.encode(), salt=salt, n=32768, r=8, p=1, maxmem=64*1024*1024)
    return 'scrypt$' + salt.hex() + '$' + key.hex()


def bootstrap_account():
    with db.connect() as con:
        if con.execute('SELECT 1 FROM accounts WHERE id=1').fetchone():
            return
        password = os.getenv('ADMIN_PASSWORD', '')
        if len(password) < 16 or password.startswith('replace_with_'):
            fail(503, '首次启动需要至少 16 字符的独立 ADMIN_PASSWORD')
        if credential('TRANS_PASSWORD') and hmac.compare_digest(digest(password), digest(credential('TRANS_PASSWORD'))):
            fail(503, '管理密码必须与翻译密码不同')
        con.execute('INSERT OR IGNORE INTO accounts VALUES (1,?,?)', (hash_password(password), db.now()))


def password_fingerprint():
    bootstrap_account()
    with db.connect() as con:
        return digest(con.execute('SELECT password_hash FROM accounts WHERE id=1').fetchone()[0])


def verify_password(password):
    if not isinstance(password, str) or not password or len(password) > 1024:
        return False
    bootstrap_account()
    with db.connect() as con:
        encoded = con.execute('SELECT password_hash FROM accounts WHERE id=1').fetchone()[0]
    _, salt, expected = encoded.split('$')
    actual = hashlib.scrypt(password.encode(), salt=bytes.fromhex(salt), n=32768, r=8, p=1, maxmem=64*1024*1024)
    return hmac.compare_digest(actual.hex(), expected)


def session(token):
    fingerprint = password_fingerprint()
    if not isinstance(token, str) or not token.startswith('admin.v1.') or len(token) > 200:
        fail(401, '登录已失效，请重新登录')
    with db.connect() as con:
        row = con.execute('SELECT * FROM sessions WHERE digest=? AND expires>?', (digest(token), time.time())).fetchone()
        if not row or not hmac.compare_digest(row['fingerprint'], fingerprint):
            fail(401, '登录已失效，请重新登录')
        if not row['csrf']:
            con.execute('UPDATE sessions SET csrf=? WHERE digest=?', (secrets.token_urlsafe(24), digest(token)))
            row = con.execute('SELECT * FROM sessions WHERE digest=?', (digest(token),)).fetchone()
        # Avoid a database write for every single API call.
        if not row['last_seen'] or (db.now()[:16] != row['last_seen'][:16]):
            con.execute('UPDATE sessions SET last_seen=? WHERE digest=?', (db.now(), digest(token)))
    return {'token': token, 'expiresAt': int(row['expires']*1000), 'csrf': row['csrf']}


def login(password, ip, remember=False, agent=''):
    password_fingerprint()
    if isinstance(password, str) and password.startswith('admin.v1.'):
        return session(password)
    if not db.reserve('login:' + ip, 10, 300):
        fail(429, '登录尝试过多，请五分钟后重试')
    if not verify_password(password):
        fail(401, '管理密码错误')
    token = 'admin.v1.' + secrets.token_urlsafe(32)
    expires = time.time() + (30*86400 if remember else 12*3600)
    csrf = secrets.token_urlsafe(24)
    with db.connect() as con:
        con.execute('DELETE FROM sessions WHERE expires<?', (time.time(),))
        con.execute('INSERT INTO sessions(digest,expires,fingerprint,created_at,last_seen,csrf,agent) VALUES (?,?,?,?,?,?,?)',
                    (digest(token), expires, password_fingerprint(), db.now(), db.now(), csrf, str(agent)[:300]))
    return {'token': token, 'expiresAt': int(expires*1000), 'csrf': csrf}


def list_sessions(token):
    current = digest(token)
    with db.connect() as con:
        return {'items': [{'id': r['digest'], 'current': r['digest'] == current, 'createdAt': r['created_at'],
                           'lastSeen': r['last_seen'], 'expiresAt': int(r['expires']*1000), 'agent': r['agent']}
                          for r in con.execute('SELECT * FROM sessions WHERE expires>? ORDER BY expires DESC', (time.time(),))]}


def revoke_session(session_id):
    with db.connect() as con:
        con.execute('DELETE FROM sessions WHERE digest=?', (session_id,))
    return {'ok': True}


def change_password(current, new):
    if not verify_password(current):
        fail(401, '当前密码不正确')
    if not isinstance(new, str) or not 16 <= len(new) <= 1024 or new.startswith('replace_with_'):
        fail(400, '新密码需要 16–1024 字符')
    if hmac.compare_digest(digest(new), digest(credential('TRANS_PASSWORD'))):
        fail(400, '管理密码不能与翻译密码相同')
    with db.connect() as con:
        con.execute('UPDATE accounts SET password_hash=?,updated_at=? WHERE id=1', (hash_password(new), db.now()))
        con.execute('DELETE FROM sessions')
        con.execute('INSERT INTO history(resource,version,data,created_at,message) VALUES (?,?,?,?,?)',
                    ('account', secrets.token_hex(16), '{}', db.now(), '修改管理密码并撤销全部会话'))
    return {'ok': True, 'relogin': True}


def trans_auth(password, ip):
    if not db.reserve('trans-auth:' + ip, 120, 60):
        fail(429, '请求过多，请稍后重试')
    expected = credential('TRANS_PASSWORD')
    if not expected or not isinstance(password, str) or len(password) > 1024 or not hmac.compare_digest(digest(password), digest(expected)):
        fail(401, 'invalid_password')
