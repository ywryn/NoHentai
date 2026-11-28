"""Outbound URL validation and bounded responses. Never forward credentials to redirects."""
import asyncio
from http.cookiejar import CookieJar, DefaultCookiePolicy
import ipaddress
import json
import os
import socket
from urllib.parse import urlsplit, urljoin
import httpx
from .security import fail, credential

GALLERY_HOSTS = {'e-hentai.org', 'exhentai.org'}
IMAGE_SUFFIXES = ('hath.network', 'ehgt.org', 'e-hentai.org', 'exhentai.org')
MAX_IMAGE = 24 * 1024 * 1024
MAX_JSON = 16 * 1024 * 1024


class _NoUpstreamCookies(DefaultCookiePolicy):
    def set_ok(self, cookie, request):
        return False


def page_client():
    return httpx.AsyncClient(
        follow_redirects=False,
        cookies=CookieJar(policy=_NoUpstreamCookies()),
        limits=httpx.Limits(max_connections=12, max_keepalive_connections=8, keepalive_expiry=20),
    )


def validate_url(url, gallery=False, image=False, *, retry_dns=False):
    try:
        p = urlsplit(url)
        if p.scheme != 'https' or not p.hostname or p.username or p.password:
            raise ValueError()
        # H@H nodes serve HTTPS images on user-configured unprivileged ports.
        hath = image and p.hostname.lower().endswith('.hath.network')
        if p.port not in (None,443) and not (hath and 1024 <= p.port <= 65535):
            raise ValueError()
        host = p.hostname.lower()
        if gallery and host not in GALLERY_HOSTS:
            raise ValueError()
        if image and not any(host == s or host.endswith('.' + s) for s in IMAGE_SUFFIXES):
            raise ValueError()
        addresses = socket.getaddrinfo(host, 443, type=socket.SOCK_STREAM)
        if not addresses or any(not ipaddress.ip_address(r[4][0]).is_global for r in addresses):
            raise ValueError()
    except OSError as exc:
        if retry_dns:
            raise httpx.ConnectError('Upstream DNS resolution failed') from exc
        fail(400, '不允许的上游地址')
    except ValueError:
        fail(400, '不允许的上游地址')
    return url


def cookies():
    return '; '.join(f'{k}={v}' for k, v in {
        'ipb_member_id': credential('EXHENTAI_COOKIE_MEMBER_ID'),
        'ipb_pass_hash': credential('EXHENTAI_COOKIE_PASS_HASH'),
        'igneous': credential('EXHENTAI_COOKIE_IGNEOUS'),
    }.items() if v)


def fetch(url, gallery=False, image=False, *, cover_validators=None, **kwargs):
    if os.getenv('NOHENTAI_DISABLE_UPSTREAM') == '1':
        fail(503, '验收环境未启用外部服务')
    # Follow each redirect explicitly, applying the host/network checks again.
    for _ in range(5):
        validate_url(url, gallery=gallery, image=image)
        headers = {'User-Agent': 'Mozilla/5.0 NoHentai/2.0', 'Referer': 'https://e-hentai.org/'}
        if urlsplit(url).hostname == 'exhentai.org':
            headers['Cookie'] = cookies()
        if cover_validators is not None:
            headers.update(cover_validators)
        with httpx.Client(timeout=8 if cover_validators is not None else 45, follow_redirects=False) as client:
            with client.stream('GET', url, headers=headers, **kwargs) as response:
                if response.status_code == 304 and cover_validators:
                    return None, response.headers
                if response.is_redirect:
                    url = urljoin(url, response.headers['location'])
                    continue
                response.raise_for_status()
                chunks, length = [], 0
                for chunk in response.iter_bytes():
                    length += len(chunk)
                    if length > MAX_IMAGE:
                        fail(502, '上游响应过大')
                    chunks.append(chunk)
                return b''.join(chunks), response.headers if cover_validators is not None else response.headers.get('content-type', '')
    fail(502, '上游重定向过多')


def json_request(method, url, **kwargs):
    if os.getenv('NOHENTAI_DISABLE_UPSTREAM') == '1':
        fail(503, '验收环境未启用外部服务')
    validate_url(url)
    with httpx.Client(timeout=90, follow_redirects=False) as client:
        with client.stream(method, url, **kwargs) as response:
            response.raise_for_status()
            chunks, size = [], 0
            for chunk in response.iter_bytes():
                size += len(chunk)
                if size > MAX_JSON:
                    fail(502, '上游 JSON 响应过大')
                chunks.append(chunk)
            return json.loads(b''.join(chunks))


async def fetch_page(url, client, *, image=False):
    """Bound a page lookup or image download, including redirects and slow streams."""
    if os.getenv('NOHENTAI_DISABLE_UPSTREAM') == '1':
        fail(503, '验收环境未启用外部服务')
    timeout = httpx.Timeout(12 if image else 9, connect=5, pool=3)
    send_cookie = urlsplit(url).hostname == 'exhentai.org'
    try:
        async with asyncio.timeout(15 if image else 11):
            for _ in range(5):
                await asyncio.to_thread(validate_url, url, gallery=not image, image=image, retry_dns=True)
                headers = {'User-Agent': 'Mozilla/5.0 NoHentai/2.0', 'Referer': 'https://e-hentai.org/'}
                if send_cookie and urlsplit(url).hostname == 'exhentai.org':
                    headers['Cookie'] = await asyncio.to_thread(cookies)
                async with client.stream('GET', url, headers=headers, timeout=timeout) as response:
                    if response.is_redirect:
                        location = response.headers.get('location')
                        if not location:
                            fail(502, '上游重定向缺少目标地址')
                        next_url = urljoin(url, location)
                        send_cookie = send_cookie and urlsplit(next_url).netloc == urlsplit(url).netloc
                        url = next_url
                        continue
                    response.raise_for_status()
                    content = bytearray()
                    async for chunk in response.aiter_bytes():
                        if len(content) + len(chunk) > MAX_IMAGE:
                            fail(502, '上游响应过大')
                        content.extend(chunk)
                    return bytes(content), response.headers.get('content-type', '')
    except TimeoutError as exc:
        raise httpx.ReadTimeout('Page attempt timed out') from exc
    fail(502, '上游重定向过多')
