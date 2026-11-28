import asyncio
import re
from urllib.parse import urlencode, urljoin, urlsplit

import httpx
from bs4 import BeautifulSoup
from . import db, observability
from .security import fail
from fastapi import HTTPException
from .upstream import fetch, fetch_page, json_request, validate_url


def gallery_directory_url(host, gid, token, part):
    # Upstream can redirect nw=always to the gallery root and drop p.
    query = f'p={part}' if part else 'nw=always'
    return f'https://{host}/g/{gid}/{token}/?{query}'


def gallery_page(url, part=None):
    content, _ = fetch(url, gallery=True)
    return parse_gallery_page(BeautifulSoup(content, 'html.parser'), part)


def parse_gallery_page(soup, part=None):
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
    if part is not None and images:
        numbers = [image['pageNum'] for image in images]
        active = soup.select_one('.ptt td.ptds')
        if ((active and active.get_text(strip=True) != str(part + 1))
                or (numbers[0] == 1) != (part == 0)):
            fail(502, '上游返回了错误的目录分页，请刷新')
        if (not 1 <= numbers[0] <= numbers[-1] <= total <= 100000
                or numbers != list(range(numbers[0], numbers[0] + len(numbers)))):
            fail(502, '上游目录页码不完整，请刷新')
    pages = [int(t.get_text(strip=True)) for t in soup.select('.ptt td') if t.get_text(strip=True).isdigit()]
    return total, images, max(pages, default=1)


def gallery_part(gid, token, part, source=None, refresh=False):
    if not re.fullmatch(r'[1-9][0-9]{0,14}', gid) or not re.fullmatch(r'[a-zA-Z0-9]{5,64}', token):
        fail(400, '画廊 ID 或 token 不正确')
    for host in ([source] if source else ['e-hentai.org', 'exhentai.org']):
        key = f'gallery-part:v2:{host}:{gid}:{token}:{part}'
        cached = None if refresh else db.get_cache(key)
        if cached:
            return cached
        url = gallery_directory_url(host, gid, token, part)
        try:
            result = gallery_page(url, part)
        except httpx.HTTPStatusError as exc:
            if exc.response.status_code not in (403, 404):
                raise
            continue
        if not result or not result[1]:
            continue
        total, images, part_count = result
        for item in images:
            item['pageUrl'] = urljoin(url, item['pageUrl'])
            if item['thumbSprite']:
                item['thumbSprite'] = urljoin(url, item['thumbSprite'])
        data = {'total': total, 'images': images, 'partCount': part_count, 'source': host}
        db.set_cache(key, data, 900)
        return data
    fail(403, 'exhentai_blocked')


def gallery_images(gid, token):
    if not re.fullmatch(r'[1-9][0-9]{0,14}', gid) or not re.fullmatch(r'[a-zA-Z0-9]{5,64}', token):
        fail(400, '画廊 ID 或 token 不正确')
    key = f'gallery:v2:{gid}:{token}'
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
            if result[0] and total and result[0] != total:
                fail(502, '画廊分页总页数发生变化，请稍后重试')
            images.extend(result[1])
        total = total or len(images)
        numbers = [item['pageNum'] for item in images]
        if not total or len(numbers) != total or sorted(numbers) != list(range(1, total + 1)):
            fail(502, '画廊页面列表不完整，请重新加载')
        result = {'gid': gid, 'total': total, 'images': sorted(images, key=lambda item: item['pageNum']), 'source': source}
        db.set_cache(key, result, 3600)
        return result
    fail(403, 'exhentai_blocked')


def image_url(page_url, refresh=False, persistent=True, *, store=True):
    validate_url(page_url, gallery=True)
    if not re.fullmatch(r'/s/[a-zA-Z0-9]+/[0-9]+-[0-9]+/?', urlsplit(page_url).path):
        fail(400, '图片页面路径不正确')
    key = 'image-url:' + page_url
    cached = None if refresh or not persistent else db.get_cache(key)
    if cached:
        return cached
    content, _ = fetch(page_url, gallery=True)
    result = parse_image_page(content)
    validate_url(result['imageUrl'], image=True)
    if persistent and store:
        db.set_cache(key, result, 900)
    return result


class PageImageError(HTTPException):
    def __init__(self, status, message, code):
        super().__init__(status, message)
        self.code = code


