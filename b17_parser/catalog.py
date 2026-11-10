"""Read B17 catalog cards and verify the server-rendered filter state."""

from __future__ import annotations

import re
from urllib.parse import parse_qsl, urlencode, urljoin, urlsplit, urlunsplit

from bs4 import BeautifulSoup, Tag


_TRACKING = {"prt", "fbclid", "gclid", "yclid", "ysclid"}
_DEFAULT_OFF = {"", "0", "-"}


def normalize_url(url: str, base: str | None = None, profile: bool = False) -> str:
    """Return an HTTPS B17 URL without fragments or known tracking parameters.

    Relative links require a B17 base. Other hosts, credentials, ports and
    non-HTTP schemes are rejected before a caller can fetch the result.
    Profile URLs use the single canonical path and discard query parameters.
    """
    if not isinstance(url, str) or not url.strip():
        raise ValueError("A nonempty B17 URL is required")
    absolute = urljoin(base, url.strip()) if base else url.strip()
    parts = urlsplit(absolute)
    if (
        parts.scheme.lower() not in {"http", "https"}
        or parts.hostname not in {"b17.ru", "www.b17.ru"}
        or parts.username is not None
        or parts.password is not None
        or parts.port is not None
        or "\\" in parts.path
    ):
        raise ValueError("Only public HTTP(S) b17.ru URLs without credentials or ports are supported")
    path = parts.path or "/"
    path = re.sub(r"/{2,}", "/", path)
    if any(part in {".", ".."} for part in path.split("/")):
        raise ValueError("Dot segments are not supported in B17 URLs")
    if profile:
        if not re.fullmatch(r"/[\w-]+/?", path):
            raise ValueError("A profile URL must contain a single profile path")
        path = path.rstrip("/") + "/"
        query = ""
    else:
        query = urlencode(
            [(k, v) for k, v in parse_qsl(parts.query, keep_blank_values=True)
             if k.lower() not in _TRACKING and not k.lower().startswith("utm_")]
        )
    return urlunsplit(("https", "www.b17.ru", path, query, ""))


def page_url(url: str, page: int) -> str:
    """Set an absolute catalog page while preserving all selected filters."""
    if isinstance(page, bool) or not isinstance(page, int) or page < 1:
        raise ValueError("Page must be a positive integer")
    parts = urlsplit(normalize_url(url))
    query = [(k, v) for k, v in parse_qsl(parts.query, keep_blank_values=True)
             if k not in {"page", "page_plus"}]
    query.append(("page", str(page)))
    return urlunsplit(parts._replace(query=urlencode(query)))


def _text(node: Tag | None) -> str:
    if node is None:
        return ""
    # Redaction also applies to short descriptions and catalog evidence.
    from .profile import redact_contacts

    return redact_contacts(re.sub(r"\s+", " ", node.get_text(" ", strip=True)).strip())


def _values(raw: str) -> list[str]:
    return [v for v in re.split(r"[,\s]+", raw.strip()) if v]


def _filter_state(root: Tag) -> tuple[dict, dict]:
    selected: dict[str, list[str]] = {}
    available: dict[str, dict] = {}
    for control in root.select("input[name], select[name]"):
        name = control.get("name", "")
        if not name.startswith("f_") or name in {"f_mod", "f_city"}:
            continue
        key = name[2:]
        group = control.find_parent("div", class_="f")
        heading = _text(group.select_one(".fh")) if group else key
        kind = control.get("type", "select" if control.name == "select" else "text")
        metadata = available.setdefault(key, {"label": heading, "kind": kind, "options": []})
        selected.setdefault(key, [])
        if control.name == "select":
            metadata["multiple"] = control.has_attr("multiple")
            options = control.select("option")
            for option in options:
                value = str(option.get("value", option.get_text(strip=True)))
                metadata["options"].append({"value": value, "label": _text(option)})
                if option.has_attr("selected") and value not in _DEFAULT_OFF:
                    selected[key].append(value)
            # An unmarked select defaults to its first option in browsers.
            if not any(o.has_attr("selected") for o in options) and options and not control.has_attr("multiple"):
                default = str(options[0].get("value", options[0].get_text(strip=True)))
                if default not in _DEFAULT_OFF:
                    selected[key].append(default)
        else:
            value = str(control.get("value", ""))
            label_node = control.find_parent("div", class_=["radio", "checkbox"])
            metadata["options"].append({"value": value, "label": _text(label_node) or value})
            if control.has_attr("checked") and value not in _DEFAULT_OFF:
                selected[key].append(value)
    return selected, available


