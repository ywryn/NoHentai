"""Modern Web Guidance regressions; local server and synthetic API fixtures only."""
from functools import partial
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
import json
import re
import threading
from playwright.sync_api import sync_playwright, expect

ROOT = Path(__file__).resolve().parents[1]

class Quiet(SimpleHTTPRequestHandler):
    def log_message(self, *args): pass

def main():
    server = ThreadingHTTPServer(('127.0.0.1', 0), partial(Quiet, directory=str(ROOT/'web-static/dist')))
    threading.Thread(target=server.serve_forever, daemon=True).start()
    base = f'http://127.0.0.1:{server.server_port}'
    output = Path('/tmp/nohentai-modern-guidance'); output.mkdir(exist_ok=True)
    fixtures = [{'gid':i,'title':f'城市漫游 · 插画集 第 {i} 卷 / Stories and sketches', 'category':'Manga', 'tags':[], 'tagLabels':['旅行'], 'filecount':128, 'rating':4, 'posted':1700000000} for i in range(1,7)]
    try:
        with sync_playwright() as pw:
            browser=pw.chromium.launch(headless=True)
            page=browser.new_page(service_workers='block',viewport={'width':1440,'height':900})
            errors=[];page.on('pageerror',lambda error: errors.append(str(error)))
            page.route('**/api/revision',lambda r:r.fulfill(json={'catalog':'modern'}))
            page.route('**/api/galleries?*',lambda r:r.fulfill(json={'items':fixtures,'total':6,'totalAll':6,'page':1,'perPage':30,'categoryCounts':{'Manga':6},'totalCategoryCounts':{'Manga':6}}))
            page.route('**/api/tags/suggestions?*',lambda r:r.fulfill(json={'items':[]}))
            page.route('**/api/gallery-images?*',lambda r:r.fulfill(json={'total':8,'images':[{'pageNum':i,'pageUrl':f'https://e-hentai.org/s/abcde/1-{i}','thumbSprite':'','thumbX':0,'thumbW':85,'thumbH':120} for i in range(1,9)]}))
            page.route('**/api/image-url?*',lambda r:r.fulfill(status=503,json={'error':'fixture unavailable'}))
            page.route('**/api/trans-verify',lambda r:r.fulfill(status=401,json={'error':'fixture invalid password'}))
            page.route('**/api/admin/session',lambda r:r.fulfill(status=401,json={}))
            page.add_init_script("localStorage.setItem('theme','light');localStorage.setItem('reader-settings',JSON.stringify({readingMode:'book',pagesPerScreen:1,bookDirection:'ltr',pageTurnAnimation:'flip'}))")
            page.goto(base+'/#/')
            expect(page.locator('.gallery-row')).to_have_count(6)
            expect(page.locator('.gallery-row input')).to_have_count(0)
            expect(page.get_by_role('img',name='评分 4，满分 5')).to_have_count(6)
            expect(page.locator('.gallery-row button,.gallery-row a')).to_have_count(0)
            # A desktop-hosted narrow panel must behave like a narrow component.
            page.locator('.gallery-results').evaluate("e=>e.style.width='380px'")
            assert page.locator('.gr-title').first.evaluate("e=>getComputedStyle(e).webkitLineClamp")=='2'
            page.screenshot(path=str(output/'narrow-desktop-component.png'))
            page.locator('.gallery-results').evaluate("e=>e.style.width=''")
            page.set_viewport_size({'width':320,'height':844})
            page.get_by_role('button',name='切换为封面视图',exact=True).click()
            expect(page.locator('.vm-cover-card')).to_have_count(6)
            grid=page.locator('.vm-cover-grid')
            assert grid.evaluate("e=>getComputedStyle(e).gridTemplateColumns.split(' ').length")==2
            assert page.evaluate('document.documentElement.scrollWidth<=innerWidth')
            page.screenshot(path=str(output/'cover-320.png'))
            print('PASS: static rating semantics, no form controls nested in links, component queries, 320px two-column covers')

            page.set_viewport_size({'width':1024,'height':700})
            page.goto(base+'/#/gallery/1/read?token=abcde')
            opener=page.get_by_role('button',name='页目录',exact=True)
            opener.click()
            modal=page.locator('dialog.tg-overlay')
            expect(modal).to_be_visible()
            assert modal.evaluate("e=>e.matches(':modal')")
            expect(page.get_by_role('spinbutton',name='跳转页码')).to_be_focused()
            page.locator('.tg-item').last.focus()
            page.keyboard.press('Tab')
            # Native modals may allow the browser chrome between the last and first control.
            assert page.evaluate("document.activeElement===document.body||document.querySelector('dialog').contains(document.activeElement)")
            if not page.get_by_role('spinbutton',name='跳转页码').evaluate('e=>e===document.activeElement'):
                page.keyboard.press('Tab')
            expect(page.get_by_role('spinbutton',name='跳转页码')).to_be_focused()
            page.locator('.tb-settings').evaluate('e=>e.focus()')
            assert modal.evaluate('e=>e.contains(document.activeElement)')
            page.keyboard.press('Escape')
            expect(modal).to_have_count(0)
            expect(opener).to_be_focused()
            opener.click()
            # Exercise the manual fallback used where closedby is unavailable.
            page.evaluate("delete HTMLDialogElement.prototype.closedBy;document.querySelector('dialog').removeAttribute('closedby')")
            rect=modal.bounding_box()
            page.mouse.click(rect['x']+8,rect['y']+3)
            expect(modal).to_be_visible()
            page.mouse.move(8,8);page.mouse.down();page.mouse.move(rect['x']+8,rect['y']+3);page.mouse.up()
            expect(modal).to_be_visible()
            page.mouse.click(8,8)
            expect(modal).to_have_count(0)
            expect(opener).to_be_focused()
            print('PASS: native modal focus containment/return, Escape and safe light-dismiss fallback')

            page.emulate_media(reduced_motion='reduce')
            page.keyboard.press('ArrowRight')
            expect(page.locator('.tb-counter')).to_have_text('2 / 8')
            assert page.evaluate("[...document.querySelectorAll('.spread')].every(e=>e.getAnimations().every(a=>!a.effect.getKeyframes().some(k=>k.transform&&k.transform!=='none')))")
            assert page.evaluate("JSON.parse(localStorage.getItem('reader-settings')).pageTurnAnimation")=='flip'
            # Changing back must retain the saved animation choice.
            page.emulate_media(reduced_motion='no-preference')
            page.keyboard.press('ArrowRight')
            expect(page.locator('.tb-counter')).to_have_text('3 / 8')
            page.emulate_media(reduced_motion='reduce')
            assert page.locator('.reader-btn').first.evaluate("e=>getComputedStyle(e).transitionDuration")!='1e-05s'
            print('PASS: live reduced-motion changes preserve reader settings and page navigation')

            page.goto(base+'/#/gallery/1/translate?token=abcde')
            password=page.get_by_label('翻译访问密码')
            password.fill('fixture-invalid')
            password.press('Enter')
            expect(page.locator('#translate-access-error')).to_be_visible()
            expect(password).to_have_attribute('aria-invalid','true')
            expect(password).to_have_attribute('aria-describedby','translate-access-error')
            page.goto(base+'/#/admin/overview')
            expect(page.get_by_role('heading',name='登录管理后台')).to_be_visible()
            expect(page.locator('main')).to_have_count(1)
            print('PASS: translator native form validation and single admin main landmark')

            axe=Path('/tmp/nohentai-axe.min.js')
            if axe.exists():
                reports=[]
                for route,theme in [('/', 'light'),('/', 'dark'),('/admin/overview','light'),('/admin/overview','dark')]:
                    page.goto(base+'/#'+route)
                    page.wait_for_selector('.gallery-results a' if route=='/' else '.a-login-form')
                    page.evaluate("t=>document.documentElement.className='my-app-'+t",theme)
                    page.add_script_tag(path=str(axe))
                    result=page.evaluate("async()=>await axe.run(document,{runOnly:{type:'tag',values:['wcag2a','wcag2aa','wcag21aa','wcag22aa']}})")
                    reports.append({'route':route,'theme':theme,'violations':result['violations'],'incomplete':len(result['incomplete'])})
                (output/'axe-report.json').write_text(json.dumps(reports,ensure_ascii=False,indent=2))
                serious=[(r['route'],v['id']) for r in reports for v in r['violations'] if v['impact'] in ['serious','critical']]
                assert not serious,serious
                print('PASS: axe checks; report saved with any remaining minor/moderate findings')
            else:
                print('SKIP: axe checks require /tmp/nohentai-axe.min.js')
            page.emulate_media(forced_colors='active')
            page.goto(base+'/#/')
            expect(page.locator('.gallery-results')).to_be_visible()
            assert page.locator('.nav-menu [aria-current=page]').evaluate("e=>getComputedStyle(e).outlineStyle")=='solid'
            page.screenshot(path=str(output/'forced-colors.png'))
            page.emulate_media(forced_colors='none')
            print('PASS: forced-color system palette and visible active-navigation boundary')
            # Native sheet must remain usable in a short mobile viewport.
            touch=browser.new_page(service_workers='block',viewport={'width':320,'height':420},is_mobile=True,has_touch=True)
            touch.route('**/api/gallery-images?*',lambda r:r.fulfill(json={'total':1,'images':[{'pageNum':1,'pageUrl':'https://e-hentai.org/s/abcde/1-1','thumbSprite':'','thumbX':0,'thumbW':85,'thumbH':120}]}))
            touch.route('**/api/image-url?*',lambda r:r.fulfill(status=503,json={'error':'fixture unavailable'}))
            touch.goto(base+'/#/gallery/1/read?token=abcde')
            touch.get_by_role('button',name='页目录',exact=True).click()
            sheet=touch.locator('dialog.tg-overlay').bounding_box()
            assert sheet['height']<=420*.75+1 and sheet['y']+sheet['height']<=421
            assert touch.get_by_role('button',name='关闭页目录').bounding_box()['height']>=44
            touch.screenshot(path=str(output/'directory-mobile-short.png'))
            touch.close()
            print('PASS: short mobile directory and 44px coarse-pointer close control')
            assert not errors,errors
            browser.close()
    finally:
        server.shutdown();server.server_close()

if __name__=='__main__':main()
