"""Offline browser transport contracts without launching or contacting B17."""
from __future__ import annotations

import sys
from types import ModuleType, SimpleNamespace
from pathlib import Path

import pytest

from b17_parser import browser
from b17_parser.browser import BrowserClient, _prepare_profile_dir
from b17_parser.http import AccessError, FetchError

URL = 'https://www.b17.ru/example/'


class FakePage:
    def __init__(self, html='<h1>Public page</h1>', status=200):
        self.html = html
        self.status = status
        self.url = URL
        self.main_frame = object()
        self.calls = []
        self.handlers = []
        self.raise_on_goto = None
        self.content_type = 'text/html; charset=windows-1251'

    def route(self, pattern, handler):
        self.handlers.append((pattern, handler))

    def unroute(self, pattern, handler):
        self.handlers.remove((pattern, handler))

    def goto(self, url, **kwargs):
        self.calls.append((url, kwargs))
        self.url = url
        if self.raise_on_goto:
            raise self.raise_on_goto
        return SimpleNamespace(status=self.status, headers={'content-type': self.content_type})

    def content(self):
        return self.html


@pytest.fixture
def fake_client(tmp_path, monkeypatch):
    page = FakePage()
    client = BrowserClient(tmp_path / 'session', require_authenticated=False)
    monkeypatch.setattr(client, '_start', lambda: None)
    monkeypatch.setattr(browser.time, 'sleep', lambda seconds: None)
    client._page = page
    page.route('**/*', client._navigation_handler)
    return client, page


def test_rendered_html_and_timeout_are_preserved(fake_client):
    client, page = fake_client
    page.html = '<div style="display:none">Full hidden diploma text</div>'
    assert client.get('http://b17.ru/example/?utm_source=x#main') == page.html
    assert page.calls == [(URL, {'wait_until': 'domcontentloaded', 'timeout': 30000})]
    assert client.requests == 1
    assert client.last_url == URL


@pytest.mark.parametrize('status', [401, 403, 429, 503])
def test_access_denials_stop_without_retry(fake_client, status):
    client, page = fake_client
    page.status = status
    with pytest.raises(AccessError, match=f'HTTP {status}'):
        client.get(URL)
    assert client.requests == len(page.calls) == 1


@pytest.mark.parametrize('html', [
    '<title>Just a moment</title><div>Wait</div>',
    '<img src="/img/b17_guard.png">Ваш IP заблокирован',
    '<input name="captcha">Введите код с картинки',
])
def test_challenges_are_not_valid_html_results(fake_client, html):
    client, page = fake_client
    page.html = html
    with pytest.raises(AccessError):
        client.get(URL)
    assert len(page.calls) == 1


def test_login_requirement_is_checked_for_each_collection_page(fake_client, monkeypatch):
    client, page = fake_client
    client.require_login = True
    calls = []

    def validate(html, url, require_login=False):
        calls.append((html, url, require_login))
        raise AccessError('Login expired')

    monkeypatch.setattr(browser, 'validate_page', validate)
    with pytest.raises(AccessError, match='Login expired'):
        client.get(URL)
    assert calls == [(page.html, URL, True)]
    assert len(page.calls) == 1


def test_initial_external_url_is_rejected_before_browser_start(tmp_path, monkeypatch):
    client = BrowserClient(tmp_path / 'session')
    starts = []
    monkeypatch.setattr(client, '_start', lambda: starts.append(True))
    with pytest.raises(ValueError, match='b17.ru'):
        client.get('https://example.org/')
    assert not starts
    assert client.requests == 0


def test_external_redirect_is_aborted_but_subresources_are_allowed(fake_client):
    client, page = fake_client
    actions = []
    request = SimpleNamespace(url='https://example.org/', frame=page.main_frame,
                              is_navigation_request=lambda: True)
    route = SimpleNamespace(request=request, abort=lambda: actions.append('abort'),
                            continue_=lambda: actions.append('continue'))
    client._guard_navigation(route)
    assert actions == ['abort'] and client._blocked_navigation
    client._blocked_navigation = False
    request.is_navigation_request = lambda: False
    client._guard_navigation(route)
    assert actions[-1] == 'continue'
    assert not client._blocked_navigation


def test_navigation_error_has_no_retry(fake_client):
    client, page = fake_client
    page.raise_on_goto = TimeoutError('simulated timeout')
    with pytest.raises(FetchError, match='no retry attempted'):
        client.get(URL)
    assert client.requests == len(page.calls) == 1


