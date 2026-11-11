"""Responsive layout and intermediate-state regressions; fixture-only, no production writes.
Run after building: .venv/bin/python tests/browser_layout.py
Screenshots are saved under /tmp/nohentai-ui-layout.
"""
from functools import partial
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
import threading
from urllib.parse import parse_qs, urlsplit
from playwright.sync_api import sync_playwright, expect

ROOT = Path(__file__).resolve().parents[1]
class Quiet(SimpleHTTPRequestHandler):
    def log_message(self, *args): pass

def main():
    server = ThreadingHTTPServer(('127.0.0.1', 0), partial(Quiet, directory=str(ROOT/'web-static/dist')))
    threading.Thread(target=server.serve_forever, daemon=True).start()
    base = f'http://127.0.0.1:{server.server_port}'
    output = Path('/tmp/nohentai-ui-layout'); output.mkdir(exist_ok=True)
    galleries = [{'gid':i,'title':f'城市漫游 · 插画集 第 {i} 卷 / A collection of stories and sketches',
                  'category':'Manga','tags':[],'tagLabels':['插画','旅行'],'filecount':128,
                  'thumb':'/missing-cover.jpg','rating':4,'posted':1700000000} for i in range(1,31)]
    mode = {'value':'ready'}; pending=[]
    def catalog(r):
        if mode['value']=='loading': pending.append(r); return
        if mode['value']=='error': r.fulfill(status=503,json={'error':'暂时无法加载'}); return
        params=parse_qs(urlsplit(r.request.url).query)
        r.fulfill(json={'items':[] if mode['value']=='empty' else galleries,'total':0 if mode['value']=='empty' else 90,
                       'totalAll':90,'page':int(params.get('page',['1'])[0]),'perPage':30,
                       'categoryCounts':{'Manga':90},'totalCategoryCounts':{'Manga':90}})
    def admin(r):
        action=r.request.post_data_json['action']
        if action=='records': r.fulfill(json={'items':[{'id':str(g['gid']),'version':'0','data':{},'source':g,'effective':g} for g in galleries],'page':1,'pages':1,'total':30})
        elif action=='record': r.fulfill(json={'id':'1','version':'0','data':{},'source':galleries[0],'effective':galleries[0]})
        else: r.fulfill(json={})
    try:
        with sync_playwright() as p:
            browser=p.chromium.launch(headless=True)
            page=browser.new_page(service_workers='block');page.set_default_timeout(20000)
            errors=[];page.on('pageerror',lambda e:errors.append(str(e)))
            page.route('**/api/galleries?*',catalog)
            page.route('**/api/revision',lambda r:r.fulfill(json={'catalog':'layout'}))
            page.route('**/api/tags/suggestions?*',lambda r:r.fulfill(json={'items':[]}))
            page.route('**/missing-cover.jpg',lambda r:r.fulfill(status=404,body=''))
            page.route('**/api/admin/session',lambda r:r.fulfill(json={'session':{'csrf':'fixture'}}))
            page.route('**/api/admin',admin)
            for theme in ['light','dark']:
                for width in [360,600,768,1024,1440]:
                    page.set_viewport_size({'width':width,'height':900})
                    page.goto(base+'/#/');expect(page.locator('.gallery-row')).to_have_count(30)
                    page.evaluate('(t)=>{document.documentElement.classList.toggle("my-app-dark",t==="dark");document.documentElement.classList.toggle("my-app-light",t==="light")}',theme)
                    assert page.evaluate('document.documentElement.scrollWidth <= innerWidth'),(theme,width,'overflow')
                    if width<=600:
                        box=page.get_by_role('combobox',name='搜索画廊').bounding_box()
                        assert box['width']>width*.65,(width,box)
                    assert page.locator('.pag-nav').first.bounding_box()['height']>=44
                    page.screenshot(path=str(output/f'catalog-{theme}-{width}.png'))
            for width in [390,768,1440]:
                page.set_viewport_size({'width':width,'height':900})
                page.get_by_role('button',name='切换为封面视图',exact=True).click()
                expect(page.locator('.vm-cover-card')).to_have_count(30)
                assert page.evaluate('document.documentElement.scrollWidth <= innerWidth'),('cover',width)
                page.screenshot(path=str(output/f'cover-{width}.png'))
                page.get_by_role('button',name='切换为列表视图',exact=True).click()
            page.set_viewport_size({'width':390,'height':844})
            page.locator('.home-filter-btn').click();expect(page.locator('.home-filter-btn')).to_have_attribute('aria-expanded','true')
            page.keyboard.press('Escape');expect(page.locator('.home-filter-btn')).to_have_attribute('aria-expanded','false')
            page.get_by_role('button',name='下一页',exact=True).first.click();expect(page).to_have_url(base+'/#/?page=2')
            page.go_back();expect(page).to_have_url(base+'/#/')
            jump=page.locator('.pag-jump-input').first;jump.fill('3');page.locator('.catalog-title').click();expect(page).to_have_url(base+'/#/')
            jump.fill('999');jump.press('Enter');expect(page).to_have_url(base+'/#/?page=3');expect(jump).to_have_value('3')
            for state in ['loading','empty','error']:
                mode['value']=state
                page.goto(base+'/#/?q='+state)
                if state=='loading':
                    expect(page.locator('.sk-card').first).to_be_visible();expect(page.locator('.home-content-panel')).to_have_attribute('aria-busy','true')
                elif state=='empty': expect(page.locator('.empty-state')).to_be_visible()
                else:
                    expect(page.locator('.catalog-error')).to_be_visible();expect(page.locator('.empty-state')).to_have_count(0)
                page.screenshot(path=str(output/f'{state}.png'))
                for r in pending:
                    try:r.fulfill(json={'items':[],'total':0,'totalAll':0,'page':1,'perPage':30,'categoryCounts':{},'totalCategoryCounts':{}})
                    except Exception:pass
                pending.clear()
            mode['value']='ready';page.get_by_role('button',name='重新加载',exact=True).click();expect(page.locator('.gallery-row')).to_have_count(30)
            for width in [360,768,1024,1440]:
                page.set_viewport_size({'width':width,'height':900})
                page.goto(base+'/#/admin/galleries');expect(page.locator('.a-master-list')).to_be_visible()
                assert page.evaluate('document.documentElement.scrollWidth <= innerWidth'),('admin',width,'overflow')
                footer=page.locator('.a-pagination').bounding_box()
                assert footer['y']+footer['height'] <= 900,('admin footer',width,footer)
                page.screenshot(path=str(output/f'admin-{width}.png'))
            assert not errors,errors
            browser.close()
            print('PASS: 10 theme/viewport layouts, touch targets, pagination history and jump, popover state, loading/empty/error/retry, 4 admin layouts')
    finally:server.shutdown();server.server_close()

if __name__=='__main__': main()
