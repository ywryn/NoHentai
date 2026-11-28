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
            page.route('**/api/gallery-images/part?*',lambda r:r.fulfill(json={'total':8,'images':[{'pageNum':i,'pageUrl':f'https://e-hentai.org/s/abcde/1-{i}','thumbSprite':'','thumbX':0,'thumbW':85,'thumbH':120} for i in range(1,9)]}))
            page.route('**/api/page-image?*',lambda r:r.fulfill(status=503,json={'error':'fixture unavailable'}))
            page.route('**/api/trans-verify',lambda r:r.fulfill(status=401,json={'error':'fixture invalid password'}))
            page.route('**/api/admin/session',lambda r:r.fulfill(status=401,json={}))
            page.add_init_script("localStorage.setItem('theme','light');if(!localStorage.getItem('reader-settings'))localStorage.setItem('reader-settings',JSON.stringify({readingMode:'book',pagesPerScreen:1,bookDirection:'ltr',pageTurnAnimation:'flip'}))")
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
            page.get_by_role('button',name='页面导航').click()
            page.get_by_role('button',name='切换为封面视图',exact=True).click()
            page.keyboard.press('Escape')
            expect(page.locator('.vm-cover-card')).to_have_count(6)
            assert page.evaluate('document.documentElement.scrollWidth<=innerWidth')
            page.screenshot(path=str(output/'cover-320.png'))
            # Two 132px cover tracks plus the gap require 278px of content width.
            page.set_viewport_size({'width':360,'height':844})
            grid=page.locator('.vm-cover-grid')
            page.wait_for_function("e=>getComputedStyle(e).gridTemplateColumns.split(' ').length===2", arg=grid.element_handle())
            print('PASS: static rating semantics, component queries, 320px overflow and two columns when they fit')

            page.set_viewport_size({'width':1024,'height':700})
            page.goto(base+'/#/gallery/1/read?token=abcde')
            opener = page.locator('.top-bar').get_by_role('button', name='缩略图栏', exact=True)
            capsule = page.locator('.reader-reveal')
            opener.click()
            sidebar = page.locator('.thumb-sidebar')
            expect(sidebar).to_be_visible()
            expect(opener).to_have_attribute('aria-pressed', 'true')
            expect(capsule).to_have_attribute('aria-pressed', 'true')
            palette = sidebar.evaluate("""sidebar => {
                const colors = getComputedStyle(sidebar)
                const list = getComputedStyle(sidebar.querySelector('.ts-list'))
                return [document.documentElement.classList.contains('my-app-light'),
                    colors.backgroundColor, list.scrollbarColor]
            }""")
            assert palette == [True, 'rgb(16, 19, 18)', 'rgb(148, 163, 184) rgb(16, 19, 18)'], palette
            jump = page.get_by_role('spinbutton', name='跳转页码')
            jump.focus()
            page.keyboard.press('Tab')
            expect(sidebar.get_by_role('button', name='跳转', exact=True)).to_be_focused()
            assert jump.evaluate("e=>{e.focus();return getComputedStyle(e).outlineStyle==='solid'}")
            page.keyboard.press('Escape')
            expect(sidebar).to_have_count(0)
            expect(capsule).to_be_focused()
            capsule.click()
            expect(sidebar).to_be_visible()
            page.keyboard.press('F')
            expect(sidebar).to_have_count(0)
            print('PASS: nonmodal thumbnail sidebar keyboard controls, focus return and dark scrollbar on light theme')

            page.get_by_role('button', name='阅读设置').click()
            page.get_by_label('翻页动画').select_option('fade')
            page.reload()
            page.get_by_role('button', name='阅读设置').click()
            expect(page.get_by_label('翻页动画')).to_have_value('fade')
            page.get_by_role('button', name='阅读设置').click()
            page.evaluate("""() => {
                window.readerTransitions = []
                document.addEventListener('transitionrun', event => {
                    if (event.target.matches('.spread')) {
                        window.readerTransitions.push([event.propertyName, String(event.target.className)])
                    }
                })
            }""")
            page.keyboard.press('ArrowRight')
            expect(capsule).to_have_text('2 / 8')
            page.wait_for_function("readerTransitions.some(([property, classes]) => property === 'opacity' && classes.includes('fade-enter-active'))")
            page.emulate_media(reduced_motion='reduce')
            page.wait_for_function("!document.querySelector('.fade-enter-active,.fade-leave-active')")
            page.evaluate('readerTransitions.length = 0')
            page.keyboard.press('ArrowRight')
            expect(capsule).to_have_text('3 / 8')
            page.evaluate("new Promise(resolve => requestAnimationFrame(() => requestAnimationFrame(resolve)))")
            assert page.evaluate('readerTransitions.length') == 0
            assert page.evaluate("JSON.parse(localStorage.getItem('reader-settings')).pageTurnAnimation") == 'fade'
            assert page.locator('.reader-btn').first.evaluate("e=>getComputedStyle(e).transitionDuration") != '1e-05s'
            print('PASS: fade persists after reload, animates opacity and honors live reduced-motion preference')

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
            # Keep thumbnail controls accessible in a short mobile viewport.
            touch=browser.new_page(service_workers='block',viewport={'width':320,'height':420},is_mobile=True,has_touch=True)
            touch.route('**/api/gallery-images/part?*',lambda r:r.fulfill(json={'total':1,'images':[{'pageNum':1,'pageUrl':'https://e-hentai.org/s/abcde/1-1','thumbSprite':'','thumbX':0,'thumbW':85,'thumbH':120}]}))
            touch.route('**/api/page-image?*',lambda r:r.fulfill(status=503,json={'error':'fixture unavailable'}))
            touch.goto(base+'/#/gallery/1/read?token=abcde')
            touch.locator('.top-bar').get_by_role('button', name='缩略图栏', exact=True).click()
            assert touch.get_by_role('button', name='跳转', exact=True).bounding_box()['height'] >= 48
            expect(touch.get_by_role('spinbutton', name='跳转页码')).to_be_visible()
            touch.get_by_role('button', name='阅读设置', exact=True).click()
            settings = touch.locator('.tb-controls').bounding_box()
            position = touch.locator('.reader-reveal').bounding_box()
            assert position['y'] >= settings['y'] + settings['height']
            assert position['y'] + position['height'] <= 421
            touch.screenshot(path=str(output/'thumbnails-mobile-short.png'))
            touch.close()
            print('PASS: short mobile thumbnail controls, 48px submit and no settings overlap')
            assert not errors,errors
            browser.close()
    finally:
        server.shutdown();server.server_close()

if __name__=='__main__':main()
