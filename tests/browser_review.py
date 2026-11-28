"""Focused review regressions against built assets and mocked, delayed upstreams.
Run after npm --prefix web-static run build: .venv/bin/python tests/browser_review.py
All HTTP responses other than the local static build are fixtures; no production writes.
"""
import io
from functools import partial
import re
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
import threading
from urllib.parse import parse_qs, urlsplit
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
            def gallery_directory(route):
                route.fulfill(json={'total':5,'images':[
                    {'pageNum':i,'pageUrl':f'https://e-hentai.org/s/abcde/1-{i}','thumbSprite':'','thumbX':0,'thumbW':100,'thumbH':150} for i in range(1,6)]})
            page.route('**/api/gallery-images/part?*', gallery_directory)
            requests = []
            fail_image = {'value': False}
            image_version = {'value': '"fixture"'}
            def picture(route):
                requests.append(route.request.headers.get('x-page-image-refresh'))
                if fail_image['value']:
                    route.fulfill(content_type='image/png', body=b'not an image')
                else:
                    route.fulfill(content_type='image/png', headers={'ETag': image_version['value']}, body=image.getvalue())
            page.route('**/api/page-image?*', picture)
            authorized = False
            def verify(route):
                nonlocal authorized
                authorized = authorized or bool(route.request.post_data_json.get('password'))
                route.fulfill(status=200 if authorized else 401, json={'ok': authorized})
            page.route('**/api/trans-verify', verify)
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
            expect(page.locator('.reader-reveal')).to_have_text('4 / 5')
            page.screenshot(path='/tmp/nohentai-ui/reader-desktop.png')
            page.locator('.top-bar').get_by_role('button', name='缩略图栏', exact=True).click()
            page.locator('.ts-item').nth(1).click()
            page.wait_for_function("Math.abs(document.querySelector('.scroll-page:nth-child(2)').getBoundingClientRect().top-document.querySelector('.scroll-view').getBoundingClientRect().top)<2")
            page.keyboard.press('ArrowRight')
            page.wait_for_function("Math.abs(document.querySelector('.scroll-page:nth-child(3)').getBoundingClientRect().top-document.querySelector('.scroll-view').getBoundingClientRect().top)<2")
            print('PASS: scroll reader initial page, directory, keyboard and asynchronous image resize alignment')

            spread = browser.new_page(service_workers='block', viewport={'width':1440,'height':1000})
            spread.route('**/api/gallery-images/part?*', gallery_directory)
            spread.add_init_script("localStorage.setItem('reader-hint-seen','1');localStorage.setItem('reader-settings',JSON.stringify({readingMode:'book',pagesPerScreen:2}))")
            requested_pages = []
            held_images = {}
            def spread_image(route):
                url = urlsplit(route.request.url)
                number = int(parse_qs(url.query)['pageUrl'][0].rsplit('-', 1)[1])
                requested_pages.append(number)
                if number in (1, 3) and number not in held_images:
                    held_images[number] = route
                else:
                    picture(route)
            spread.route('**/api/page-image?*', spread_image)
            spread.goto(base+'/#/gallery/1/read?token=abcde')
            expect(spread.get_by_alt_text('第 2 页', exact=True)).to_be_visible()
            expect(spread.locator('.reader-reveal')).to_have_text('1 / 5')
            spread.get_by_role('button', name='阅读设置', exact=True).click()
            gutter = spread.locator('.tb-controls').bounding_box()
            capsule = spread.locator('.reader-reveal').bounding_box()
            assert capsule['y'] >= gutter['y'] + gutter['height']
            spread.get_by_role('button', name='阅读设置', exact=True).click()
            assert set(requested_pages) == {1, 2}, requested_pages
            with spread.expect_response(lambda response:
                    urlsplit(response.url).path == '/api/page-image'
                    and parse_qs(urlsplit(response.url).query)['pageUrl'][0].endswith('-4')):
                picture(held_images[1])
                for _ in range(50):
                    if 3 in held_images:
                        break
                    spread.wait_for_timeout(50)
                assert 3 in held_images, requested_pages
                spread.keyboard.press('ArrowLeft')
            expect(spread.get_by_alt_text('第 4 页', exact=True)).to_be_visible()
            assert set(requested_pages) == {1, 2, 3, 4}, requested_pages
            assert requested_pages.count(3) == 1, requested_pages
            picture(held_images[3])
            expect(spread.get_by_alt_text('第 3 页', exact=True)).to_be_visible()
            expect(spread.locator('.reader-reveal')).to_have_text('3 / 5')
            spread.locator('.click-zone-center').click()
            expect(spread.locator('.reader-reveal')).to_be_hidden()
            spread.locator('.click-zone-center').click()
            expect(spread.locator('.reader-reveal')).to_be_visible()
            spread.close()
            print('PASS: double-page reader defers preloading and reuses the in-flight image after turning')

            retry_page = browser.new_page(service_workers='block', viewport={'width':800,'height':1000})
            retry_page.add_init_script("localStorage.setItem('reader-hint-seen','1')")
            directory_refreshes = []
            def retry_directory(route):
                refreshed = parse_qs(urlsplit(route.request.url).query).get('refresh') == ['true']
                directory_refreshes.append(refreshed)
                route.fulfill(json={'total': 1, 'images': [
                    {'pageNum': 1, 'pageUrl': f'https://e-hentai.org/s/{"fresh" if refreshed else "stale"}/1-1',
                     'thumbSprite': '', 'thumbX': 0, 'thumbW': 100, 'thumbH': 150}]})
            def retry_picture(route):
                url = parse_qs(urlsplit(route.request.url).query)['pageUrl'][0]
                if '/stale/' in url:
                    route.fulfill(status=404, json={'code': 'page_unavailable', 'error': '上游图片页面不可访问'})
                else:
                    picture(route)
            retry_page.route('**/api/gallery-images/part?*', retry_directory)
            retry_page.route('**/api/page-image?*', retry_picture)
            retry_page.goto(base+'/#/gallery/1/read?token=abcde')
            expect(retry_page.locator('.pi-error')).to_contain_text('上游图片页面不可访问')
            retry_page.get_by_role('button', name='重试', exact=True).click()
            expect(retry_page.get_by_alt_text('第 1 页', exact=True)).to_be_visible()
            assert directory_refreshes == [False, True], directory_refreshes
            retry_page.close()
            print('PASS: retry refreshes the directory when the saved image page is unavailable')

            for status in (429, 509):
                limited = browser.new_page(service_workers='block', viewport={'width':800,'height':1000})
                limited.clock.install()
                limited.add_init_script("localStorage.setItem('reader-hint-seen','1');localStorage.setItem('reader-settings',JSON.stringify({pagesPerScreen:1}))")
                limited.route('**/api/gallery-images/part?*', gallery_directory)
                requested = []
                def limited_picture(route):
                    url = parse_qs(urlsplit(route.request.url).query)['pageUrl'][0]
                    number = int(url.rsplit('-', 1)[1])
                    requested.append(number)
                    if number == 1 and route.request.headers.get('x-page-image-refresh') != '1':
                        route.fulfill(status=status, json={'error': '暂时无法加载'})
                    else:
                        picture(route)
                limited.route('**/api/page-image?*', limited_picture)
                limited.goto(base+'/#/gallery/1/read?token=abcde')
                expect(limited.locator('.spread:visible .pi-error')).to_contain_text('暂时无法加载')
                limited.keyboard.press('ArrowLeft')
                expect(limited.get_by_alt_text('第 2 页', exact=True)).to_be_visible()
                limited.wait_for_timeout(100)
                assert requested == [1, 2], requested
                if status == 429:
                    limited.clock.fast_forward(61_000)
                    limited.keyboard.press('ArrowLeft')
                    expect(limited.get_by_alt_text('第 3 页', exact=True)).to_be_visible()
                    for _ in range(40):
                        if 4 in requested:
                            break
                        limited.wait_for_timeout(50)
                    assert 4 in requested, requested
                else:
                    limited.keyboard.press('ArrowRight')
                    expect(limited.locator('.spread:visible .pi-error')).to_contain_text('暂时无法加载')
                    assert requested == [1, 2], requested
                    limited.get_by_role('button', name='重试', exact=True).click()
                    expect(limited.get_by_alt_text('第 1 页', exact=True)).to_be_visible()
                    for _ in range(40):
                        if 3 in requested:
                            break
                        limited.wait_for_timeout(50)
                    assert 3 in requested, requested
                limited.close()
            print('PASS: page-image quota and rate limits suspend background preloads across page turns')

            touch = browser.new_page(has_touch=True, is_mobile=True, viewport={'width':390,'height':844})
            touch.route('**/api/gallery-images/part?*', lambda r:r.fulfill(json={'total':2,'images':[
                {'pageNum':i,'pageUrl':str(i),'thumbSprite':'','thumbX':0,'thumbW':100,'thumbH':150}
                for i in (1,2)]}))
            touch.route('**/api/page-image?*', picture)
            for mode in ('book','scroll'):
                touch.goto(base+'/#/gallery/1/read?token=abcde')
                touch.evaluate("mode=>localStorage.setItem('reader-settings',JSON.stringify({readingMode:mode,pagesPerScreen:1}))",mode)
                touch.reload()
                img = touch.locator('.pi-img:visible').first
                expect(img).to_be_visible()
                settings = touch.get_by_role('button',name='阅读设置')
                settings.tap()
                privacy = touch.get_by_role('switch',name='妈妈模式')
                privacy.tap()
                expect(privacy).to_be_checked()
                expect(img).to_have_css('filter',touch.evaluate("'blur('+getComputedStyle(document.documentElement).getPropertyValue('--mom-mode-blur').trim()+')'"))
                touch.reload()
                settings.tap()
                expect(privacy).to_be_checked()
                privacy.tap()
                expect(img).to_have_css('filter','none')
                settings.tap()
                box = img.bounding_box()
                x, y = int(box['x']+box['width']*.15), int(box['y']+box['height']*.5)
                touch.evaluate("""() => {
                    window.zoomAnimations = []
                    const animate = Element.prototype.animate
                    Element.prototype.animate = function(frames, options) {
                      if (this.matches('.reader-zoom img')) window.zoomAnimations.push(options.duration)
                      return animate.call(this,frames,options)
                    }
                }""")
                if mode == 'book':
                    expect(touch.locator('.click-zone-center')).to_have_css('-webkit-tap-highlight-color','rgba(0, 0, 0, 0)')
                previous_scale = 1
                for step in (1,2,3):
                    touch.touchscreen.tap(x,y)
                    touch.touchscreen.tap(x,y)
                    if step == 3:
                        expect(touch.locator('.reader-zoom')).to_have_count(0)
                    else:
                        overlay = touch.locator('.reader-zoom img')
                        expect(overlay).to_be_visible()
                        scale = float(re.search(r'scale\(([^)]+)',overlay.get_attribute('style'))[1])
                        assert scale > previous_scale
                        previous_scale = scale
                assert touch.evaluate('window.zoomAnimations') == [300,300,300]
                expect(touch.locator('.reader-reveal')).to_have_text('1 / 2')
            touch.close()
            print('PASS: mobile edge double taps cycle zoom without turning the page in both reading modes')


            pending=[]
            page.route('**/api/trans-ocr',lambda r:pending.append(r))
            page.goto(base+'/#/gallery/1/translate?token=abcde&page=1')
            page.get_by_placeholder('输入密码',exact=True).fill('fixture-password')
            page.get_by_role('button',name='进入',exact=True).click()
            expect(page.locator('.gt-page-img')).to_be_visible()
            page.get_by_role('button',name='识别并翻译',exact=True).click()
            page.wait_for_function("document.querySelector('.gt-header').textContent.includes('识别中')")
            page.locator('.gt-thumb').nth(1).click()
            expect(page).to_have_url(base+'/#/gallery/1/translate?token=abcde&page=2')
            expect(page.locator('.gt-page-img')).to_be_visible()
            page.locator('.gt-thumb').nth(0).click()
            expect(page).to_have_url(base+'/#/gallery/1/translate?token=abcde&page=1')
            expect(page.locator('.gt-page-img')).to_be_visible()
            pending.pop(0).fulfill(json={'results':[{'text':'OLD_PAGE_OCR','confidence':1,'bbox':[10,10,100,100]}],'source':'vision'})
            page.wait_for_timeout(250)
            assert not page.evaluate("localStorage.getItem('translate-drafts:v2')")
            assert not translated
            page.get_by_role('button',name='识别并翻译',exact=True).click()
            page.wait_for_function("document.querySelector('.gt-header').textContent.includes('识别中')")
            pending.pop(0).fulfill(json={'results':[{'text':'CURRENT_PAGE_OCR','confidence':1,'bbox':[10,10,100,100]}],'source':'vision'})
            page.wait_for_function("localStorage.getItem('translate-drafts:v2')?.includes('CURRENT_TRANSLATION')")
            assert 'CURRENT_PAGE_OCR' in page.evaluate("localStorage.getItem('translate-drafts:v2')")
            assert translated[0]['texts']==['CURRENT_PAGE_OCR']
            print('PASS: late OCR discarded after page 1 -> 2 -> 1; new request still translates and caches correctly')
            page.set_viewport_size({'width':390,'height':844})
            page.locator('.gt-ocr-box').first.click()
            expect(page.locator('.gt-bubble-card')).to_be_visible()
            sheet_button=page.get_by_role('button',name='识别结果面板',exact=True)
            sheet_button.focus();page.keyboard.press('Space')
            expect(page.locator('.gt-sidebar')).to_have_class(re.compile(r'is-half'))
            sheet_button.press('Enter')
            expect(page.locator('.gt-sidebar')).to_have_class(re.compile(r'is-full'))
            sheet_button.press('Enter')
            expect(page.locator('.gt-sidebar')).to_have_class(re.compile(r'is-peek'))
            page.screenshot(path='/tmp/nohentai-ui/translator-mobile.png')
            page.locator('.gt-bubble-card').get_by_role('button',name='编辑译文',exact=True).click()
            expect(page.locator('.gt-result-edit textarea')).to_be_visible()
            expect(page.locator('.gt-sidebar')).to_have_class(re.compile(r'is-full'))
            print('PASS: mobile translated bubble opens its own editor')
            page.set_viewport_size({'width':1440,'height':1000})

            page.reload()
            expect(page.locator('.gt-page-img')).to_be_visible()
            expect(page.locator('.gt-ocr-box')).to_have_count(1)
            assert page.evaluate("JSON.parse(localStorage.getItem('translate-drafts:v2')).trans_cache_catalog_1_p1.ocrResults[0].bbox") == [10,10,100,100]
            image_version['value'] = '"changed-image"'
            page.reload()
            expect(page.locator('.gt-page-img')).to_be_visible()
            expect(page.locator('.gt-ocr-box')).to_have_count(0)
            image_version['value'] = '"fixture"'
            print('PASS: a different image version does not restore old OCR boxes')

            fail_image['value']=True
            page.goto(base+'/#/gallery/1/read?token=abcde&page=1')
            expect(page.locator('.pi-error:visible').first).to_be_visible()
            assert '1' in requests
            requests.clear()
            fail_image['value']=False
            page.locator('.pi-error:visible').first.get_by_role('button',name='重试',exact=True).click()
            expect(page.locator('.pi-img:visible').first).to_be_visible()
            assert '1' in requests
            print('PASS: automatic decode retry and manual image refresh')
            page.locator('.scroll-view').click(position={'x':400,'y':300})
            expect(page.locator('.reader-reveal')).to_be_hidden()
            expect(page.locator('.top-bar')).to_be_hidden()
            page.locator('.scroll-view').click(position={'x':400,'y':300})
            expect(page.locator('.top-bar')).to_be_visible()
            expect(page.locator('.reader-reveal')).to_be_visible()
            print('PASS: scroll reader toolbar can be hidden and restored')


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
            page.unroute('**/api/gallery-images/part?*')
            requested_parts = []
            def long_directory(route):
                part = int(parse_qs(urlsplit(route.request.url).query)['part'][0])
                requested_parts.append(part)
                route.fulfill(json={'total': 400, 'partCount': 20, 'images': [
                    {'pageNum': i, 'pageUrl': f'https://e-hentai.org/s/abcde/1-{i}', 'thumbSprite': '',
                     'thumbX': 0, 'thumbW': 100, 'thumbH': 150}
                    for i in range(part * 20 + 1, part * 20 + 21)
                ]})
            page.route('**/api/gallery-images/part?*', long_directory)
            page.evaluate("localStorage.setItem('reader-settings',JSON.stringify({readingMode:'book',pagesPerScreen:1,bookDirection:'ltr',pageTurnAnimation:'none'}))")
            page.goto(base+'/#/gallery/1/read?token=abcde&page=350')
            expect(page.locator('.pi-img:visible').first).to_be_visible()
            assert {0, 17}.issubset(requested_parts) and len(set(requested_parts)) < 20, requested_parts
            page.keyboard.press('f')
            expect(page.locator('.ts-item')).to_have_count(80)
            expect(page.locator('.ts-item[aria-current=page]')).to_have_text('350')
            expect(page.locator('.thumb-sidebar form')).to_have_count(0)
            expect(page.locator('.reader-reveal')).to_have_text('350 / 400')
            page.locator('.thumb-sidebar').get_by_role('button', name='第 399 页', exact=True).click()
            expect(page.locator('.reader-reveal')).to_have_text('399 / 400')
            expect(page.locator('.ts-item')).to_have_count(80)
            expect(page.locator('.ts-item[aria-current=page]')).to_have_text('399')
            page.locator('.reader-reveal').focus()
            page.keyboard.press('F')
            expect(page.locator('.thumb-sidebar')).to_have_count(0)
            print('PASS: 80-page thumbnail window, thumbnail navigation and F shortcut')
            page.evaluate("localStorage.setItem('reader-settings',JSON.stringify({readingMode:'scroll',pagesPerScreen:1,bookDirection:'ltr',pageTurnAnimation:'none'}))")
            page.goto(base+'/#/gallery/1/read?token=abcde&page=350')
            page.reload()
            expect(page.locator('.scroll-page')).to_have_count(120)
            page.get_by_role('button',name=re.compile(r'第 361–400 页')).click()
            expect(page.locator('.scroll-page')).to_have_count(40)
            expect(page.locator('.reader-reveal')).to_have_text('361 / 400')
            page.get_by_role('button',name=re.compile(r'第 241–360 页')).click()
            expect(page.locator('.reader-reveal')).to_have_text('241 / 400')
            print('PASS: long scrolling reader loads bounded page segments in both directions')
            page.route('**/api/stats',lambda r:r.fulfill(status=503,json={'error':'temporary failure'}))
            page.goto(base+'/#/data')
            expect(page.locator('.stats-load-error')).to_be_visible()
            expect(page.locator('.data-panel')).to_have_count(0)
            print('PASS: failed statistics request shows recovery without empty charts')
            load_requests = {}

            def hold_load(stage):
                return lambda route: load_requests.update({stage: route})

            for stage, pattern in (
                ('list', '**/api/gallery-images/part?*'),
                ('image', '**/api/page-image?*'),
            ):
                page.route(pattern, hold_load(stage))
            for view in ('read', 'translate'):
                load_requests.clear()
                page.goto(base+f'/?view={view}#/gallery/1/{view}?token=abcde&page=1')
                for stage, response in (
                    ('list', {'json': {'total': 1, 'images': [
                        {'pageNum': 1, 'pageUrl': 'https://e-hentai.org/s/abcde/1-1',
                         'thumbSprite': '', 'thumbX': 0, 'thumbW': 100, 'thumbH': 150}]}}),
                    ('image', {'content_type': 'image/png', 'body': image.getvalue()}),
                ):
                    expect(page.locator(f'.image-load-progress.{stage}')).to_be_visible()
                    for _ in range(100):
                        if stage in load_requests:
                            break
                        page.wait_for_timeout(20)
                    load_requests[stage].fulfill(**response)
                expect(page.locator('.pi-img' if view == 'read' else '.gt-page-img')).to_be_visible()
                expect(page.locator('.image-load-progress')).to_have_count(0)
            print('PASS: reader and translator show directory and image loading stages until the image loads')
            assert not errors, errors
            browser.close()
    finally:
        server.shutdown(); server.server_close()


if __name__ == '__main__':
    main()