def parse_image_page(content):
    soup = BeautifulSoup(content, 'html.parser')
    img = soup.select_one('#img[src]')
    if not img:
        raise PageImageError(502, '无法读取图片地址', 'resolve_failed')
    link = soup.select_one('#loadfail, a[onclick*="nl("]')
    nl = re.search(r"nl\('([^']+)'\)", link.get('onclick', '')) if link else None
    return {'imageUrl': img['src'], 'nlParam': nl[1] if nl else None}


PAGE_IMAGE_TIMEOUT = 35


async def page_image(page_url, client, *, refresh=False, persistent=True):
    try:
        async with asyncio.timeout(PAGE_IMAGE_TIMEOUT):
            return await _load_page_image(page_url, client, refresh=refresh, persistent=persistent)
    except TimeoutError as exc:
        raise PageImageError(504, '页图加载超过等待时间，请重试', 'page_timeout') from exc


async def _load_page_image(page_url, client, *, refresh, persistent):
    page = urlsplit(page_url)
    canonical = page._replace(query='', fragment='').geturl()
    if not re.fullmatch(r'/s/[a-zA-Z0-9]+/[0-9]+-[0-9]+/?', page.path):
        raise PageImageError(400, '图片页面路径不正确', 'invalid_page')
    candidate = canonical
    seen_keys = set()
    failed_urls = set()
    last_download_error = None
    for attempt in range(3):
        stage = '图片地址'
        try:
            resolved = None
            if persistent and not refresh and attempt == 0:
                await asyncio.to_thread(validate_url, candidate, gallery=True, retry_dns=True)
                resolved = await asyncio.to_thread(db.get_cache, 'image-url:' + canonical)
            if not resolved:
                html, _ = await fetch_page(candidate, client)
                resolved = await asyncio.to_thread(parse_image_page, html)
            target = resolved['imageUrl']
            if urlsplit(target).path.lower().endswith(('/509.gif', '/509s.gif')):
                raise PageImageError(509, '上游图片额度已用尽', 'quota_exhausted')
            stage = '正文图片'
            if target in failed_urls:
                break
            last_download_error = None
            content, mime = await fetch_page(target, client, image=True)
            if content and mime.lower().split(';', 1)[0].strip() in {
                'image/jpeg', 'image/png', 'image/gif', 'image/webp', 'image/avif',
                'image/bmp', 'image/x-ms-bmp', 'image/jxl', 'image/apng',
            }:
                if persistent:
                    await asyncio.to_thread(db.set_cache, 'image-url:' + canonical, resolved, 900)
                return content, mime
            failed_urls.add(target)
        except httpx.HTTPStatusError as exc:
            status = exc.response.status_code
            if status == 509:
                raise PageImageError(509, '上游图片额度已用尽', 'quota_exhausted') from exc
            if status == 429:
                raise PageImageError(429, '上游请求过多，请稍后重试', 'rate_limited') from exc
            if stage == '图片地址' and status in (401, 403, 404):
                raise PageImageError(status, '上游图片页面不可访问', 'page_unavailable') from exc
            if stage == '图片地址' and status >= 500 and attempt < 2:
                continue
            if stage == '图片地址':
                raise PageImageError(502, '获取图片地址失败', 'resolve_failed') from exc
            if status in (403, 404, 410):
                failed_urls.add(target)
        except httpx.PoolTimeout as exc:
            observability.log_failure('page_image_pool', exc)
            raise PageImageError(503, '页图请求繁忙，请稍后重试', 'pool_busy') from exc
        except httpx.TransportError as exc:
            if stage == '图片地址':
                if attempt == 2:
                    raise PageImageError(504, '图片地址超时或连接失败', 'resolve_failed') from exc
                continue
            last_download_error = exc
            failed_urls.add(target)
        key = resolved['nlParam']
        if key and key not in seen_keys:
            seen_keys.add(key)
            candidate = page._replace(query=urlencode({'nl': key}), fragment='').geturl()
        elif attempt == 0:
            candidate = canonical
        else:
            break
    if last_download_error is not None:
        raise PageImageError(504, '正文图片超时或连接失败', 'download_timeout') from last_download_error
    raise PageImageError(502, '正文图片下载失败，请重新加载', 'download_failed')


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
