"""Optional visible-browser transport using a dedicated persistent login session."""
from __future__ import annotations

import math
import os
import time
from pathlib import Path

from .catalog import normalize_url
from .http import AccessError, FetchError, validate_page


_SESSION_MARKER = '.b17-collector-session'


def _prepare_profile_dir(profile_dir: Path) -> Path:
    """Create a private dedicated browser directory without adopting other data.

    Existing nonempty directories must carry our marker. This prevents accidental
    use of the user's everyday Chrome profile or another application's folder.
    Cookies remain in the browser-managed directory and are never exported.
    """
    path = profile_dir.expanduser()
    if path.is_symlink():
        raise ValueError('Browser session directory must not be a symlink')
    path = path.resolve()
    if path.exists():
        if not path.is_dir():
            raise ValueError('Browser session path must be a directory')
        if any(path.iterdir()) and not (path / _SESSION_MARKER).is_file():
            raise ValueError('Use a dedicated empty browser session directory, not an existing Chrome profile')
    path.mkdir(parents=True, exist_ok=True, mode=0o700)
    os.chmod(path, 0o700)
    marker = path / _SESSION_MARKER
    if not marker.exists():
        marker.write_text('B17 Profile Collector dedicated browser session\n', encoding='utf-8')
        os.chmod(marker, 0o600)
    return path