def _verify_filters(url: str, selected: dict, available: dict) -> dict[str, list[str]]:
    requested: dict[str, list[str]] = {}
    for key, raw in parse_qsl(urlsplit(url).query, keep_blank_values=True):
        if key in {"page", "page_plus"}:
            if not raw.isdigit() or int(raw) < 1:
                raise ValueError(f"Invalid pagination parameter {key}={raw!r}")
            continue
        if key == "fav":
            raise ValueError("The favorites filter requires a personal session and is not supported")
        if key not in available:
            raise ValueError(f"The catalog does not expose a verifiable filter named {key!r}")
        if available[key].get("kind") == "text":
            requested.setdefault(key, []).append(raw.strip())
        else:
            requested.setdefault(key, []).extend(_values(raw))
    for key, values in requested.items():
        expected = {v for v in values if v not in _DEFAULT_OFF}
        actual = set(selected.get(key, []))
        if expected != actual:
            raise ValueError(
                f"Filter {key!r} was not applied by B17: requested {sorted(expected)}, selected {sorted(actual)}"
            )
    # Without cookies, an unexpected non-default selection must not silently
    # change the user's requested search. Defaults are normalized away above.
    for key, values in selected.items():
        if values and key not in requested:
            raise ValueError(f"B17 selected an unrequested filter {key!r}: {values}")
    return requested


