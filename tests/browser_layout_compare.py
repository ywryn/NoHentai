"""Compare each layout with the same OCR and translation, across switches and reloads."""
import io
import threading
from functools import partial
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import urlsplit
from PIL import Image, ImageDraw
from playwright.sync_api import expect, sync_playwright


def run():
    folder = Path(__file__).resolve().parents[1] / 'web-static/dist'
    server = ThreadingHTTPServer(('127.0.0.1', 0), partial(SimpleHTTPRequestHandler, directory=str(folder)))
    threading.Thread(target=server.serve_forever, daemon=True).start()
    image = Image.new('RGB', (480, 900), 'gray')
    ImageDraw.Draw(image).ellipse((45, 50, 220, 260), fill='white', outline='black', width=4)
    data = io.BytesIO()
    image.save(data, format='PNG')
    try:
        with sync_playwright() as pw, pw.chromium.launch() as browser:
            for source in ('gallery', 'search'):
                page = browser.new_page(viewport={'width': 1200, 'height': 800})
                calls = {'ocr': 0, 'translate': 0}
                errors = []
                page.on('pageerror', lambda e: errors.append(str(e)))

                def api(route):
                    path = urlsplit(route.request.url).path
                    if path == '/api/trans-ocr':
                        calls['ocr'] += 1
                        route.fulfill(json={'results': [{'text': 'いい天気', 'bbox': [100, 100, 122, 150],
                                                       'confidence': .99}], 'source': 'vision'})
                    elif path == '/api/trans-translate':
                        calls['translate'] += 1
                        route.fulfill(json={'translations': [{'t': '今天天气真好。'}]})
                    elif path in ('/api/gallery-images/part', '/api/live/directory'):
                        route.fulfill(json={'total': 1, 'images': [{'pageNum': 1, 'pageUrl': 'https://example.org/1'}]})
                    elif path == '/api/page-image':
                        route.fulfill(content_type='image/png', headers={'ETag': '"layout-test"'}, body=data.getvalue())
                    else:
                        route.fulfill(json={})

                page.route('**/api/**', api)
                page.goto(f'http://127.0.0.1:{server.server_port}/#/{source}/42/translate?token=abcdef1234&page=1')
                page.get_by_role('button', name='识别并翻译', exact=True).click()
                page.get_by_role('link', name='排版对比').click()
                expect(page.locator('.lab article')).to_have_count(3)
                expect(page.get_by_text('识别到轮廓 1 / 1', exact=False)).to_be_visible()
                page.get_by_label('分组轮廓').check()
                expect(page.locator('.lab .outline')).to_have_count(3)
                page.locator('.lab article').first.get_by_role('button', name='对白 1').click()
                expect(page.locator('.lab aside')).to_contain_text('今天天气真好。')
                page.locator('.lab aside button').click()
                page.reload()
                expect(page.locator('.lab article')).to_have_count(3)
                page.set_viewport_size({'width': 390, 'height': 844})
                expect(page.locator('.lab article')).to_have_count(1)
                page.get_by_label('倍率').select_option('200')
                pane = page.locator('.lab .viewport')
                pane.evaluate('(el)=>el.scrollTo(100,150)')
                page.wait_for_function("document.querySelector('.lab .viewport').scrollTop===150")
                page.get_by_label('方案').select_option('balloon')
                expect(page.locator('.lab h2')).to_contain_text('气泡轮廓')
                assert pane.evaluate('(el)=>[el.scrollLeft,el.scrollTop]') == [100, 150]
                assert calls == {'ocr': 1, 'translate': 1}, calls
                assert not errors, errors
                page.close()
                print(source, calls)
    finally:
        server.shutdown()
        server.server_close()


if __name__ == '__main__':
    run()
