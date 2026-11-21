"""Request-scoped access to the configured gallery site."""
import re
from urllib.parse import parse_qs, urlencode, urljoin, urlsplit
from bs4 import BeautifulSoup
import httpx
from app.exhentai_search import GalleryListParser
from . import media, catalog, db
from .security import credential, fail
from .upstream import fetch, GALLERY_HOSTS


def site(expected=''):
    host = credential('LIVE_SITE')
    if host not in GALLERY_HOSTS:
        fail(503, '请配置实时搜索站点')
    if expected and expected != host:
        fail(409, '搜索站点已切换，请返回重新搜索')
    return host


def document(url):
    try:
        content, _ = fetch(url, gallery=True)
    except httpx.HTTPStatusError as exc:
        if exc.response.status_code in (429, 509):
            fail(429, '上游请求额度受限，请稍后重试')
        if exc.response.status_code in (401, 403, 404):
            fail(403, '上游内容不可访问，请检查站点权限')
        raise
    return content


def search(query, cursor, expected, prev, excluded_categories=0):
    host = site(expected)
    params = {'f_search': query, 'inline_set': 'dm_c'}
    if excluded_categories:
        params['f_cats'] = excluded_categories
    if cursor:
        params['next'] = cursor
    if prev:
        params.pop('next', None)
        params['prev'] = prev
    page = GalleryListParser.parse(document(f'https://{host}/?' + urlencode(params)).decode('utf-8', 'replace'))
    if page['error']:
        fail(502, '无法读取实时列表，请检查上游登录或稍后重试')
    cursor = parse_qs(urlsplit(page['next_url'] or '').query).get('next', [''])[0]
    return {'site': host, 'items': page['galleries'], 'next': cursor,
            'prev': parse_qs(urlsplit(page.get('prev_url') or '').query).get('prev', [''])[0]}


def gallery_metadata(soup, url, total):
    def text(selector):
        element = soup.select_one(selector)
        return element.get_text(strip=True) if element else ''

    fields = {}
    for label in soup.select('#gdd .gdt1'):
        value = label.find_next_sibling('td')
        if value:
            fields[label.get_text(strip=True).rstrip(':')] = value.get_text(strip=True)
    cover = soup.select_one('#gd1 [style*="url("], #gd1[style*="url("]')
    match = re.search(r"""url\(['"]?([^)'"]+)""", cover['style']) if cover else None
    cover_img = soup.select_one('#gd1 img[src]')
    thumb = match[1] if match else cover_img['src'] if cover_img else ''
    rating = re.search(r'([0-5](?:\.\d+)?)$', text('#rating_label'))
    tags = []
    with db.connect() as con:
        dictionary = catalog.translations(con)
        for row in soup.select('#taglist tr'):
            ns = row.select_one('td')
            namespace = ns.get_text(strip=True).rstrip(':') if ns else 'other'
            for anchor in row.select('a'):
                value = anchor.get_text(strip=True)
                tag = f'{namespace}:{value}'
                tags.append({'tag':tag, 'namespace':namespace, 'value':value,
                             'tag_cn':dictionary.get(tag, {}).get('name', '')})
    return {'title': text('#gn') or text('#gj'), 'title_jpn':text('#gj'), 'category':text('#gdc'),
            'uploader':text('#gdn a'), 'filecount':total, 'postedLabel':fields.get('Posted'),
            'sizeLabel':fields.get('File Size'), 'thumb':urljoin(url,thumb) if thumb else '',
            'rating':float(rating[1]) if rating else None, 'tags':tags}


def directory(host, gid, token, part, details=False):
    host = site(host)
    url = f'https://{host}/g/{gid}/{token}/?nw=always&p={part}'
    soup = BeautifulSoup(document(url), 'html.parser')
    page = media.parse_gallery_page(soup)
    if not page or not page[1]:
        fail(403, '画廊不可访问，请检查站点权限')
    total, images, part_count = page
    if not 0 < total <= 100000:
        fail(502, '画廊页数无效')
    numbers = [image['pageNum'] for image in images]
    if numbers != list(range(numbers[0], numbers[0] + len(images))) or not 1 <= numbers[0] <= numbers[-1] <= total:
        fail(502, '上游目录页码不完整，请刷新')
    for image in images:
        image['pageUrl'] = urljoin(url, image['pageUrl'])
        if image['thumbSprite']:
            image['thumbSprite'] = urljoin(url, image['thumbSprite'])
    title = soup.select_one('#gj')
    if not title or not title.get_text(strip=True):
        title = soup.select_one('#gn')
    result = {'total': total, 'images': images, 'partCount':part_count, 'title': title.get_text(strip=True) if title else gid,
            'tags': [a.get_text(strip=True) for a in soup.select('#taglist a')], 'site': host}
    if details:
        result['gallery'] = gallery_metadata(soup, url, total)
    return result


def resolve(host, url):
    if urlsplit(url).hostname != site(host):
        fail(400, '图片来源与当前站点不符')
    return media.image_url(url, persistent=False)
