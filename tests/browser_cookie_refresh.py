"""Exercise the ordered cross-domain login with a real browser and local fixtures."""
from contextlib import contextmanager
from unittest.mock import patch
from urllib.parse import urlsplit
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from playwright.sync_api import sync_playwright
from backend.cookie_refresh import acquire
from backend.jobs import JobFailure


def run(challenge=False):
    visits = []
    form = ('<form method="POST"><input name="UserName"><input type="password" name="PassWord">'
            '<input type="submit"></form>')

    def respond(route):
        request = route.request
        host = urlsplit(request.url).hostname
        visits.append((host, request.method))
        if host == 'forums.e-hentai.org':
            if challenge:
                return route.fulfill(status=403, headers={'cf-mitigated': 'challenge'}, body='Challenge')
            body = form if request.method == 'GET' else (
                '<script>document.cookie="ipb_member_id=test-42; Domain=.e-hentai.org; Path=/; Secure";'
                'document.cookie="ipb_pass_hash=test-hash; Domain=.e-hentai.org; Path=/; Secure";</script>')
        elif host == 'e-hentai.org':
            body = '<p>Public site</p>'
        else:
            cookie = request.all_headers().get('cookie', '')
            assert 'ipb_member_id=test-42' in cookie and 'ipb_pass_hash=test-hash' in cookie
            assert 'igneous' not in cookie
            body = '<table class="itg"></table><script>document.cookie="igneous=test-new; Path=/; Secure";</script>'
        route.fulfill(content_type='text/html', body=body)

    @contextmanager
    def browser_fixture():
        with sync_playwright() as playwright:
            launch = playwright.chromium.launch

            def launch_fixture(**kwargs):
                # This fixture runs on CI and as root with all requests intercepted.
                kwargs['chromium_sandbox'] = False
                browser = launch(**kwargs)
                new_context = browser.new_context

                def setup_context(**options):
                    context = new_context(**options)
                    context.route('**/*', respond)
                    context.route = lambda *_: None
                    return context

                browser.new_context = setup_context
                return browser

            playwright.chromium.launch = launch_fixture
            yield playwright

    with patch('playwright.sync_api.sync_playwright', browser_fixture):
        if challenge:
            try:
                acquire('fixture-user', 'fixture-password', lambda _: None)
            except JobFailure as exc:
                assert 'Cloudflare' in str(exc)
            else:
                raise AssertionError('challenge should stop the attempt')
        else:
            assert acquire('fixture-user', 'fixture-password', lambda _: None) == {
                'EXHENTAI_COOKIE_MEMBER_ID': 'test-42', 'EXHENTAI_COOKIE_PASS_HASH': 'test-hash',
                'EXHENTAI_COOKIE_IGNEOUS': 'test-new',
            }
    assert visits == [('forums.e-hentai.org', 'GET')] if challenge else visits == [
        ('forums.e-hentai.org', 'GET'), ('forums.e-hentai.org', 'POST'),
        ('e-hentai.org', 'GET'), ('exhentai.org', 'GET')], visits


if __name__ == '__main__':
    run()
    run(challenge=True)
    print('Cookie order, cross-domain handoff and Cloudflare failure verified')
