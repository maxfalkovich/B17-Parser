"""One HTTP session with bounded requests and explicit access failures."""
from __future__ import annotations

import time
from urllib.parse import urljoin

import requests


class FetchError(RuntimeError):
    """A request failed; callers must not interpret it as an empty result set."""


class AccessError(FetchError):
    """Access was denied; stop collection without attempting a bypass."""


class HttpClient:
    """Fetch public HTML with a fixed identity and at least one second spacing.

    Optional cookies are supplied explicitly; this never extracts a browser session.
    It never calls contact endpoints, rotates identities,
    or retries access denials. Network errors and non-access 5xx get two retries.
    """

    def __init__(self, delay: float = 3.0, timeout: float = 30, cookies_file=None):
        self.delay = max(1.0, delay)
        self.timeout = timeout
        self.session = requests.Session()
        self.session.headers.update({
            "User-Agent": "B17ProfileCollector/0.1 (local, public professional profiles)",
            "Accept": "text/html,application/xhtml+xml",
        })
        self.require_login = cookies_file is not None
        if cookies_file is not None:
            from .auth import load_cookies
            self.session.cookies.update(load_cookies(cookies_file))
        self.last_url = None
        self.last_request = 0.0
        self.requests = 0

    def close(self):
        self.session.close()

    def get(self, url: str) -> str:
        from .catalog import normalize_url

        current = normalize_url(url)
        self.last_url = current
        for redirect in range(6):
            for attempt in range(3):
                time.sleep(max(0, self.last_request + self.delay - time.monotonic()))
                self.last_request = time.monotonic()
                self.requests += 1
                try:
                    r = self.session.get(current, timeout=self.timeout, allow_redirects=False)
                except requests.RequestException as exc:
                    if attempt == 2:
                        raise FetchError(f"Network error for {current}: {exc}") from exc
                    continue
                if r.status_code in (401, 403, 429, 503):
                    raise AccessError(f"HTTP {r.status_code} for {current}; collection stopped")
                if r.status_code >= 500 and attempt < 2:
                    continue
                break
            if r.is_redirect:
                current = normalize_url(urljoin(current, r.headers.get("Location", "")))
                continue
            if r.status_code != 200:
                raise FetchError(f"HTTP {r.status_code} for {current}")
            if "html" not in r.headers.get("Content-Type", "").lower():
                raise FetchError(f"Expected HTML for {current}")
            # B17 declares Windows-1251 in its HTTP response; Requests honors it.
            html = r.text
            validate_page(html, current, self.require_login)
            self.last_url = current
            return html
        raise FetchError(f"Too many redirects for {url}")


def validate_page(html: str, url: str, require_login: bool = False) -> None:
    """Stop on access pages or expired login instead of collecting false records."""
    lower = html.lower()
    markers = ("<title>just a moment", "cf-chl-", "<title>access denied", "b17_guard.png",
               "доступ к сайту b17.ru для вашего ip", "ваш ip заблокирован",
               "<title>доступ ограничен", "попробуте зайти через 60 минут")
    if any(marker in lower for marker in markers):
        raise AccessError(f"Access/challenge page for {url}; collection stopped")
    from bs4 import BeautifulSoup
    soup = BeautifulSoup(html, 'html.parser')
    if soup.select_one('input[name="captcha"], input[name="captcha_code"], '
                       '.g-recaptcha[data-sitekey], iframe[src*="recaptcha"], img[src*="captcha"]'):
        raise AccessError(f"CAPTCHA page for {url}; collection stopped")
    if require_login:
        from .auth import authenticated_html
        if not authenticated_html(html):
            raise AccessError("B17 login is absent or expired; authenticated collection stopped")


class BudgetReached(FetchError):
    """The explicit per-run navigation budget was reached before a new request."""


class ManagedClient:
    """Apply a process-shared gate and a request budget to either transport."""

    def __init__(self, client, gate, max_requests=100):
        self.client, self.gate, self.max_requests = client, gate, max_requests
        self.requests = 0
        self.last_url = None

    def get(self, url):
        from .pacing import CooldownError
        if self.requests >= self.max_requests:
            raise BudgetReached('Request budget reached; resume later or explicitly increase --max-requests')
        try:
            with self.gate.slot():
                self.requests += 1
                try:
                    html = self.client.get(url)
                except AccessError as exc:
                    if 'login is absent or expired' not in str(exc):
                        self.gate.block(3600)
                    raise
                self.last_url = self.client.last_url
                return html
        except CooldownError as exc:
            raise AccessError(str(exc)) from exc

    def close(self):
        close = getattr(self.client, 'close', None)
        if close:
            close()
