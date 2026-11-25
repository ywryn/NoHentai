"""Manual ExHentai refresh, executed in the socket-activated browser service."""
import os
import secrets
import socket
import threading
from urllib.parse import urljoin, urlsplit

from cryptography.fernet import Fernet

from . import db, security, services, settings
from .jobs import JobCancelled, JobFailure, event

KIND = 'cookie-refresh'
SOCKET_PATH = '/run/nohentai-cookie-refresh.sock'
FORUM = 'https://forums.e-hentai.org'
PUBLIC = 'https://e-hentai.org'
PRIVATE = 'https://exhentai.org'
LOGIN = FORUM + '/index.php?act=Login&CODE=00'
LOGIN_FIELDS = ('EXHENTAI_LOGIN_USERNAME', 'EXHENTAI_LOGIN_PASSWORD')
COOKIE_FIELDS = {
    'ipb_member_id': 'EXHENTAI_COOKIE_MEMBER_ID',
    'ipb_pass_hash': 'EXHENTAI_COOKIE_PASS_HASH',
    'igneous': 'EXHENTAI_COOKIE_IGNEOUS',
}


def request(job_id):
    try:
        with socket.socket(socket.AF_UNIX, socket.SOCK_STREAM) as client:
            client.settimeout(100)
            client.connect(SOCKET_PATH)
            client.sendall(f'{job_id}\n'.encode())
            with client.makefile('rb') as result:
                if result.read(2) == b'ok':
                    return
    except OSError:
        raise JobFailure('刷新服务不可用或连接超时，请检查服务器上的刷新服务') from None
    with db.connect() as con:
        row = con.execute('SELECT status FROM jobs WHERE id=?', (job_id,)).fetchone()
    if row and row['status'] == 'completed':
        return
    raise JobFailure('刷新进程异常结束或超时，原 Cookie 已保留')


def stage(job_id, message):
    with db.connect() as con:
        con.execute('UPDATE jobs SET summary=?,updated_at=? WHERE id=? AND status=?',
                    (message, db.now(), job_id, 'in_progress'))
        event(job_id, KIND, message, con=con)


def acquire(username, password, report):
    from playwright.sync_api import Error, sync_playwright

    def allow(route):
        url = urlsplit(route.request.url)
        if url.scheme == 'https' and url.netloc in {
            'forums.e-hentai.org', 'e-hentai.org', 'exhentai.org',
        } and route.request.resource_type not in {'image', 'media', 'font'}:
            route.continue_()
        else:
            route.abort()

    def session(context, url):
        return {entry['name']: entry['value'] for entry in context.cookies([url])}

    with sync_playwright() as playwright:
        browser_env = {key: os.environ[key] for key in ('HOME', 'PATH', 'LANG', 'TMPDIR') if key in os.environ}
        browser = playwright.chromium.launch(timeout=15000, chromium_sandbox=True, env=browser_env)
        try:
            context = browser.new_context(service_workers='block')
            try:
                context.route('**/*', allow)
                page = context.new_page()
                page.set_default_timeout(12000)
                report('正在打开表站论坛登录页')
                try:
                    response = page.goto(LOGIN, wait_until='domcontentloaded')
                    if response and response.headers.get('cf-mitigated') == 'challenge':
                        raise JobFailure('表站论坛要求 Cloudflare 人工验证，原 Cookie 已保留')
                    if response and not response.ok:
                        raise JobFailure('表站论坛拒绝或暂时无法提供登录页')
                    form = page.locator('form').filter(has=page.locator('input[name="PassWord"]'))
                    action = urlsplit(urljoin(page.url, form.get_attribute('action') or page.url))
                    if action.scheme != 'https' or action.netloc != 'forums.e-hentai.org':
                        raise JobFailure('论坛登录表单地址异常')
                    form.locator('input[name="UserName"]').fill(username)
                    form.locator('input[name="PassWord"]').fill(password)
                    form.locator('input[type="submit"], button[type="submit"]').first.click()
                    page.wait_for_load_state('domcontentloaded')
                    initial = session(context, LOGIN)
                    keys = ('ipb_member_id', 'ipb_pass_hash')
                    if not all(initial.get(key) for key in keys):
                        raise JobFailure('未获得表站登录会话，请检查账号、密码或人工验证')
                    page.goto(PUBLIC, wait_until='domcontentloaded')
                    public = session(context, PUBLIC)
                except Error:
                    raise JobFailure('表站登录未完成，页面不可达或需要人工验证') from None

                report('表站已登录，正在请求里站签发 Cookie')
                context.clear_cookies(domain='exhentai.org')
                context.clear_cookies(domain='.exhentai.org')
                context.add_cookies([{'name': key, 'value': public.get(key) or initial[key],
                                      'url': PRIVATE, 'secure': True} for key in keys])
                try:
                    page.goto(PRIVATE + '/favorites.php', wait_until='domcontentloaded')
                    issued = session(context, PRIVATE)
                    if urlsplit(page.url).hostname != 'exhentai.org' or not page.locator('table.itg').count():
                        raise JobFailure('里站未返回收藏列表，请检查账号权限或人工验证')
                except Error:
                    raise JobFailure('里站访问超时或连接失败') from None
                if any(not issued.get(key) or issued[key] in {'mystery', '0'} for key in COOKIE_FIELDS):
                    raise JobFailure('里站未签发完整有效的 Cookie')
                return {field: issued[key] for key, field in COOKIE_FIELDS.items()}
            finally:
                context.close()
        finally:
            browser.close()