def parse_catalog(html: str, url: str) -> dict:
    """Parse one catalog page and verify every requested filter against HTML.

    Invalid markup, city pickers, unknown query filters and silently ignored
    selections raise ValueError rather than looking like an exhausted search.
    The returned next_page is an absolute page number, not a link to follow;
    callers should retain the first page's total when later pages omit it.
    The advertised total is metadata and never a pagination stopping rule.
    Numbered page links take priority over hidden AJAX counters: a hidden
    counter can still be present at the numbered list's terminal page.
    """
    url = normalize_url(url)
    soup = BeautifulSoup(html, "html.parser")
    container = soup.select_one("#items_list, .items_list")
    filters = soup.select_one("#master_filter_right")
    if container is None or filters is None:
        raise ValueError("No supported B17 catalog found (city selection, login, challenge, or changed markup)")
    selected, available = _filter_state(filters)
    # The catalog's own search form uses a literal text query, unlike numeric
    # multi-select IDs. Do not split a phrase into separate filter values.
    for form in soup.select("form[action]"):
        if str(form.get("method", "get")).lower() != "get":
            continue
        try:
            action = normalize_url(form.get("action", ""), base=url)
        except ValueError:
            continue
        search = form.select_one("input[name='tag']")
        if search is not None and urlsplit(action).path == urlsplit(url).path:
            available["tag"] = {"label": search.get("placeholder", "Найти специалиста"),
                                "kind": "text", "options": [], "min_length": int(search.get("minlength", 0))}
            value = search.get("value", "").strip()
            selected["tag"] = [value] if value else []
            break
    requested = _verify_filters(url, selected, available)
    context = _text(soup.select_one("h1")) or None
    city_node = soup.select_one("#maket_body_right_content [onclick*='city_ppp_search_show']") or soup.select_one("#maket_body_right_content > .menu-blue-box3 > span.like_a")
    city = re.sub(r"^г\.\s*", "", _text(city_node)) or None
    city_id = filters.select_one("input[name='f_city']")
    cards = []
    seen = set()
    warnings = []
    items = container.select(".item")
    for item in items:
        link = item.select_one("a.h[href]")
        if link is None:
            raise ValueError("A catalog item has no named profile link; use detailed view or update selectors")
        profile_url = normalize_url(link["href"], base=url, profile=True)
        if profile_url in seen:
            warnings.append(f"Duplicate catalog card omitted: {profile_url}")
            continue
        seen.add(profile_url)
        anchor = item.select_one("[id^='spec_']")
        identifier = (anchor.get("id", "") if anchor else link.get("name", ""))
        match = re.search(r"spec_?(\d+)", identifier)
        review = item.select_one("a[href*='#otzyv']")
        review_match = re.search(r"([\d\s]+)\s*отзыв", _text(review), re.I)
        cards.append({
            "id": match.group(1) if match else None,
            "name": _text(link),
            "url": profile_url,
            "summary": _text(item.select_one(".t")) or None,
            "status": _text(item.select_one(".s")) or None,
            "city": city,
            "price_text": _text(item.select_one(".price1")) or None,
            "statistics_text": _text(item.select_one(".price2")) or None,
            "reviews_count": int(re.sub(r"\s", "", review_match.group(1))) if review_match else None,
            "source_catalog_url": url,
        })
    notice = soup.select_one(".list_blue_info_filter")
    pager = soup.select_one("#items_page")
    total = None
    for text in [_text(notice), _text(pager)]:
        match = re.search(r"(?:Найден[аоы]?\s*|из\s+)([\d\s]+)\s*специалист", text, re.I)
        if match:
            total = int(re.sub(r"\s", "", match.group(1)))
            break
        # The pager puts the noun before 'из 300'.
        match = re.search(r"Показан[аоы]?.*?\bиз\s+([\d\s]+)", text, re.I)
        if match:
            total = int(re.sub(r"\s", "", match.group(1)))
            break
    query_values = dict(parse_qsl(urlsplit(url).query))
    current = max(int(query_values.get("page", "1")), int(query_values.get("page_plus", "1")))
    explicit_empty = total == 0 or bool(re.search(
        r"(?:не найден|нет специалист|найден[аоы]?\s*0)", _text(container), re.I
    ))
    if not cards and not explicit_empty:
        # Later absolute pages can legitimately contain no cards. A first-page
        # empty response without a zero-results message is a layout failure.
        if current <= 1:
            raise ValueError("B17 returned no parseable cards and no explicit empty-results indication")
    next_control = soup.select_one("#backend_page")
    next_page = None
    hidden_next = None
    page_list = soup.select_one("#page_list")
    numbered_pages = set()
    pagination_method = "empty_page" if not cards else "no_next_marker"
    terminal_evidence = "explicit_zero_results" if explicit_empty else "empty_catalog_page" if not cards else None
    if next_control is not None:
        raw_next = str(next_control.get("value", ""))
        if not raw_next.isdigit() or int(raw_next) < 1:
            raise ValueError("B17 returned an invalid next-page marker")
        hidden_next = int(raw_next)
    if cards and page_list is not None:
        active = page_list.select_one("a.on, span.on")
        active_text = _text(active)
        if active_text.isdigit() and int(active_text) != current:
            raise ValueError(f"B17 returned page {active_text} when page {current} was requested")
        for link in page_list.select("a[href]"):
            query = dict(parse_qsl(urlsplit(urljoin(url, link["href"])).query))
            value = query.get("page", "")
            if value.isdigit() and int(value) > 0:
                numbered_pages.add(int(value))
        if active_text.isdigit():
            numbered_pages.add(int(active_text))
        if not numbered_pages:
            raise ValueError("B17 returned an unrecognized numbered pagination control")
        pagination_method = "page_links"
        if max(numbered_pages) > current:
            # A list may show only nearby pages and its final page. Advance
            # sequentially rather than jumping to a distant visible link.
            next_page = current + 1
        else:
            terminal_evidence = "numbered_pagination_end"
    elif cards and hidden_next is not None:
        if hidden_next != current + 1:
            raise ValueError(f"B17 returned nonsequential next-page marker {hidden_next} after page {current}")
        pagination_method = "backend_page"
        next_page = hidden_next
    elif cards:
        terminal_evidence = "no_pagination_marker"
        warnings.append("No pagination marker found; this does not prove that all B17 specialists were available")
    notice_node = notice.select_one("[title]") if notice else None
    return {
        "url": url,
        "cards": cards,
        "total": total,
        "city": city,
        "city_id": city_id.get("value") if city_id else None,
        "context": context,
        "requested_filters": requested,
        "selected_filters": selected,
        "available_filters": available,
        "filter_notice": notice_node.get("title") if notice_node else None,
        "next_page": next_page,
        "pagination_has_next": next_page is not None,
        "terminal_evidence": terminal_evidence,
        "pagination": {
            "current_page": current,
            "method": pagination_method,
            "visible_last_page": max(numbered_pages) if numbered_pages else None,
            "hidden_next_page": hidden_next,
        },
        "warnings": warnings,
    }
