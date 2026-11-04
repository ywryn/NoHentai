"""Focused review regressions against built assets and mocked, delayed upstreams.
Run after npm --prefix web-static run build: .venv/bin/python tests/browser_review.py
All HTTP responses other than the local static build are fixtures; no production writes.
"""
import io
from functools import partial
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
import threading
from PIL import Image
from playwright.sync_api import sync_playwright, expect

ROOT = Path(__file__).resolve().parents[1]


class QuietHandler(SimpleHTTPRequestHandler):
    def log_message(self, *args):
        pass


def main():
    expect.set_options(timeout=15000)
    server = ThreadingHTTPServer(('127.0.0.1', 0), partial(QuietHandler, directory=str(ROOT/'web-static/dist')))
    threading.Thread(target=server.serve_forever, daemon=True).start()
    base = f'http://127.0.0.1:{server.server_port}'
    image = io.BytesIO(); Image.new('RGB',(600,900),'white').save(image,format='PNG')
    try:
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True)
            page = browser.new_page(service_workers='block', viewport={'width':1440,'height':1000})
            errors = []; page.on('pageerror', lambda error: errors.append(str(error)))
            page.route('**/api/gallery-images?*', lambda r:r.fulfill(json={'total':5,'images':[
                {'pageNum':i,'pageUrl':f'https://e-hentai.org/s/abcde/1-{i}','thumbSprite':'','thumbX':0,'thumbW':100,'thumbH':150} for i in range(1,6)]}))
            requests = []
            def image_url(route):
                requests.append(route.request.url)
                route.fulfill(json={'imageUrl':base+'/fixture.png?request='+str(len(requests)),'nlParam':None})
            page.route('**/api/image-url?*', image_url)
            fail_image = {'value':False}
            def picture(route):
                if fail_image['value']:
                    route.fulfill(status=502,body='image failed')
                else:
                    route.fulfill(content_type='image/png',body=image.getvalue())
            page.route('**/fixture.png*',picture)
            page.route('**/api/image-proxy?*',picture)
            page.route('**/api/trans-verify',lambda r:r.fulfill(json={'ok':True}))
            translated=[]
            def translate(route):
                translated.append(route.request.post_data_json)
                route.fulfill(json={'translations':[{'t':'CURRENT_TRANSLATION'}]})
            page.route('**/api/trans-translate',translate)
            page.route('**/data/translate-config.json',lambda r:r.fulfill(json={'defaultOcr':'google'}))
            page.route('**/api/galleries/1?*',lambda r:r.fulfill(json={'gallery':{'gid':'1','title':'FIRST_GALLERY','category':'Manga'},'tagDetails':[]}))
            page.route('**/api/galleries/2?*',lambda r:r.fulfill(status=404,json={'error':'not found'}))
            page.route('**/api/revision',lambda r:r.fulfill(json={'catalog':'v1'}))
            page.route('**/api/galleries?*',lambda r:r.fulfill(json={'items':[],'total':0,'totalAll':0,'page':1,'perPage':30,'categoryCounts':{},'totalCategoryCounts':{}}))
            page.route('**/api/tags/suggestions?*',lambda r:r.fulfill(json={'items':[]}))
            page.add_init_script("localStorage.setItem('reader-hint-seen','1');localStorage.setItem('reader-settings',JSON.stringify({readingMode:'scroll',pagesPerScreen:2,bookDirection:'ltr',pageTurnAnimation:'none'}))")
            page.goto(base+'/#/gallery/1/read?token=abcde&page=4')
            page.wait_for_function("document.querySelector('.scroll-view')?.scrollTop > 1000")
            expect(page.locator('.tb-counter')).to_have_text('4 / 5')
            page.get_by_role('button',name='页目录',exact=True).click()
            page.locator('.tg-item').nth(1).click()
            page.wait_for_function("Math.abs(document.querySelector('.scroll-page:nth-child(2)').getBoundingClientRect().top-document.querySelector('.scroll-view').getBoundingClientRect().top)<2")
            page.keyboard.press('ArrowRight')
            page.wait_for_function("Math.abs(document.querySelector('.scroll-page:nth-child(3)').getBoundingClientRect().top-document.querySelector('.scroll-view').getBoundingClientRect().top)<2")
            print('PASS: scroll reader initial page, directory, keyboard and asynchronous image resize alignment')

            pending=[]
            page.route('**/api/trans-ocr',lambda r:pending.append(r))
            page.goto(base+'/#/gallery/1/translate?token=abcde&page=1')
            page.get_by_placeholder('输入密码',exact=True).fill('fixture-password')
            page.get_by_role('button',name='进入',exact=True).click()
            expect(page.locator('.gt-page-img')).to_be_visible()
            page.get_by_role('button',name='翻译',exact=True).click()
            page.wait_for_function("document.querySelector('.gt-header').textContent.includes('识别中')")
            page.locator('.gt-thumb').nth(1).click()
            expect(page).to_have_url(base+'/#/gallery/1/translate?token=abcde&page=2')
            expect(page.locator('.gt-page-img')).to_be_visible()
            page.locator('.gt-thumb').nth(0).click()
            expect(page).to_have_url(base+'/#/gallery/1/translate?token=abcde&page=1')
            expect(page.locator('.gt-page-img')).to_be_visible()
            pending.pop(0).fulfill(json={'results':[{'text':'OLD_PAGE_OCR','confidence':1,'bbox':[10,10,100,100]}],'source':'vision'})
            page.wait_for_timeout(250)
            assert not page.evaluate("localStorage.getItem('trans_cache_1_p1') || localStorage.getItem('trans_cache_1_p2')")
            assert not translated
            page.get_by_role('button',name='翻译',exact=True).click()
            page.wait_for_function("document.querySelector('.gt-header').textContent.includes('识别中')")
            pending.pop(0).fulfill(json={'results':[{'text':'CURRENT_PAGE_OCR','confidence':1,'bbox':[10,10,100,100]}],'source':'vision'})
            page.wait_for_function("localStorage.getItem('trans_cache_1_p1')?.includes('CURRENT_TRANSLATION')")
            assert 'CURRENT_PAGE_OCR' in page.evaluate("localStorage.getItem('trans_cache_1_p1')")
            assert translated[0]['texts']==['CURRENT_PAGE_OCR']
            print('PASS: late OCR discarded after page 1 -> 2 -> 1; new request still translates and caches correctly')

            fail_image['value']=True
            page.goto(base+'/#/gallery/1/read?token=abcde&page=1')
            expect(page.locator('.pi-error:visible').first).to_be_visible()
            assert any('refresh=true' in url for url in requests)
            fail_image['value']=False
            page.locator('.pi-error:visible').first.get_by_role('button',name='重试',exact=True).click()
            expect(page.locator('.pi-img:visible').first).to_be_visible()
            assert 'refresh=true' in requests[-1]
            print('PASS: automatic and manual image retry bypass server URL cache without nl')

            page.goto(base+'/#/gallery/1')
            expect(page.get_by_role('heading',name='FIRST_GALLERY',exact=True)).to_be_visible()
            page.evaluate("location.hash='/gallery/2'")
            expect(page.locator('.gallery-detail-wrapper > .error')).to_be_visible()
            expect(page.get_by_role('heading',name='FIRST_GALLERY',exact=True)).to_have_count(0)
            print('PASS: failed detail navigation removes previous gallery and shows retry')
            page.goto(base+'/#/?q=female%3A%22sole%20female%24%22')
            expect(page.locator('.home-filter-chip')).to_have_count(1)
            page.locator('.home-filter-chip').click()
            expect(page.locator('.home-filter-chip')).to_have_count(0)
            expect(page.get_by_role('combobox',name='搜索画廊',exact=True)).to_have_value('')
            print('PASS: quoted multiword search chip can be removed')
            assert not errors, errors
            browser.close()
    finally:
        server.shutdown(); server.server_close()


if __name__ == '__main__':
    main()