def execute(job_id):
    with db.connect() as con:
        row = con.execute('SELECT kind,status,cancel_requested FROM jobs WHERE id=?', (job_id,)).fetchone()
        if not row or row['kind'] != KIND or row['status'] != 'in_progress' or row['cancel_requested']:
            raise JobCancelled('刷新任务已取消或不可运行')
        expected = services.version(con, 'favorites')
        username, password = (security.credential(key, con) for key in LOGIN_FIELDS)
    if not username or not password:
        raise JobFailure('请先在服务配置的收藏来源中保存表站论坛账号和密码')

    candidate = acquire(username, password, lambda message: stage(job_id, message))
    stage(job_id, '正在用候选 Cookie 验证后端收藏访问')
    try:
        # Probe the actual EX site even if the configured collection source is public EH.
        with security.use_credentials(candidate):
            ok = services.probe_favorites(PRIVATE + '/favorites.php')
    except Exception:
        raise JobFailure('后端无法完成候选 Cookie 的收藏访问验证') from None
    if not ok:
        raise JobFailure('候选 Cookie 未通过后端收藏访问验证')

    cipher = Fernet(settings.encryption_key())
    with db.connect() as con:
        con.execute('BEGIN IMMEDIATE')
        row = con.execute('SELECT status,cancel_requested FROM jobs WHERE id=?', (job_id,)).fetchone()
        if row['status'] != 'in_progress' or row['cancel_requested']:
            raise JobCancelled('刷新任务已取消，原 Cookie 已保留')
        if expected != services.version(con, 'favorites'):
            raise JobFailure('刷新期间收藏来源配置已更改，请重新运行')
        stamp = db.now()
        for field, value in candidate.items():
            con.execute('DELETE FROM service_settings WHERE name=?', (field,))
            con.execute('INSERT OR REPLACE INTO credentials VALUES (?,?,?)',
                        (field, cipher.encrypt(value.encode()).decode(), stamp))
        con.execute('INSERT OR REPLACE INTO service_versions VALUES (?,?)', ('favorites', secrets.token_hex(16)))
        con.execute('INSERT INTO history(resource,version,data,created_at,message) VALUES (?,?,?,?,?)',
                    ('service:favorites', secrets.token_hex(16), db.dumps({'fields': sorted(candidate)}),
                     stamp, '刷新 ExHentai Cookie'))
        con.execute("UPDATE jobs SET status='completed',conclusion='success',summary=?,updated_at=? WHERE id=?",
                    ('Cookie 已验证并更新', stamp, job_id))
        event(job_id, KIND, '后端验证通过，三个 Cookie 已同时更新', con=con)


def serve():
    from .jobs import record_failure

    # Socket activation supplies an authenticated local connection on stdin.
    connection = socket.socket(fileno=0)
    line = connection.makefile('rb').readline(24)
    if not line.endswith(b'\n') or not line[:-1].isdigit():
        return
    job_id = int(line)
    finished = threading.Event()

    def stop_on_disconnect():
        try:
            connection.recv(1)
        finally:
            if not finished.is_set():
                os._exit(1)  # systemd cleans the remaining browser process tree.

    threading.Thread(target=stop_on_disconnect, daemon=True).start()
    try:
        execute(job_id)
    except JobCancelled as exc:
        record_failure(job_id, str(exc), 'cancelled')
    except JobFailure as exc:
        record_failure(job_id, str(exc))
    except Exception:
        record_failure(job_id, '浏览器刷新失败，请检查刷新服务和浏览器依赖')
    else:
        finished.set()
        connection.sendall(b'ok')
    finally:
        finished.set()


if __name__ == '__main__':
    serve()
