import re
from urllib.parse import urlsplit
from bs4 import BeautifulSoup
from . import db
from .security import fail
from .upstream import fetch, json_request, validate_url


def gallery_page(url):
    content, _ = fetch(url, gallery=True)
    soup = BeautifulSoup(content, 'html.parser')
    if not soup.select_one('#gdt'):
        return None
    total = 0
    for label in soup.select('#gdd .gdt1'):
        if label.get_text(strip=True) == 'Length:':
            m = re.search(r'\d+', label.find_next_sibling().get_text())
            total = int(m[0]) if m else 0
    images = []
    for a in soup.select('#gdt a[href]'):
        match = re.search(r'/s/[a-zA-Z0-9]+/\d+-(\d+)/?$', a['href'])
        if not match:
            continue
        div = a.select_one('div[style*="url("]')
        img = a.select_one('img')
        style = div.get('style', '') if div else (img.get('style', '') if img else '')
        sprite = re.search(r'url\([\'"]?([^\)\'\"]+)', style)
        offset = re.search(r'(-?\d+)px\s+0(?:px)?\s+no-repeat|no-repeat\s+(-?\d+)px', style)
        width, height = re.search(r'width:\s*(\d+)px', style), re.search(r'height:\s*(\d+)px', style)
        images.append({'pageNum': int(match[1]), 'pageUrl': a['href'],
                       'thumbSprite': sprite[1] if sprite else (img.get('src', '') if img else ''),
                       'thumbX': int(next(v for v in offset.groups() if v is not None)) if offset else 0,
                       'thumbW': int(width[1]) if width else 100, 'thumbH': int(height[1]) if height else 142})
    pages = [int(t.get_text(strip=True)) for t in soup.select('.ptt td') if t.get_text(strip=True).isdigit()]
    return total, images, max(pages, default=1)


def gallery_images(gid, token):
    if not re.fullmatch(r'[1-9][0-9]{0,14}', gid) or not re.fullmatch(r'[a-zA-Z0-9]{5,64}', token):
        fail(400, '画廊 ID 或 token 不正确')
    key = f'gallery:{gid}:{token}'
    cached = db.get_cache(key)
    if cached:
        return cached
    for host, source in [('e-hentai.org', 'e-hentai'), ('exhentai.org', 'exhentai')]:
        base = f'https://{host}/g/{gid}/{token}/'
        try:
            first = gallery_page(base + '?nw=always')
        except Exception as exc:
            import httpx
            if isinstance(exc, httpx.HTTPStatusError) and exc.response.status_code in (403, 404):
                first = None
            else:
                raise
        if not first:
            continue
        total, images, pages = first
        if pages > 500:
            fail(502, '画廊分页超过限制')
        for page in range(1, pages):
            result = gallery_page(base + f'?p={page}')
            if not result:
                fail(502, '画廊分页不完整，请稍后重试')
            images.extend(result[1])
        result = {'gid': gid, 'total': total or len(images), 'images': images[:total] if total else images, 'source': source}
        db.set_cache(key, result, 3600)
        return result
    fail(403, 'exhentai_blocked')


def image_url(page_url):
    validate_url(page_url, gallery=True)
    if not re.fullmatch(r'/s/[a-zA-Z0-9]+/[0-9]+-[0-9]+/?', urlsplit(page_url).path):
        fail(400, '图片页面路径不正确')
    key = 'image-url:' + page_url
    cached = db.get_cache(key)
    if cached:
        return cached
    content, _ = fetch(page_url, gallery=True)
    soup = BeautifulSoup(content, 'html.parser')
    img = soup.select_one('#img[src]')
    if not img:
        fail(502, '无法读取图片地址')
    validate_url(img['src'], image=True)
    link = soup.select_one('#loadfail, a[onclick*="nl("]')
    nl = re.search(r"nl\('([^']+)'\)", link.get('onclick', '')) if link else None
    result = {'imageUrl': img['src'], 'nlParam': nl[1] if nl else None}
    db.set_cache(key, result, 900)
    return result


def lookup(word):
    if not word or len(word) > 100:
        fail(400, 'word 长度不正确')
    key = 'jisho:' + word
    cached = db.get_cache(key)
    if cached:
        return cached
    data = json_request('GET', 'https://jisho.org/api/v1/search/words', params={'keyword': word})
    results = []
    for entry in data.get('data', [])[:5]:
        ja = (entry.get('japanese') or [{}])[0]
        results.append({'word': ja.get('word') or entry.get('slug'), 'reading': ja.get('reading'),
                        'is_common': bool(entry.get('is_common')), 'jlpt': [v.replace('jlpt-', '').upper() for v in entry.get('jlpt', [])],
                        'senses': [{k: s.get(k, []) for k in ('parts_of_speech', 'english_definitions', 'tags', 'info')}
                                   for s in entry.get('senses', [])[:6]]})
    result = {'results': results}
    db.set_cache(key, result, 86400)
    return result
