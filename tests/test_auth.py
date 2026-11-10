"""Explicit session imports and authenticated-page evidence, entirely offline."""
from pathlib import Path
import json
import time

import pytest
import requests

from b17_parser.auth import authenticated_html, load_cookies


def write_state(tmp_path, cookies):
    path = tmp_path / "state.json"
    path.write_text(json.dumps({"cookies": cookies, "origins": []}), encoding="utf-8")
    return path


def browser_cookie(**changes):
    value = {"name": "session", "value": "private-value", "domain": ".b17.ru",
             "path": "/", "expires": -1, "secure": True, "httpOnly": True,
             "sameSite": "Lax"}
    value.update(changes)
    return value


def test_playwright_import_preserves_scope_and_attributes(tmp_path):
    expiry = int(time.time()) + 3600
    path = write_state(tmp_path, [browser_cookie(expires=expiry, path="/psiholog/"),
                                  browser_cookie(domain=".example.org", name="unrelated")])
    jar = load_cookies(path)
    assert len(jar) == 1
    cookie = next(iter(jar))
    assert cookie.domain == ".b17.ru"
    assert cookie.path == "/psiholog/"
    assert cookie.secure is True
    assert cookie.expires == expiry
    assert cookie.get_nonstandard_attr("HttpOnly") is True
    assert cookie.get_nonstandard_attr("SameSite") == "Lax"
    session = requests.Session()
    session.cookies.update(jar)
    assert session.prepare_request(requests.Request("GET", "https://www.b17.ru/psiholog/")).headers.get("Cookie")
    assert "Cookie" not in session.prepare_request(requests.Request("GET", "https://example.org/psiholog/")).headers
    assert "Cookie" not in session.prepare_request(requests.Request("GET", "http://www.b17.ru/psiholog/")).headers
    assert "Cookie" not in session.prepare_request(requests.Request("GET", "https://www.b17.ru/other/")).headers


def test_netscape_import_keeps_httponly_session_cookie(tmp_path):
    path = tmp_path / "cookies.txt"
    original = ("# Netscape HTTP Cookie File\n"
                "#HttpOnly_.b17.ru\tTRUE\t/\tTRUE\t\tsession\tprivate-value\n"
                "example.org\tFALSE\t/\tFALSE\t\tunrelated\tignored\n")
    path.write_text(original, encoding="utf-8")
    jar = load_cookies(path)
    assert len(jar) == 1
    cookie = next(iter(jar))
    assert cookie.expires is None
    assert cookie.discard is True
    assert cookie.has_nonstandard_attr("HTTPOnly")
    assert cookie.secure is True
    assert path.read_text(encoding="utf-8") == original


def test_netscape_zero_expiry_represents_a_session_cookie(tmp_path):
    path = tmp_path / "cookies.txt"
    path.write_text("# Netscape HTTP Cookie File\n"
                    ".b17.ru\tTRUE\t/\tTRUE\t0\tsession\tprivate-value\n", encoding="utf-8")
    cookie = next(iter(load_cookies(path)))
    assert cookie.expires is None
    assert cookie.discard is True


@pytest.mark.parametrize("line", [
    ".b17.ru\tTRUE\t/\tTRUE\tprivate-value\tsession\tsecret",
    ".b17.ru\tFALSE\t/\tTRUE\t\tsession\tprivate-value",
    ".b17.ru\tTRUE\t/\tprivate-value\t\tsession\tsecret",
    "private-value\tprivate-value",
])
def test_malformed_netscape_file_emits_no_cookie_values(tmp_path, line, capsys):
    path = tmp_path / "cookies.txt"
    path.write_text("# Netscape HTTP Cookie File\n" + line + "\n", encoding="utf-8")
    with pytest.raises(ValueError) as error:
        load_cookies(path)
    assert "private-value" not in str(error.value)
    assert "private-value" not in capsys.readouterr().err


@pytest.mark.parametrize("domain", ["b17.ru", "www.b17.ru", ".b17.ru"])
def test_only_supported_domain_forms_are_imported(tmp_path, domain):
    assert len(load_cookies(write_state(tmp_path, [browser_cookie(domain=domain)]))) == 1


@pytest.mark.parametrize("domain", ["evilb17.ru", "b17.ru.evil.org", ".www.b17.ru", "sub.b17.ru"])
def test_other_domains_are_not_imported(tmp_path, domain):
    with pytest.raises(ValueError, match="no unexpired B17 cookies"):
        load_cookies(write_state(tmp_path, [browser_cookie(domain=domain)]))


def test_expired_cookie_does_not_count_as_an_available_session(tmp_path):
    with pytest.raises(ValueError, match="no unexpired B17 cookies"):
        load_cookies(write_state(tmp_path, [browser_cookie(expires=1)]))


@pytest.mark.parametrize("contents", ["", "private-value", "{private-value", "[]", '{"cookies":{}}'])
def test_invalid_exports_do_not_expose_contents(tmp_path, contents):
    path = tmp_path / "cookies.txt"
    path.write_text(contents, encoding="utf-8")
    with pytest.raises(ValueError) as error:
        load_cookies(path)
    assert "private-value" not in str(error.value)


@pytest.mark.parametrize("changes", [
    {"value": "private-value\r\nInjected: yes"}, {"name": "private-value\n"},
    {"path": "private-value"}, {"expires": float("nan")}, {"expires": True},
    {"secure": "private-value"}, {"httpOnly": "private-value"}, {"sameSite": "private-value"},
])
def test_malformed_cookie_fields_are_rejected_without_values(tmp_path, changes):
    with pytest.raises(ValueError) as error:
        load_cookies(write_state(tmp_path, [browser_cookie(**changes)]))
    assert "private-value" not in str(error.value)


def test_captured_anonymous_profile_is_not_authenticated():
    # The public fixture omits scripts but contains no personal account links.
    html = (Path(__file__).parent / "fixtures" / "profile_01.html").read_text(encoding="utf-8")
    assert authenticated_html(html) is False


def test_positive_session_requires_account_navigation():
    assert authenticated_html('<script>var uid_id = 123;</script><a href="/privat.php">Messages</a>') is True
    assert authenticated_html('<script>var uid_id = 123;</script>') is False
    assert authenticated_html('<script>var uid_id = 0;</script><nav><a href="/privat.php">Messages</a>'
                              '<a href="/my_response.php">Responses</a></nav>') is False


def test_saved_dom_needs_both_same_site_personal_menu_links():
    links = '<a href="/privat.php">Messages</a><a href="/my_response.php">Responses</a>'
    assert authenticated_html('<div class="menu_left">' + links + '</div>') is True
    assert authenticated_html(links) is False
    assert authenticated_html('<nav><a href="https://evil.org/privat.php">Messages</a>'
                              '<a href="/my_response.php">Responses</a></nav>') is False
    assert authenticated_html('<nav><a href="/privat.php">Messages</a></nav>') is False