def test_non_html_response_is_rejected(fake_client):
    client, page = fake_client
    page.content_type = 'application/json'
    with pytest.raises(FetchError, match='Expected HTML'):
        client.get(URL)


def test_delay_applies_between_automatic_pages(fake_client, monkeypatch):
    client, _ = fake_client
    moments = iter([20, 20, 21, 21])
    waits = []
    monkeypatch.setattr(browser.time, 'monotonic', lambda: next(moments))
    monkeypatch.setattr(browser.time, 'sleep', waits.append)
    client.get(URL)
    client.get(URL)
    assert waits == [0, 2]
    assert client.delay == 3
    assert BrowserClient(Path('unused'), delay=0).delay == 1


def test_manual_login_waits_without_routed_requests_and_checks_result(fake_client, monkeypatch):
    client, page = fake_client
    validations = []
    monkeypatch.setattr(browser, 'validate_page', lambda html, url, require_login=False:
                        validations.append((html, url, require_login)))

    def enter(prompt):
        assert not page.handlers
        assert 'вручную' in prompt
        page.html = '<a href="/my_response.php">Отклики</a>'
        return ''

    monkeypatch.setattr('builtins.input', enter)
    client.login()
    assert validations[0][2] is False
    assert validations[-1] == (page.html, 'https://www.b17.ru/', True)
    assert page.handlers == [('**/*', client._navigation_handler)]
    assert client.requests == 1


def test_private_session_directory_and_default_profile_protection(tmp_path):
    directory = _prepare_profile_dir(tmp_path / 'dedicated')
    assert directory.stat().st_mode & 0o777 == 0o700
    assert (directory / '.b17-collector-session').stat().st_mode & 0o777 == 0o600
    assert _prepare_profile_dir(directory) == directory
    ordinary = tmp_path / 'Chrome'
    ordinary.mkdir()
    (ordinary / 'Preferences').write_text('Existing browser data')
    with pytest.raises(ValueError, match='dedicated empty'):
        _prepare_profile_dir(ordinary)
    assert (ordinary / 'Preferences').read_text() == 'Existing browser data'


def test_session_symlink_is_not_adopted(tmp_path):
    target = tmp_path / 'target'
    target.mkdir()
    link = tmp_path / 'link'
    link.symlink_to(target, target_is_directory=True)
    with pytest.raises(ValueError, match='symlink'):
        _prepare_profile_dir(link)


def test_startup_uses_visible_vendor_chrome_and_closes_resources(tmp_path, monkeypatch):
    page = FakePage()
    opened = []
    closed = []
    context = SimpleNamespace(pages=[page], close=lambda: closed.append('context'))
    chromium = SimpleNamespace(launch_persistent_context=lambda path, **options:
                               (opened.append((path, options)) or context))
    runtime = SimpleNamespace(chromium=chromium, stop=lambda: closed.append('runtime'))
    package = ModuleType('playwright')
    package.__path__ = []
    api = ModuleType('playwright.sync_api')
    api.sync_playwright = lambda: SimpleNamespace(start=lambda: runtime)
    monkeypatch.setitem(sys.modules, 'playwright', package)
    monkeypatch.setitem(sys.modules, 'playwright.sync_api', api)
    directory = tmp_path / 'browser-session'
    with BrowserClient(directory) as client:
        assert client._page is page
        assert opened == [(str(directory), {'headless': False, 'accept_downloads': False, 'channel': 'chrome'})]
        assert client.requests == 0
    assert closed == ['context', 'runtime']
    client.close()
    assert closed == ['context', 'runtime']


def test_closed_page_reports_a_transport_failure(fake_client, monkeypatch):
    client, page = fake_client

    def closed():
        raise RuntimeError('page closed')

    monkeypatch.setattr(page, 'content', closed)
    with pytest.raises(FetchError, match='Cannot read the rendered'):
        client.get(URL)


def test_noninteractive_login_is_an_explicit_error(fake_client, monkeypatch):
    client, page = fake_client

    def no_stdin(prompt):
        raise EOFError

    monkeypatch.setattr('builtins.input', no_stdin)
    with pytest.raises(FetchError, match='interactive terminal'):
        client.login()
    assert page.handlers == [('**/*', client._navigation_handler)]


def test_cleanup_failure_does_not_mask_access_denial(tmp_path):
    stopped = []
    client = BrowserClient(tmp_path / 'session')

    def broken_close():
        raise RuntimeError('browser already crashed')

    client._context = SimpleNamespace(close=broken_close)
    client._playwright = SimpleNamespace(stop=lambda: stopped.append(True))
    client.close()
    assert stopped == [True]
    assert client._context is None and client._playwright is None