class BrowserClient:
    """Fetch rendered HTML in visible Chrome without exporting authentication.

    The required profile_dir must be dedicated to this collector. Browser startup
    is lazy, and the optional Playwright dependency is imported only then. Login
    happens manually in the visible browser via login(); collection requires the
    authenticated site controls by default and stops when the session expires.

    Automatic page attempts are spaced by at least one second. The requests
    counter counts get()/initial login navigations, not browser subresources,
    redirects, or the user's manual login actions. Access denials and challenges
    stop immediately without retries, identity changes, or CAPTCHA interaction.
    Call close(), or use a context manager, to flush and release the session.
    """

    def __init__(self, profile_dir: str | Path, delay: float = 3.0,
                 timeout: float = 30, channel: str | None = 'chrome',
                 require_authenticated: bool = True):
        if not math.isfinite(delay) or not math.isfinite(timeout) or timeout <= 0:
            raise ValueError('Browser delay must be finite and timeout must be finite and positive')
        self.profile_dir = Path(profile_dir)
        self.delay = max(1.0, delay)
        self.timeout = timeout
        self.channel = channel
        self.require_login = require_authenticated
        self.requests = 0
        self.last_request = 0.0
        self.last_url = None
        self._playwright = None
        self._context = None
        self._page = None
        self._blocked_navigation = False
        # Keep one bound callback object so unroute removes exactly this handler.
        self._navigation_handler = self._guard_navigation

    def _start(self) -> None:
        if self._context is not None:
            return
        try:
            from playwright.sync_api import sync_playwright
        except ImportError as exc:
            raise FetchError("Browser mode requires Playwright; install the project's [browser] extra") from exc
        profile_dir = _prepare_profile_dir(self.profile_dir)
        try:
            self._playwright = sync_playwright().start()
            options = {'headless': False, 'accept_downloads': False}
            if self.channel:
                options['channel'] = self.channel
            self._context = self._playwright.chromium.launch_persistent_context(str(profile_dir), **options)
            self._page = self._context.pages[0] if self._context.pages else self._context.new_page()
            self._page.route('**/*', self._navigation_handler)
        except Exception as exc:
            self.close()
            raise FetchError('Cannot launch the dedicated Playwright browser; check the browser installation and session directory') from exc

    def _guard_navigation(self, route) -> None:
        request = route.request
        if request.is_navigation_request() and request.frame == self._page.main_frame:
            try:
                normalize_url(request.url)
            except ValueError:
                self._blocked_navigation = True
                route.abort()
                return
        route.continue_()

    def _navigate(self, url: str, require_login: bool) -> str:
        current = normalize_url(url)
        self._start()
        self._blocked_navigation = False
        time.sleep(max(0, self.last_request + self.delay - time.monotonic()))
        self.last_request = time.monotonic()
        self.requests += 1
        try:
            response = self._page.goto(current, wait_until='domcontentloaded', timeout=self.timeout * 1000)
        except Exception as exc:
            if self._blocked_navigation:
                raise AccessError('Browser navigation outside B17 was blocked; collection stopped') from exc
            raise FetchError(f'Browser navigation failed for {current} ({type(exc).__name__}); no retry attempted') from exc
        if self._blocked_navigation:
            raise AccessError('Browser navigation outside B17 was blocked; collection stopped')
        try:
            final_url = normalize_url(self._page.url)
        except ValueError as exc:
            raise AccessError('Browser left B17 during automatic navigation; collection stopped') from exc
        self.last_url = final_url
        if response is None:
            raise FetchError(f'Browser received no document response for {final_url}')
        if response.status in (401, 403, 429, 503):
            raise AccessError(f'HTTP {response.status} for {final_url}; collection stopped')
        if response.status != 200:
            raise FetchError(f'HTTP {response.status} for {final_url}')
        if 'html' not in response.headers.get('content-type', '').lower():
            raise FetchError(f'Expected HTML for {final_url}')
        html = self._read_html()
        validate_page(html, final_url, require_login)
        # Explicit CAPTCHA controls mean a challenge rather than usable profile
        # content. Merely mentioning CAPTCHA in a script is not sufficient.
        from bs4 import BeautifulSoup
        soup = BeautifulSoup(html, 'html.parser')
        if soup.select_one('input[name="captcha"], input[name="captcha_code"], '
                           '.g-recaptcha[data-sitekey], iframe[src*="recaptcha"], img[src*="captcha"]'):
            raise AccessError(f'CAPTCHA page for {final_url}; collection stopped')
        return html

    def _read_html(self) -> str:
        try:
            return self._page.content()
        except Exception as exc:
            raise FetchError('Cannot read the rendered B17 page; the browser may have been closed') from exc

    def get(self, url: str) -> str:
        """Return rendered HTML after verifying access, login, and the final URL."""
        return self._navigate(url, self.require_login)

    def login(self) -> None:
        """Open B17 for manual login and verify the user's completed session.

        Run only when site access is available. No credentials are requested by
        this process, and no cookies are read, printed, or exported. The caller
        must supply interactive stdin; Enter is only an acknowledgement that the
        user has finished, not evidence of successful authentication.
        """
        self._navigate('https://www.b17.ru/', require_login=False)
        # Synchronous Python input otherwise prevents Playwright's routed request
        # callbacks from being served while the user operates the login page.
        self._page.unroute('**/*', self._navigation_handler)
        try:
            input('Войдите в B17 вручную в открытом браузере, затем нажмите Enter здесь: ')
        except EOFError as exc:
            raise FetchError('Manual browser login requires an interactive terminal') from exc
        finally:
            try:
                self._page.route('**/*', self._navigation_handler)
            except Exception as exc:
                raise FetchError('The manual browser session was closed before login verification') from exc
        final_url = normalize_url(self._page.url)
        html = self._read_html()
        validate_page(html, final_url, require_login=True)
        self.last_url = final_url

    def close(self) -> None:
        """Release browser resources, retaining the dedicated local session.

        Cleanup tolerates an already closed or crashed browser so it cannot mask
        an access-denial error raised by a collection operation.
        """
        context, runtime = self._context, self._playwright
        self._context = self._page = self._playwright = None
        try:
            if context is not None:
                context.close()
        except Exception:
            pass
        finally:
            if runtime is not None:
                try:
                    runtime.stop()
                except Exception:
                    pass

    def __enter__(self):
        self._start()
        return self

    def __exit__(self, exc_type, exc, traceback):
        self.close()


def login(profile_dir: str | Path, *, delay: float = 3.0,
          timeout: float = 30, channel: str | None = 'chrome') -> None:
    """Create or refresh one dedicated session through a manual browser login."""
    with BrowserClient(profile_dir, delay, timeout, channel) as client:
        client.login()
