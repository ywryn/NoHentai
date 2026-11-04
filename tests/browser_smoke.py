"""Opt-in full-stack smoke test against a disposable DB and built frontend.
Requires nginx and: pip install -r tests/requirements-browser.txt
Then: python -m playwright install --with-deps chromium
Run from the repository: .venv/bin/python tests/browser_smoke.py
No external requests, paid services, or production data are modified.
"""
import os
import re
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
    expect.set_options(timeout=15000)
    assert (ROOT / 'web-static/dist/index.html').exists(), 'Run npm run build first'
    assert not (ROOT / 'web-static/dist/data').exists(), 'Mutable data must not ship in dist'
    protected_paths=[Path('/var/lib/nginx')/name for name in ('body','proxy','fastcgi','uwsgi','scgi')]
    protected_owners={path:(path.stat().st_uid,path.stat().st_gid,path.stat().st_mode) for path in protected_paths if path.exists()}
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
        (tmp / 'nginx.conf').write_text(header + f'pid {tmp}/nginx.pid;\nerror_log {tmp}/nginx-error.log;\nevents {{}}\nhttp {{\naccess_log off;\ninclude /etc/nginx/mime.types;\nclient_body_temp_path {tmp}/client-body;\nproxy_temp_path {tmp}/proxy-temp;\nfastcgi_temp_path {tmp}/fastcgi-temp;\nuwsgi_temp_path {tmp}/uwsgi-temp;\nscgi_temp_path {tmp}/scgi-temp;\n' + config + '\n}')
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
                large=httpx.post(BASE+'/api/trans-ocr',json={'password':'','imageBase64':'A'*300000},timeout=15)
                assert large.status_code==401,('large OCR request must reach backend',large.status_code)
                with sync_playwright() as p:
                    browser = p.chromium.launch(headless=True)
                    context = browser.new_context(viewport={'width': 1440, 'height': 1000})
                    page = context.new_page()
                    page.set_default_timeout(20000)
                    errors = []
                    page.on('pageerror', lambda error: errors.append(str(error)))
                    page.route('**/*', lambda route: route.continue_() if urlsplit(route.request.url).hostname == '127.0.0.1' else route.abort())
                    catalog_requests = []
                    page.on('request', lambda request: catalog_requests.append(urlsplit(request.url).path))
                    page.goto(BASE + '/#/')
                    cards = page.locator('.home-page a[href*="/gallery/"]')
                    try:
                        expect(cards).to_have_count(30,timeout=15000)
                    except AssertionError:
                        print('Page errors:', errors)
                        print('Home text:', page.locator('.home-page').inner_text()[:450])
                        print('Requests:', catalog_requests)
                        print('First home anchor:', page.locator('.home-page a').first.evaluate('(a)=>a.outerHTML.slice(0,600)'))
                        print('Home links:', page.locator('.home-page a').evaluate_all('(links) => links.slice(0,3).map(a=>a.getAttribute("href"))'))
                        raise
                    first_href = cards.first.get_attribute('href')
                    first_gid = re.search(r'/gallery/([0-9]+)', first_href)[1]
                    page.get_by_role('button', name='下一页', exact=True).first.click()
                    expect(page).to_have_url(BASE + '/#/?page=2')
                    expect(cards).to_have_count(30)
                    expect(cards.first).not_to_have_attribute('href', first_href)
                    page.reload()
                    expect(page).to_have_url(BASE + '/#/?page=2')
                    expect(cards).to_have_count(30)
                    search = page.get_by_role('combobox', name='搜索画廊')
                    search.fill('gid:' + first_gid)
                    search.press('Enter')
                    expect(cards).to_have_count(1)
                    expect(cards.first).to_have_attribute('href', first_href)
                    page.get_by_role('button', name='清空搜索词', exact=True).click()
                    expect(cards).to_have_count(30)
                    page.locator('.home-filter-btn').click()
                    page.get_by_label('Manga', exact=False).first.check()
                    expect(page).to_have_url(BASE + '/#/?type=Manga')
                    expect(cards).to_have_count(30)
                    page.keyboard.press('Escape')
                    cards.first.click()
                    expect(page.locator('.gallery-detail-page')).to_be_visible()
                    assert '/data/galleries.json' not in catalog_requests, catalog_requests
                    assert '/data/translations.json' not in catalog_requests, catalog_requests
                    assert any(path.startswith('/api/galleries/') for path in catalog_requests), catalog_requests
                    print('Homepage/detail: server pagination, query, category, URL restore; zero full-data downloads')
                    from PIL import Image
                    import io
                    ocr_image=io.BytesIO();Image.new('RGB',(400,2600),'white').save(ocr_image,format='PNG')
                    ocr_mode={'value':'server-error'}
                    def fake_ocr(route):
                        if ocr_mode['value']=='server-error':route.fulfill(status=500,content_type='text/html',body='<html>nginx failure</html>')
                        elif ocr_mode['value']=='malformed':route.fulfill(json={})
                        else:route.fulfill(json={'results':[],'source':'vision'})
                    media_routes=[re.compile(r'/api/gallery-images\?'),re.compile(r'/api/image-url\?'),re.compile(r'/api/image-proxy\?'),re.compile(r'/api/trans-ocr$')]
                    media_state={'list_fail':True,'image_fail':True,'image_requests':0,'urls':[]}
                    def fake_pages(route):
                        if media_state['list_fail']:route.fulfill(status=502,content_type='text/html',body='upstream failed')
                        else:route.fulfill(json={'gid':first_gid,'total':2,'source':'e-hentai','images':[{'pageNum':i,'pageUrl':f'https://e-hentai.org/s/testing/{first_gid}-{i}','thumbSprite':'','thumbX':0,'thumbW':100,'thumbH':142} for i in (1,2)]})
                    def fake_url(route):
                        media_state['urls'].append(route.request.url)
                        route.fulfill(json={'imageUrl':'https://ehgt.org/test.png','nlParam':'reload-key'})
                    def fake_image(route):
                        media_state['image_requests']+=1
                        if media_state['image_fail']:route.fulfill(status=502,content_type='text/html',body='image failed')
                        else:route.fulfill(content_type='image/png',body=ocr_image.getvalue())
                    page.route(media_routes[0],fake_pages)
                    page.route(media_routes[1],fake_url)
                    page.route(media_routes[2],fake_image)
                    page.route('https://ehgt.org/test.png',fake_image)
                    page.goto(BASE+'/#/translate')
                    expect(page).to_have_title(re.compile('翻译入口'))
                    expect(page.locator('.tl-container')).to_be_visible()
                    page.goto(BASE+f'/#/gallery/{first_gid}')
                    page.get_by_role('button',name='加载页面缩略图',exact=False).click()
                    expect(page.get_by_role('button',name='重新加载缩略图',exact=True)).to_be_visible()
                    media_state['list_fail']=False
                    page.get_by_role('button',name='重新加载缩略图',exact=True).click()
                    expect(page.locator('.thumb-cell')).to_have_count(2)
                    media_state['list_fail']=True
                    page.evaluate("localStorage.setItem('reader-settings',JSON.stringify({pagesPerScreen:1}));localStorage.setItem('reader-hint-seen','1')")
                    page.goto(BASE+f'/#/gallery/{first_gid}/read?token=abcdef1234&page=2')
                    expect(page.get_by_role('button',name='重新加载页面列表',exact=True)).to_be_visible()
                    media_state['list_fail']=False
                    page.get_by_role('button',name='重新加载页面列表',exact=True).click()
                    expect(page.locator('.pi-error:visible').first).to_be_visible()
                    before_retry=media_state['image_requests']
                    page.wait_for_timeout(500)
                    assert media_state['image_requests']==before_retry, 'Reader must stop automatic retries'
                    media_state['image_fail']=False
                    page.locator('.pi-error:visible').first.get_by_role('button',name='重试',exact=True).click()
                    expect(page.locator('.pi-img:visible').first).to_be_visible()
                    expect(page).to_have_url(re.compile('[?&]page=2'))
                    media_state['list_fail']=True
                    media_state['image_fail']=True
                    page.evaluate('''gid=>localStorage.setItem(`trans_cache_${gid}_p2`,JSON.stringify({ocrResults:[{_id:1,text:'已保存原文',translation:'保留的译文',confidence:1,bbox:[10,10,100,60]}],lastOcrSource:'google',ts:Date.now()}))''',first_gid)

                    page.route(media_routes[3],fake_ocr)
                    page.goto(BASE+f'/#/gallery/{first_gid}/translate?token=abcdef1234&page=2')
                    page.get_by_placeholder('输入密码',exact=True).fill(env['TRANS_PASSWORD'])
                    page.get_by_role('button',name='进入',exact=True).click()
                    expect(page.get_by_role('button',name='重新加载页面列表',exact=True)).to_be_visible()
                    media_state['list_fail']=False
                    page.get_by_role('button',name='重新加载页面列表',exact=True).click()
                    expect(page.get_by_role('button',name='重新加载图片',exact=True)).to_be_visible()
                    expect(page.locator('.gt-results-list')).to_contain_text('保留的译文')
                    image_attempts=media_state['image_requests']
                    page.wait_for_timeout(500)
                    assert media_state['image_requests']==image_attempts, 'Translation must stop automatic retries'
                    assert any('nl%3Dreload-key' in url for url in media_state['urls'])
                    media_state['image_fail']=False
                    page.get_by_role('button',name='重新加载图片',exact=True).click()
                    expect(page.locator('.gt-page-img')).to_be_visible()
                    page.wait_for_function('document.querySelector(".gt-page-img")?.naturalHeight===2600')
                    expect(page.locator('.gt-results-list')).to_contain_text('保留的译文')
                    page.locator('.gt-result-del').click()

                    page.get_by_role('button',name='翻译',exact=True).click()
                    expect(page.get_by_text('OCR 失败: 服务器处理请求失败，请稍后重试',exact=True)).to_be_visible()
                    ocr_mode['value']='malformed'
                    page.get_by_role('button',name='翻译',exact=True).click()
                    expect(page.get_by_text('OCR 失败: 识别服务未返回有效结果，请重试或切换 OCR 服务',exact=True)).to_be_visible()
                    ocr_mode['value']='empty'
                    page.get_by_role('button',name='翻译',exact=True).click()
                    expect(page.get_by_text('未识别到文字',exact=True)).to_be_visible()
                    assert 'undefined' not in page.locator('body').inner_text()
                    page.goto(BASE+'/#/printed')
                    for pattern in media_routes:page.unroute(pattern)
                    page.unroute('https://ehgt.org/test.png')
                    print('OCR regression: large request reaches backend; scaled image handles HTML 500, missing results and empty OCR without JavaScript errors')
                    page.goto(BASE + '/#/printed')
                    expect(page.get_by_role('heading',name='实体书单',exact=True)).to_be_visible()
                    expect(page.locator('.digi-container a[href*="/gallery/"]').first).to_be_visible()
                    page.goto(BASE + '/#/daily')
                    expect(page.locator('.daily-group-pill').first).to_be_visible()
                    expect(page.get_by_text('查看抓取条件',exact=True)).to_have_count(0)
                    expect(page.get_by_role('region',name='分组筛选条件')).to_be_visible()
                    expect(page.locator('.daily-rule-expression')).to_contain_text('搜索表达式')
                    daily_groups=page.request.get(BASE+'/api/daily').json()['groups']
                    daily_index=next(i for i,g in enumerate(daily_groups) if g.get('galleries'))
                    page.locator('.daily-group-pill').nth(daily_index).click()
                    expect(page.locator('.daily-rule-expression code')).to_have_text(daily_groups[daily_index]['conditions']['keyword'] or '不限关键词')
                    daily_gid=str(daily_groups[daily_index]['galleries'][0]['gid'])
                    daily_cards=page.locator('.daily-page a[href*="/gallery/"]')
                    daily_search=page.get_by_role('combobox',name='搜索每日画廊',exact=True)
                    daily_search.fill('gid:'+daily_gid)
                    expect(daily_cards).to_have_count(1)
                    page.reload();expect(daily_search).to_have_value('gid:'+daily_gid);expect(daily_cards).to_have_count(1)
                    daily_search.fill('f:chi')
                    expect(page.locator('#daily-tag-suggestions [role=option]').first).to_be_visible()
                    daily_search.press('ArrowDown');daily_search.press('Enter')
                    expect(daily_search).to_have_value(re.compile('female:'))
                    page.get_by_role('button',name='重置筛选',exact=True).click()
                    expect(daily_cards).to_have_count(min(30,len(daily_groups[daily_index]['galleries'])))
                    daily_category=daily_groups[daily_index]['galleries'][0]['category']
                    page.locator('.daily-categories button').filter(has_text=daily_category).click()
                    expect(page.locator('.daily-categories button').filter(has_text=daily_category)).to_have_attribute('aria-pressed','true')
                    page.get_by_role('button',name='重置筛选',exact=True).click()
                    if len(daily_groups[daily_index]['galleries'])>30:
                        page.locator('.daily-page').get_by_role('button',name='下一页',exact=True).first.click()
                        expect(page).to_have_url(re.compile('[?&]page=2'))
                        page.reload();expect(daily_cards).to_have_count(min(30,len(daily_groups[daily_index]['galleries'])-30))
                    page.set_viewport_size({'width':390,'height':844})
                    expect(page.locator('.tab-bar')).to_be_visible()
                    assert page.evaluate('document.documentElement.scrollWidth <= innerWidth+1')
                    page.screenshot(path='/tmp/nohentai-daily-mobile.png',full_page=True)
                    expect(page.get_by_role('region',name='分组筛选条件')).to_be_visible()
                    expect(page.locator('.daily-rule-fields')).to_contain_text('最低评分')
                    page.set_viewport_size({'width':320,'height':740})
                    assert page.evaluate('document.documentElement.scrollWidth <= innerWidth+1')
                    page.goto(BASE+'/#/')
                    expect(cards).to_have_count(30)
                    page.screenshot(path='/tmp/nohentai-home-mobile.png',full_page=True)
                    page.set_viewport_size({'width':1440,'height':1000})
                    assert '/data/galleries.json' not in catalog_requests, catalog_requests
                    assert '/data/translations.json' not in catalog_requests, catalog_requests
                    page.goto(BASE+'/#/data')
                    expect(page.get_by_role('heading',name='收藏统计',exact=True)).to_be_visible()
                    expected_stats=page.request.get(BASE+'/api/stats').json()
                    expect(page.locator('.summary-value')).to_have_text(str(expected_stats['stats']['total_count']))
                    expect(page.locator('.heatmap-chart canvas')).to_be_visible()
                    assert '/api/stats' in catalog_requests
                    assert '/data/stats.json' not in catalog_requests
                    page.reload();expect(page.locator('.summary-value')).to_have_text(str(expected_stats['stats']['total_count']))
                    page.route('**/api/stats',lambda route:route.fulfill(status=503,json={'error':'temporary failure'}))
                    page.reload();expect(page.locator('.stats-load-error')).to_contain_text('统计加载失败')
                    page.unroute('**/api/stats')
                    page.get_by_role('button',name='重新加载',exact=True).click()
                    expect(page.locator('.summary-value')).to_have_text(str(expected_stats['stats']['total_count']))
                    print('Statistics: /api/stats only, charts rendered, reload and error retry passed')
                    page.goto(BASE + '/#/admin')
                    page.get_by_label('管理密码', exact=True).fill(password)
                    page.get_by_role('button', name='进入工作空间').click()
                    expect(page.get_by_role('heading', name='站点概览')).to_be_visible()
                    cookies=browser.contexts[0].cookies()
                    assert any(cookie['name']=='nohentai_admin' and cookie['httpOnly'] for cookie in cookies)
                    assert page.evaluate('localStorage.getItem("nohentai-admin-session-v1")') is None
                    for name, heading in [('画廊','画廊'),('实体书单','实体书单'),('每日筛选','每日筛选'),('服务配置','服务配置'),('任务与调度','同步任务与调度'),('服务状态','服务状态'),('修改记录','修改记录'),('备份与恢复','备份与恢复'),('账户与会话','账户与会话')]:
                        page.locator('.a-sidebar').get_by_role('link',name=name,exact=True).click()
                        expect(page.get_by_role('heading',name=heading,exact=True).first).to_be_visible()
                        assert page.locator('.a-alert-error').count()==0,name
                        if name=='服务状态':
                            expect(page.locator('.ops-health-banner')).to_be_visible()
                            page.screenshot(path='/tmp/nohentai-admin-v3-health.png',full_page=True)
                    page.reload()
                    expect(page.get_by_role('heading',name='账户与会话',exact=True)).to_be_visible()
                    def admin(action,**data):
                        session=page.request.get(BASE+'/api/admin/session').json()['session']
                        response=page.request.post(BASE+'/api/admin',data={'action':action,**data},headers={'X-CSRF-Token':session['csrf']})
                        assert response.ok,(action,response.text())
                        return response.json()
                    page.locator('.a-sidebar').get_by_role('link',name='画廊',exact=True).click()
                    save_button=page.get_by_role('button',name='保存当前条目',exact=True)
                    expect(save_button).to_be_disabled()
                    title=page.get_by_label('展示标题',exact=True)
                    original_title=title.input_value()
                    title.fill(original_title+' temporarily changed')
                    expect(save_button).to_be_enabled()
                    title.fill(original_title)
                    expect(save_button).to_be_disabled()
                    visible=page.get_by_role('checkbox',name='在公开列表中显示',exact=True)
                    visible.uncheck();expect(save_button).to_be_enabled()
                    visible.check();expect(save_button).to_be_disabled()
                    original_gallery=page.request.get(BASE+'/api/galleries/'+first_gid).json()['gallery']
                    page.locator('.ops-category-picker button').filter(has_text=original_gallery['category']).click()
                    expect(save_button).to_be_disabled()
                    tag=original_gallery['tags'][0]
                    page.get_by_role('button',name='移除标签 '+tag,exact=True).click()
                    expect(save_button).to_be_enabled()
                    page.get_by_role('combobox',name='添加标签',exact=True).fill(tag)
                    page.locator('.ops-tag-editor [role=option]').filter(has_text=tag).first.click()
                    expect(save_button).to_be_disabled()
                    page.locator('.a-sidebar').get_by_role('link',name='服务配置',exact=True).click()
                    expect(page.get_by_role('heading',name='服务配置',exact=True)).to_be_visible()
                    expect(page.locator('.a-confirm[open]')).to_have_count(0)
                    model=page.get_by_label('模型',exact=True)
                    saved_model=model.input_value()
                    model.fill('temporary-model');expect(page.get_by_role('button',name='保存翻译服务')).to_be_enabled()
                    model.fill(saved_model);expect(page.get_by_role('button',name='保存翻译服务')).to_be_disabled()
                    page.locator('.a-sidebar').get_by_role('link',name='画廊',exact=True).click()
                    expect(save_button).to_be_disabled()
                    search=page.get_by_role('combobox',name='查找条目',exact=True)
                    search.fill('gid:'+first_gid)
                    expect(page.locator('.a-gallery-row')).to_have_count(1)
                    search.fill('f:chi')
                    expect(page.locator('.ops-search [role=option]').first).to_be_visible()
                    search.press('ArrowDown');search.press('Enter')
                    expect(search).to_have_value(re.compile('female:'))
                    search.fill('')
                    expect(page.locator('.a-gallery-row')).to_have_count(30)
                    page.get_by_role('button',name='Manga',exact=True).click()
                    expect(page.locator('.ops-category-picker button').filter(has_text='Manga')).to_have_attribute('aria-pressed','true')
                    page.get_by_role('combobox',name='添加标签',exact=True).fill('artist:asanagi')
                    expect(page.locator('.ops-tag-editor [role=option]').first).to_be_visible()
                    page.get_by_role('combobox',name='添加标签',exact=True).press('Enter')
                    expect(page.get_by_role('button',name='移除标签 artist:asanagi',exact=True)).to_be_visible()
                    from PIL import Image
                    import io
                    image=Image.new('RGB',(100,160),'navy');stream=io.BytesIO();image.save(stream,format='PNG')
                    page.get_by_label('上传画廊封面',exact=True).set_input_files({'name':'gallery.png','mimeType':'image/png','buffer':stream.getvalue()})
                    expect(page.locator('.ops-cover-editor img')).to_have_attribute('src',re.compile('/media/'))
                    page.get_by_label('展示标题',exact=True).fill('standalone browser smoke title')
                    page.get_by_role('button',name='保存当前条目',exact=True).click()
                    expect(page.locator('.a-alert-success')).to_contain_text('当前条目已保存')
                    assert page.request.get(BASE+'/api/galleries/'+first_gid).json()['gallery']['title']=='standalone browser smoke title'
                    page.get_by_role('button',name='修改历史',exact=True).click()
                    expect(page.locator('.v2-history-entry')).to_have_count(2)
                    page.locator('.v2-history-entry').last.get_by_role('button',name='恢复此版本').click()
                    page.locator('.a-confirm').get_by_role('button',name='恢复版本',exact=True).click()
                    expect(page.locator('dialog[open]')).to_have_count(0)
                    assert page.request.get(BASE+'/api/galleries/'+first_gid).json()['gallery']['title']!='standalone browser smoke title'
                    page.locator('.a-sidebar').get_by_role('link',name='实体书单',exact=True).click()
                    page.get_by_role('button',name='新增书目',exact=True).click()
                    page.get_by_label('中文书名',exact=True).fill('Browser test book')
                    page.get_by_label('书目编号（允许重复）',exact=True).fill('TEST-DUPLICATE')
                    page.get_by_role('combobox',name='关联画廊',exact=True).fill(first_gid)
                    page.get_by_role('button',name='关联画廊 '+first_gid,exact=True).click()
                    expect(page.locator('.ops-link-panel .ops-gallery-preview').first).to_contain_text('#'+first_gid)
                    from PIL import Image
                    import io
                    image=Image.new('RGB',(100,160),'navy');stream=io.BytesIO();image.save(stream,format='PNG')
                    page.locator('input[type=file]').set_input_files({'name':'cover.png','mimeType':'image/png','buffer':stream.getvalue()})
                    expect(page.locator('.v2-cover img')).to_be_visible()
                    page.wait_for_function('document.querySelector(".v2-cover img")?.naturalWidth > 0')
                    page.get_by_role('button',name='保存当前条目',exact=True).click()
                    expect(page.locator('.a-alert-success')).to_be_visible()
                    assert any(item['book']['书名']=='Browser test book' for item in page.request.get(BASE+'/api/books').json()['items'])
                    page.get_by_role('button',name='删除条目',exact=True).click()
                    page.locator('.a-confirm').get_by_role('button',name='删除',exact=True).click()
                    expect(page.locator('.a-alert-success')).to_contain_text('操作已完成')
                    assert not any(item['book']['书名']=='Browser test book' for item in page.request.get(BASE+'/api/books').json()['items'])
                    page.locator('.a-sidebar').get_by_role('link',name='每日筛选',exact=True).click()
                    expect(page.get_by_text('展示标签（每行一个）',exact=True)).to_have_count(0)
                    page.get_by_label('分组名称',exact=True).fill('Browser daily rule')
                    page.get_by_role('button',name='保存当前条目',exact=True).click()
                    expect(page.locator('.a-alert-success')).to_be_visible()
                    page.get_by_role('button',name='立即同步此分组',exact=True).click()
                    expect(page.locator('.a-alert-success')).to_contain_text('已加入队列')
                    page.locator('.a-sidebar').get_by_role('link',name='服务配置',exact=True).click()
                    page.get_by_label('重试间隔（秒）',exact=True).fill('3')
                    page.get_by_label('模型',exact=True).fill('browser-test-model')
                    page.get_by_role('button',name='保存翻译服务',exact=True).click()
                    expect(page.locator('.a-alert-success')).to_be_visible()
                    assert admin('load',resource='translate')['data']['model']=='browser-test-model'
                    expect(page.get_by_label('重试间隔（秒）',exact=True)).to_have_value('3')
                    page.get_by_label('重试间隔（秒）',exact=True).fill('2')
                    page.locator('.a-sidebar').get_by_role('link',name='任务与调度',exact=True).click()
                    expect(page.locator('.v2-run')).to_have_count(1)
                    expect(page.locator('.v2-run')).to_contain_text('排队中')
                    page.locator('.v2-run').get_by_role('button',name='取消任务',exact=True).click()
                    page.locator('.a-confirm').get_by_role('button',name='取消任务',exact=True).click()
                    expect(page.locator('.v2-run')).to_contain_text('已取消')
                    page.locator('.v2-run').get_by_role('button',name='日志与进度',exact=True).click()
                    expect(page.get_by_role('log',name='任务执行日志')).to_contain_text('已取消排队')
                    expect(page.locator('.ops-config-details')).to_be_visible()
                    page.mouse.click(20,500)
                    expect(page.locator('.ops-task-drawer')).not_to_be_visible()
                    progress_job=admin('dispatch',workflow='favorites')['id']
                    def publish_progress(batch):
                        code="from backend import db,jobs;import logging;con=db.connect();c=con.__enter__();c.execute(\"UPDATE jobs SET status='in_progress' WHERE id=?\",("+str(progress_job)+",));c.execute(\"INSERT OR IGNORE INTO job_steps(job_id,name,status) VALUES (?,'favorites','in_progress')\",("+str(progress_job)+",));con.__exit__(None,None,None);h=jobs.Progress("+str(progress_job)+",'favorites');h.emit(logging.LogRecord('favorites',20,'',0,'开始获取元数据，共 4 批',(),None));h.emit(logging.LogRecord('favorites',20,'',0,'第 "+str(batch)+" 批成功，获取 25 条',(),None))"
                        subprocess.run([sys.executable,'-c',code],cwd=ROOT,env=env,check=True)
                    publish_progress(1)
                    page.get_by_role('button',name='刷新',exact=True).click()
                    page.locator('.ops-run').filter(has_text='#'+str(progress_job)).get_by_role('button',name='日志与进度').click()
                    expect(page.get_by_role('log',name='任务执行日志')).to_contain_text('元数据第 1 批完成')
                    publish_progress(2)
                    expect(page.get_by_role('log',name='任务执行日志')).to_contain_text('元数据第 2 批完成')
                    expect(page.locator('.ops-config-details')).to_have_count(0)
                    # Seed a long log in one subprocess so imports do not dominate this test.
                    subprocess.run([sys.executable,'-c',"from backend import jobs;[jobs.event("+str(progress_job)+",'favorites','元数据第 '+str(batch)+' 批完成') for batch in range(3,30)]"],cwd=ROOT,env=env,check=True)
                    page.locator('.ops-log-heading').get_by_role('button',name='刷新',exact=True).click()
                    expect(page.get_by_role('log')).to_contain_text('元数据第 29 批完成')
                    log_view=page.get_by_role('log')
                    log_view.evaluate('(el)=>{el.scrollTop=0;el.dispatchEvent(new Event("scroll"))}')
                    expect(page.get_by_label('跟随最新',exact=True)).not_to_be_checked()
                    publish_progress(30)
                    expect(log_view).to_contain_text('元数据第 30 批完成')
                    assert log_view.evaluate('(el)=>el.scrollTop')==0
                    page.get_by_label('跟随最新',exact=True).check()
                    page.wait_for_timeout(100)
                    assert log_view.evaluate('(el)=>el.scrollHeight-el.clientHeight-el.scrollTop')<3
                    # A completed task must preserve the reader's position across idle polls.
                    subprocess.run([sys.executable,'-c',"from backend import db;con=db.connect();c=con.__enter__();c.execute(\"UPDATE jobs SET status='completed',conclusion='success' WHERE id=?\",("+str(progress_job)+",));con.__exit__(None,None,None)"],cwd=ROOT,env=env,check=True)
                    log_view.evaluate('(el)=>{el.scrollTop=0;el.dispatchEvent(new Event("scroll"))}')
                    page.wait_for_timeout(4500)
                    assert log_view.evaluate('(el)=>el.scrollTop')==0
                    page.get_by_role('button',name='关闭任务详情').click()
                    for dark in (False,True):
                        page.locator('html').evaluate('(el,dark)=>el.classList.toggle("my-app-dark",dark)',dark)
                        for selector in ('.ops-launch','.ops-run-title'):
                            button=page.locator(selector).first
                            button.hover()
                            page.wait_for_timeout(200)
                            assert button.evaluate('''el=>{const sample=document.createElement('span');sample.style.backgroundColor='var(--a-soft)';el.append(sample);const expected=getComputedStyle(sample).backgroundColor;sample.remove();return getComputedStyle(el).backgroundColor===expected}''')
                    page.locator('html').evaluate('(el)=>el.classList.remove("my-app-dark")')
                    page.get_by_role('tab',name='每日调度').click()
                    hour=page.get_by_label('收藏同步执行小时',exact=True)
                    original_hour=hour.input_value()
                    hour.fill('7');hour.fill(original_hour)
                    expect(page.locator('.v2-schedules article').filter(has_text='收藏同步').get_by_role('button',name='已保存',exact=True)).to_be_disabled()
                    hour.fill('5')
                    page.locator('.v2-schedules article').filter(has_text='收藏同步').get_by_role('button',name='保存调度',exact=True).click()
                    expect(page.locator('.a-alert-success')).to_be_visible()
                    assert next(s for s in admin('schedules')['items'] if s['kind']=='favorites')['hour']==5
                    page.locator('.a-sidebar').get_by_role('link',name='备份与恢复',exact=True).click()
                    page.get_by_role('button',name='立即备份',exact=True).click()
                    expect(page.locator('.a-alert-success')).to_be_visible()
                    expect(page.get_by_role('link',name='下载数据库').first).to_be_visible()
                    await_sw="async()=>{await navigator.serviceWorker.ready;if(!navigator.serviceWorker.controller)await new Promise(resolve=>navigator.serviceWorker.addEventListener('controllerchange',resolve,{once:true}));return true}"
                    assert page.evaluate(await_sw)
                    before_download=page.url
                    with page.expect_download() as pending_download:
                        page.get_by_role('link',name='下载数据库').first.click()
                    downloaded=pending_download.value
                    assert downloaded.suggested_filename.endswith('.sqlite3')
                    with Path(downloaded.path()).open('rb') as backup_stream:
                        assert backup_stream.read(16)==b'SQLite format 3\x00'
                    assert page.url==before_download
                    # Also exercise a normal navigation, as in bookmarks and older clients.
                    page.get_by_role('link',name='下载数据库').first.evaluate('(el)=>el.removeAttribute("download")')
                    with page.expect_download() as pending_navigation:
                        page.get_by_role('link',name='下载数据库').first.click()
                    assert pending_navigation.value.suggested_filename==downloaded.suggested_filename
                    assert page.url==before_download
                    # Navigation fallback must not turn backend errors into the homepage.
                    probe=page.context.new_page()
                    response=probe.goto(BASE+'/api/not-a-real-api')
                    assert response.status==404 and 'application/json' in response.headers['content-type']
                    assert 'Not Found' in probe.locator('body').inner_text()
                    probe.close()

                    page.locator('.a-sidebar').get_by_role('link',name='账户与会话',exact=True).click()
                    page.get_by_label('当前密码',exact=True).fill(password)
                    new_password=secrets.token_urlsafe(24)
                    page.get_by_label('新密码',exact=True).fill(new_password)
                    page.get_by_label('再次输入新密码',exact=True).fill(new_password)
                    page.get_by_role('button',name='修改密码并退出全部设备',exact=True).click()
                    expect(page.get_by_label('管理密码',exact=True)).to_be_visible()
                    page.get_by_label('管理密码',exact=True).fill(new_password)
                    page.get_by_role('button',name='进入工作空间').click()
                    expect(page.get_by_role('heading',name='站点概览')).to_be_visible()
                    expect(page.locator('.ops-overview-hero')).to_be_visible()
                    page.screenshot(path='/tmp/nohentai-admin-v3-desktop.png',full_page=True)
                    page.set_viewport_size({'width':390,'height':844})
                    page.get_by_role('button',name='打开管理导航',exact=True).click()
                    page.locator('.a-nav-drawer').get_by_role('link',name='画廊',exact=True).click()
                    page.locator('.a-gallery-row').first.click()
                    expect(page.get_by_label('展示标题',exact=True)).to_be_visible()
                    assert page.evaluate('document.documentElement.scrollWidth <= innerWidth+1')
                    page.screenshot(path='/tmp/nohentai-admin-v3-mobile.png',full_page=True)
                    page.get_by_role('button',name='打开管理导航',exact=True).click()
                    page.locator('.a-nav-drawer').get_by_role('link',name='每日筛选',exact=True).click()
                    page.locator('.a-gallery-row').first.click()
                    expect(page.get_by_label('分组名称',exact=True)).to_be_visible()
                    expect(page.locator('.ops-rule-summary')).to_be_visible()
                    assert page.evaluate('document.documentElement.scrollWidth <= innerWidth+1')
                    page.screenshot(path='/tmp/nohentai-admin-daily-mobile.png',full_page=True)
                    page.get_by_role('button',name='打开管理导航',exact=True).click()
                    page.locator('.a-nav-drawer').get_by_role('link',name='任务与调度',exact=True).click()
                    first_tab=page.get_by_role('tab',name='运行记录')
                    expect(first_tab).to_have_attribute('aria-selected','true')
                    first_tab.focus();first_tab.press('ArrowRight')
                    expect(page.get_by_role('tab',name='每日调度')).to_have_attribute('aria-selected','true')
                    expect(page.get_by_role('tabpanel')).to_have_attribute('id','tasks-tabs-panel-schedules')
                    page.get_by_role('tab',name='每日调度').click()
                    page.screenshot(path='/tmp/nohentai-admin-tabs-mobile.png',full_page=True)
                    assert page.evaluate('document.documentElement.scrollWidth <= innerWidth+1')
                    page.get_by_role('button',name='打开管理导航',exact=True).click()
                    page.locator('.a-nav-drawer').get_by_role('button',name='退出管理',exact=True).click()
                    expect(page.get_by_label('管理密码',exact=True)).to_be_visible()
                    assert not errors, errors
                    browser.close()
                print('Browser smoke passed: homepage and all admin v3 flows, keyboard autocomplete, cover override, namespace tags, gallery linkage and live task events, cookie login, per-record saves, rollback, upload, scoped sync, cancellation, schedule, backup, password rotation and mobile navigation')
            finally:
                for process in reversed(processes):
                    process.terminate()
                for process in processes:
                    try:
                        process.wait(timeout=10)
                    except subprocess.TimeoutExpired:
                        process.kill()
                        process.wait()
                for path,owner in protected_owners.items():
                    assert (path.stat().st_uid,path.stat().st_gid,path.stat().st_mode)==owner,('test changed production temp directory',str(path))


if __name__ == '__main__':
    main()
