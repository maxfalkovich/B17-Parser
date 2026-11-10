"""Import an explicitly supplied B17 session without inspecting browser storage."""
from __future__ import annotations

import copy
from http.cookiejar import Cookie, LoadError, MozillaCookieJar
import json
import math
from pathlib import Path
import re
import time
from urllib.parse import urljoin, urlsplit
import warnings

from bs4 import BeautifulSoup
from requests.cookies import RequestsCookieJar, create_cookie


_DOMAINS = {"b17.ru", "www.b17.ru", ".b17.ru"}
_COOKIE_NAME = re.compile(r"[!#$%&'*+.^_`|~0-9A-Za-z-]+\Z")
_CONTROLS = re.compile(r"[\x00-\x1f\x7f]")
_ACCOUNT_PATHS = {"/my_response.php", "/privat.php"}


def _valid_cookie(cookie: Cookie) -> None:
    """Reject malformed header fields without including their values in errors."""
    if (
        not _COOKIE_NAME.fullmatch(cookie.name or "")
        or not isinstance(cookie.value, str)
        or _CONTROLS.search(cookie.value)
        or not isinstance(cookie.path, str)
        or not cookie.path.startswith("/")
        or _CONTROLS.search(cookie.path)
    ):
        raise ValueError("Cookie file contains an invalid B17 cookie")


def _playwright_cookies(data: object) -> list[Cookie]:
    if not isinstance(data, dict) or not isinstance(data.get("cookies"), list):
        raise ValueError("Expected a Playwright storage-state object with a cookies list")
    cookies = []
    for item in data["cookies"]:
        if not isinstance(item, dict) or not isinstance(item.get("domain"), str):
            raise ValueError("Cookie file contains a malformed cookie entry")
        if item["domain"] not in _DOMAINS:
            continue
        if (
            not isinstance(item.get("name"), str)
            or not isinstance(item.get("value"), str)
            or not isinstance(item.get("path", "/"), str)
            or not isinstance(item.get("secure", False), bool)
            or not isinstance(item.get("httpOnly", False), bool)
        ):
            raise ValueError("Cookie file contains a malformed B17 cookie")
        expires = item.get("expires", -1)
        if (
            isinstance(expires, bool)
            or not isinstance(expires, (int, float))
            or not math.isfinite(expires)
            or (expires < 0 and expires != -1)
        ):
            raise ValueError("Cookie file contains an invalid cookie expiry")
        rest = {"HttpOnly": item.get("httpOnly", False)}
        if "sameSite" in item:
            if item["sameSite"] not in {"Strict", "Lax", "None"}:
                raise ValueError("Cookie file contains an invalid SameSite value")
            rest["SameSite"] = item["sameSite"]
        cookies.append(create_cookie(
            name=item["name"], value=item["value"], domain=item["domain"],
            path=item.get("path", "/"), secure=item.get("secure", False),
            expires=int(expires) if expires >= 0 else None, rest=rest,
        ))
    return cookies


def _validate_netscape(contents: str) -> None:
    """Check Netscape records before the standard loader can emit diagnostics."""
    for line in contents.splitlines()[1:]:
        if line.startswith("#HttpOnly_"):
            line = line[len("#HttpOnly_"):]
        if not line.strip() or line.lstrip().startswith(("#", "$")):
            continue
        fields = line.split("\t")
        if len(fields) != 7:
            raise ValueError("Invalid Netscape cookie record")
        domain, subdomains, _, secure, expires, _, _ = fields
        if (
            subdomains not in {"TRUE", "FALSE"}
            or secure not in {"TRUE", "FALSE"}
            or (subdomains == "TRUE") != domain.startswith(".")
            or (expires and not expires.isdecimal())
        ):
            raise ValueError("Invalid Netscape cookie attributes")


def load_cookies(path: str | Path) -> RequestsCookieJar:
    """Read B17 cookies from Netscape or Playwright storage-state JSON.

    Only the exact B17 domain forms listed here are imported. Expired cookies
    are omitted; session cookies and their secure/path/HttpOnly attributes are
    retained. Empty, malformed or non-B17 exports raise ValueError without
    revealing cookie values. No file is created or changed, and browser storage
    is never inspected. Keep the supplied file private (mode 0600 is recommended).
    """
    path = Path(path)
    try:
        contents = path.read_text(encoding="utf-8-sig")
    except (OSError, UnicodeError):
        raise ValueError("Cookie file cannot be read as UTF-8") from None
    if not contents.strip():
        raise ValueError("Cookie file is empty")
    try:
        if contents.lstrip().startswith(("{", "[")):
            cookies = _playwright_cookies(json.loads(contents))
        else:
            # MozillaCookieJar understands #HttpOnly_ lines in Netscape files.
            _validate_netscape(contents)
            source = MozillaCookieJar(str(path))
            # Its malformed-record warning can include a raw exception. Keep
            # diagnostics under our control so no cookie value reaches stderr.
            with warnings.catch_warnings():
                warnings.simplefilter("ignore", UserWarning)
                source.load(ignore_discard=True, ignore_expires=True)
            cookies = list(source)
            for cookie in cookies:
                # Many Netscape exporters encode a browser-session cookie as 0.
                if cookie.expires == 0:
                    cookie.expires, cookie.discard = None, True
    except (LoadError, OSError, UnicodeError, ValueError, TypeError, KeyError):
        raise ValueError("Cookie file is malformed; use Netscape or Playwright storage-state format") from None
    result = RequestsCookieJar()
    timestamp = time.time()
    for cookie in cookies:
        if cookie.domain not in _DOMAINS:
            continue
        _valid_cookie(cookie)
        if not cookie.is_expired(timestamp):
            result.set_cookie(copy.copy(cookie))
    if not result:
        raise ValueError("Cookie file contains no unexpired B17 cookies")
    return result


def authenticated_html(html: str) -> bool:
    """Recognize a server-rendered personal session from explicit B17 markers.

    A positive session identifier must accompany an account-navigation link.
    An explicit zero identifier always means anonymous access. If scripts have
    been removed from a saved DOM, both known personal-navigation links are
    required inside menu elements. Cookie presence alone does not prove login.
    """
    soup = BeautifulSoup(html, "html.parser")
    identities = []
    for script in soup.find_all("script"):
        identities.extend(int(value) for value in re.findall(
            r"\bvar\s+uid_id\s*=\s*(\d+)\s*;", script.get_text(),
        ))
    if 0 in identities:
        return False
    paths, menu_paths = set(), set()
    for anchor in soup.select("a[href]"):
        parts = urlsplit(urljoin("https://www.b17.ru/", anchor["href"]))
        if parts.scheme not in {"http", "https"} or parts.hostname not in {"b17.ru", "www.b17.ru"}:
            continue
        if parts.path not in _ACCOUNT_PATHS:
            continue
        paths.add(parts.path)
        if anchor.find_parent(lambda node: node.name == "nav" or any(
            "menu" in str(value).lower()
            for value in ([node.get("id", "")] + node.get("class", []))
        )) is not None:
            menu_paths.add(parts.path)
    if identities:
        return any(value > 0 for value in identities) and bool(paths)
    return _ACCOUNT_PATHS.issubset(menu_paths)
