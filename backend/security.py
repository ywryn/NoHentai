import hashlib
import hmac
import os
import secrets
import time
from cryptography.fernet import Fernet
from fastapi import HTTPException
from . import db, settings


def fail(status, message):
    raise HTTPException(status, message)


def credential(name):
    if name not in settings.SECRET_NAMES:
        raise ValueError('不允许的凭证名称')
    with db.connect() as con:
        row = con.execute('SELECT ciphertext FROM credentials WHERE name=?', (name,)).fetchone()
    return Fernet(settings.encryption_key()).decrypt(row[0].encode()).decode() if row else os.getenv(name, '')


def replace_credential(name, value):
    if not isinstance(name, str) or name not in settings.SECRET_NAMES or not isinstance(value, str) or not 1 <= len(value) <= 16000 or '\0' in value:
        fail(400, '凭证名称或内容不正确')
    if name == 'TRANS_PASSWORD' and hmac.compare_digest(digest(value), digest(os.getenv('ADMIN_PASSWORD', ''))):
        fail(400, '翻译密码不能与管理密码相同')
    if name in ('EXHENTAI_BASE_URL', 'LLM_API_BASE'):
        from .upstream import validate_url
        validate_url(value, gallery=name == 'EXHENTAI_BASE_URL')
    ciphertext = Fernet(settings.encryption_key()).encrypt(value.encode()).decode()
    with db.connect() as con:
        con.execute('INSERT OR REPLACE INTO credentials VALUES (?,?,?)', (name, ciphertext, db.now()))
        # No values in audit records, including encrypted values.
        con.execute('INSERT INTO history(resource,version,data,created_at,message) VALUES (?,?,?,?,?)',
                    ('credentials', secrets.token_hex(16), '{}', db.now(), f'替换 {name}'))


def password_fingerprint():
    password = os.getenv('ADMIN_PASSWORD', '')
    if len(password) < 16 or password.startswith('replace_with_'):
        fail(503, '请在服务器配置至少 16 字符的独立 ADMIN_PASSWORD')
    if hmac.compare_digest(digest(password), digest(credential('TRANS_PASSWORD'))):
        fail(503, 'ADMIN_PASSWORD 必须与 TRANS_PASSWORD 分开设置')
    return hashlib.sha256(password.encode()).hexdigest()


def digest(token):
    return hashlib.sha256(token.encode()).hexdigest()


def session(token):
    fingerprint = password_fingerprint()
    if not isinstance(token, str) or not token.startswith('admin.v1.') or len(token) > 200:
        fail(401, '登录已失效，请重新登录')
    with db.connect() as con:
        row = con.execute('SELECT * FROM sessions WHERE digest=? AND expires>?', (digest(token), time.time())).fetchone()
    if not row or not hmac.compare_digest(row['fingerprint'], fingerprint):
        fail(401, '登录已失效，请重新登录')
    return {'token': token, 'expiresAt': int(row['expires'] * 1000)}


def login(password, ip, remember=False):
    password_fingerprint()
    if isinstance(password, str) and password.startswith('admin.v1.'):
        return session(password)
    if not db.reserve('login:' + ip, 10, 300):
        fail(429, '登录尝试过多，请五分钟后重试')
    expected = os.getenv('ADMIN_PASSWORD', '')
    if not isinstance(password, str) or len(password) > 1024 or not hmac.compare_digest(digest(password), digest(expected)):
        fail(401, '管理密码错误')
    token = 'admin.v1.' + secrets.token_urlsafe(32)
    expires = time.time() + (30 * 86400 if remember else 12 * 3600)
    with db.connect() as con:
        con.execute('DELETE FROM sessions WHERE expires<?', (time.time(),))
        con.execute('INSERT INTO sessions VALUES (?,?,?)', (digest(token), expires, password_fingerprint()))
    return {'token': token, 'expiresAt': int(expires * 1000)}


def trans_auth(password, ip):
    if not db.reserve('trans-auth:' + ip, 120, 60):
        fail(429, '请求过多，请稍后重试')
    expected = credential('TRANS_PASSWORD')
    if not expected or not isinstance(password, str) or len(password) > 1024 or not hmac.compare_digest(digest(password), digest(expected)):
        fail(401, 'invalid_password')
