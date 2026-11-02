"""Opt-in full-stack smoke test against a disposable DB and built frontend.
Requires nginx and: pip install -r tests/requirements-browser.txt
Then: python -m playwright install --with-deps chromium
Run from the repository: .venv/bin/python tests/browser_smoke.py
No external requests, paid services, or production data are modified.
"""
import os
from pathlib import Path
import secrets
import subprocess
import sys
import tempfile
import time
from urllib.parse import urlsplit
import httpx
from cryptography.fernet import Fernet
from playwright.sync_api import sync_playwright, expect

ROOT = Path(__file__).resolve().parents[1]
BASE = 'http://127.0.0.1:18080'


def main():
    assert (ROOT / 'web-static/dist/index.html').exists(), 'Run npm run build first'
    assert not (ROOT / 'web-static/dist/data').exists(), 'Mutable data must not ship in dist'
    with tempfile.TemporaryDirectory() as temporary:
        tmp = Path(temporary)
        password = secrets.token_urlsafe(24)
        env = dict(os.environ, NOHENTAI_DATA_DIR=str(tmp / 'data'), ADMIN_PASSWORD=password,
                   CREDENTIAL_ENCRYPTION_KEY=Fernet.generate_key().decode(), ALLOWED_ORIGINS=BASE,
                   TRANS_PASSWORD='browser-test-translation-password')
        subprocess.run([sys.executable, '-m', 'backend.cli', 'init'], cwd=ROOT, env=env, check=True)
        config = (ROOT / 'deploy/nginx.conf').read_text()
        config = config.replace('listen 80;', 'listen 127.0.0.1:18080;').replace('    listen [::]:80;\n', '')
        config = config.replace('root /srv/nohentai/www/current;', f'root {ROOT}/web-static/dist;')
        config = config.replace('127.0.0.1:8000', '127.0.0.1:18000')
        config = config.replace('server_name nohentai.com www.nohentai.com;', 'server_name 127.0.0.1;')
        header = 'user root;\n' if os.geteuid() == 0 else ''
        (tmp / 'nginx.conf').write_text(header + f'pid {tmp}/nginx.pid;\nerror_log {tmp}/nginx-error.log;\nevents {{}}\nhttp {{\naccess_log off;\ninclude /etc/nginx/mime.types;\n' + config + '\n}')
        processes = []
        with (tmp / 'services.log').open('w') as log:
            try:
                processes.append(subprocess.Popen([sys.executable, '-m', 'uvicorn', 'backend.main:app',
                    '--host', '127.0.0.1', '--port', '18000', '--no-access-log'], cwd=ROOT, env=env, stdout=log, stderr=log))
                processes.append(subprocess.Popen(['nginx', '-c', str(tmp / 'nginx.conf'), '-g', 'daemon off;'], stdout=log, stderr=log))
                for _ in range(100):
                    try:
                        if httpx.get(BASE + '/api/health').status_code == 200:
                            break
                    except httpx.HTTPError:
                        pass
                    time.sleep(.1)
                else:
                    raise RuntimeError('Services failed to start')
                with sync_playwright() as p:
                    browser = p.chromium.launch(headless=True)
                    page = browser.new_page(viewport={'width': 1440, 'height': 1000})
                    page.set_default_timeout(20000)
                    errors = []
                    page.on('pageerror', lambda error: errors.append(str(error)))
                    page.route('**/*', lambda route: route.continue_() if urlsplit(route.request.url).hostname == '127.0.0.1' else route.abort())
                    page.goto(BASE + '/#/admin')
                    page.get_by_label('管理密码', exact=True).fill(password)
                    page.get_by_role('button', name='进入工作空间').click()
                    expect(page.get_by_role('heading', name='站点概览')).to_be_visible()
                    for name, heading in [('画廊', '画廊'), ('实体书单', '实体书单'), ('每日筛选', '每日筛选'),
                                          ('翻译配置', '翻译配置'), ('同步任务', '同步任务'), ('服务测活', '服务测活'), ('凭证管理', '凭证管理')]:
                        page.locator('.a-sidebar').get_by_role('link', name=name, exact=True).click()
                        expect(page.get_by_role('heading', name=heading, exact=True).first).to_be_visible()
                        expect(page.locator('.a-page[aria-busy="false"]')).to_be_visible()
                        assert page.locator('.a-alert-error').count() == 0, name
                    page.reload()
                    expect(page.get_by_role('heading', name='凭证管理', exact=True)).to_be_visible()
                    page.locator('.a-sidebar').get_by_role('link', name='画廊', exact=True).click()
                    page.locator('.a-gallery-row').first.click()
                    page.get_by_label('展示标题', exact=True).fill('standalone browser smoke title')
                    page.get_by_role('button', name='保存更改', exact=True).click()
                    expect(page.locator('.a-alert-success')).to_be_visible()
                    response = page.request.get(BASE + '/data/galleries.json')
                    assert response.json()[0]['title'] == 'standalone browser smoke title'
                    page.locator('.a-sidebar').get_by_role('link', name='翻译配置', exact=True).click()
                    page.get_by_label('默认模型', exact=True).fill('browser-test-model')
                    page.get_by_role('button', name='保存更改', exact=True).click()
                    expect(page.locator('.a-alert-success')).to_be_visible()
                    page.locator('.a-sidebar').get_by_role('link', name='同步任务', exact=True).click()
                    page.locator('.a-workflow').filter(has_text='同步画廊').click()
                    page.locator('dialog[open]').get_by_role('button', name='启动任务', exact=True).click()
                    expect(page.locator('.a-run-row')).to_have_count(1)
                    expect(page.locator('.a-run-row')).to_contain_text('排队中')
                    page.locator('.a-run-row').get_by_role('button', name='查看结果').click()
                    expect(page.locator('dialog[open]')).to_contain_text('等待 Worker 执行')
                    page.locator('dialog[open]').get_by_role('button', name='关闭', exact=True).click()
                    page.locator('.a-sidebar').get_by_role('button', name='退出管理', exact=True).click()
                    expect(page.get_by_label('管理密码', exact=True)).to_be_visible()
                    assert not errors, errors
                    browser.close()
                print('Browser smoke passed: all admin pages, login restore/logout, gallery/config save, queue and result dialog')
            finally:
                for process in reversed(processes):
                    process.terminate()
                for process in processes:
                    try:
                        process.wait(timeout=10)
                    except subprocess.TimeoutExpired:
                        process.kill()
                        process.wait()


if __name__ == '__main__':
    main()
