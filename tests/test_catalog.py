"""Catalog contracts exercised with fictional cards and observed UI controls."""

from pathlib import Path

from bs4 import BeautifulSoup
import pytest

from b17_parser.catalog import normalize_url, page_url, parse_catalog


FIXTURE = Path(__file__).parent / "fixtures" / "filtered.html"
URL = "https://www.b17.ru/psiholog/sankt-peterburg/?vid=1&price1=3000&price2=5000"


@pytest.fixture
def html():
    return FIXTURE.read_text(encoding="utf-8")


def test_synthetic_catalog_cards_and_filters(html):
    page = parse_catalog(html, URL)
    assert len(page["cards"]) == 10
    assert page["total"] == 300
    assert page["next_page"] == 2
    assert page["city"] == "Санкт-Петербург"
    assert page["city_id"] == "143"
    assert page["selected_filters"]["vid"] == ["1"]
    assert page["selected_filters"]["price1"] == ["3000"]
    assert page["selected_filters"]["price2"] == ["5000"]
    assert "от 3000 руб" in page["filter_notice"]
    assert page["available_filters"]["vid"]["options"][0]["label"] == "Индивидуально"
    first = page["cards"][0]
    assert first["id"] == "900000001"
    assert first["name"] == "Тестовый специалист 01"
    assert first["url"] == "https://www.b17.ru/fixture_profile_01/"
    assert first["reviews_count"] == 344
    assert "4 000" in first["price_text"]
    assert first["source_catalog_url"] == URL
    assert len({card["url"] for card in page["cards"]}) == 10


def test_later_page_keeps_hidden_next_when_visible_control_absent(html):
    soup = BeautifulSoup(html, "html.parser")
    soup.select_one(".list_blue_info_filter").decompose()
    soup.select_one("#ajax_page_next").decompose()
    soup.select_one("#backend_page")["value"] = "3"
    page = parse_catalog(str(soup), page_url(URL, 2))
    assert page["total"] is None
    assert page["next_page"] == 3
    assert len(page["cards"]) == 10


def test_reported_300_does_not_override_next_page_31(html):
    soup = BeautifulSoup(html, "html.parser")
    soup.select_one("#backend_page")["value"] = "31"
    page = parse_catalog(str(soup), page_url(URL, 30))
    assert page["total"] == 300
    assert page["next_page"] == 31
    assert page["pagination_has_next"] is True
    assert page["terminal_evidence"] is None
    assert page["pagination"]["method"] == "backend_page"


def test_numbered_terminal_page_overrides_residual_hidden_counter(html):
    soup = BeautifulSoup(html, "html.parser")
    soup.select_one("#backend_page")["value"] = "31"
    soup.select_one("#items_page").append(BeautifulSoup(
        '<div id="page_list"><a href="?page=29">29</a><a class="on">30</a></div>', "html.parser"
    ))
    page = parse_catalog(str(soup), page_url(URL, 30))
    assert page["next_page"] is None
    assert page["pagination_has_next"] is False
    assert page["terminal_evidence"] == "numbered_pagination_end"
    assert page["pagination"]["visible_last_page"] == 30
    assert page["pagination"]["hidden_next_page"] == 31


def test_numbered_next_beyond_300_is_followed_sequentially(html):
    soup = BeautifulSoup(html, "html.parser")
    soup.select_one("#backend_page")["value"] = "31"
    soup.select_one("#items_page").append(BeautifulSoup(
        '<div id="page_list"><a class="on">30</a><a href="?page=100">100</a></div>', "html.parser"
    ))
    page = parse_catalog(str(soup), page_url(URL, 30))
    assert page["next_page"] == 31
    assert page["pagination"]["visible_last_page"] == 100
    assert page["pagination"]["method"] == "page_links"


def test_server_returning_wrong_numbered_page_is_rejected(html):
    soup = BeautifulSoup(html, "html.parser")
    soup.select_one("#items_page").append(BeautifulSoup(
        '<div id="page_list"><a class="on">1</a><a href="?page=2">2</a></div>', "html.parser"
    ))
    with pytest.raises(ValueError, match="when page 31 was requested"):
        parse_catalog(str(soup), page_url(URL, 31))


def test_nonsequential_hidden_counter_is_rejected(html):
    soup = BeautifulSoup(html, "html.parser")
    soup.select_one("#backend_page")["value"] = "5"
    with pytest.raises(ValueError, match="nonsequential"):
        parse_catalog(str(soup), page_url(URL, 2))


def test_cumulative_page_url_uses_last_already_loaded_page(html):
    soup = BeautifulSoup(html, "html.parser")
    soup.select_one("#backend_page")["value"] = "3"
    assert parse_catalog(str(soup), URL + "&page_plus=2")["next_page"] == 3


def test_fixture_contains_only_catalog_evidence_without_scripts_or_contacts(html):
    soup = BeautifulSoup(html, "html.parser")
    assert not soup.select("script, style, img, #otzyv, [id^='kontakt_'], .b0.b2")
    assert soup.select_one("#master_filter_right")
    assert soup.select_one("#items_list")
    assert soup.select_one("#items_page")


@pytest.mark.parametrize("extra", ["&unknown=1", "&map=1", "&fav=1", "&price2=8000", "&sex=1"])
def test_unknown_or_unapplied_filters_are_not_silently_accepted(html, extra):
    with pytest.raises(ValueError):
        parse_catalog(html, URL + extra)


def test_unrequested_server_selection_is_not_silently_accepted(html):
    with pytest.raises(ValueError, match="unrequested filter"):
        parse_catalog(html, "https://www.b17.ru/psiholog/sankt-peterburg/")


def test_multi_select_filter_verified_as_set(html):
    soup = BeautifulSoup(html, "html.parser")
    methods = soup.select('#master_filter_right input[name="f_metod"]')[:2]
    for method in methods:
        method["checked"] = ""
    values = [method["value"] for method in methods]
    page = parse_catalog(str(soup), URL + "&metod=" + ",".join(reversed(values)))
    assert page["selected_filters"]["metod"] == values


def test_deduplication_and_no_silent_truncation(html):
    soup = BeautifulSoup(html, "html.parser")
    first = soup.select_one(".items_list .item")
    first.select_one(".t").string = "Полезный текст " * 5000 + "КОНЕЦ_АНКЕТЫ"
    soup.select_one("#items_list").append(BeautifulSoup(str(first), "html.parser"))
    page = parse_catalog(str(soup), URL)
    assert len(page["cards"]) == 10
    assert page["cards"][0]["summary"].endswith("КОНЕЦ_АНКЕТЫ")
    assert page["warnings"]


def test_card_without_named_link_fails_instead_of_being_skipped(html):
    soup = BeautifulSoup(html, "html.parser")
    soup.select_one(".items_list a.h").decompose()
    with pytest.raises(ValueError, match="named profile link"):
        parse_catalog(str(soup), URL)


def test_card_description_redacts_contacts(html):
    soup = BeautifulSoup(html, "html.parser")
    soup.select_one(".items_list .t").string = "Психолог +1-202-555-0142 email@example.com https://t.me/contact_handle"
    page = parse_catalog(str(soup), URL)
    text = page["cards"][0]["summary"]
    assert "555-0142" not in text
    assert "email@example.com" not in text
    assert "contact_handle" not in text
    assert "Психолог" in text


def test_city_picker_or_challenge_rejected():
    with pytest.raises(ValueError, match="No supported B17 catalog"):
        parse_catalog("<h1>Выберите город</h1><a href='/psiholog/sankt-peterburg/'>СПб</a>", URL)


def test_explicit_empty_results_is_success(html):
    soup = BeautifulSoup(html, "html.parser")
    for card in soup.select(".items_list .item"):
        card.decompose()
    soup.select_one(".list_blue_info_filter span").string = "Найдены 0 специалистов"
    page = parse_catalog(str(soup), URL)
    assert page["total"] == 0
    assert page["cards"] == []
    assert page["next_page"] is None


def test_empty_first_page_without_explicit_reason_rejected(html):
    soup = BeautifulSoup(html, "html.parser")
    for element in soup.select(".items_list .item, .list_blue_info_filter, #items_page"):
        element.decompose()
    with pytest.raises(ValueError, match="no parseable cards"):
        parse_catalog(str(soup), URL)
    assert parse_catalog(str(soup), page_url(URL, 31))["next_page"] is None


@pytest.mark.parametrize("bad", [
    "https://evil.example/user/",
    "//evil.example/user/",
    "file:///tmp/user/",
    "https://b17.ru:443/user/",
    "https://user:secret@b17.ru/user/",
    "javascript:alert(1)",
    "https://b17.ru/a/../user/",
])
def test_url_normalization_rejects_external_or_credentialed_urls(bad):
    with pytest.raises(ValueError):
        normalize_url(bad)


def test_normalization_removes_tracking_and_fragment():
    assert normalize_url("http://b17.ru/person/?prt=123&utm_source=x#otzyv", profile=True) == "https://www.b17.ru/person/"
    assert normalize_url("/person/?prt=123&utm_source=x#otzyv", URL) == "https://www.b17.ru/person/"
    assert normalize_url(URL + "&prt=123&utm_source=foo#bottom") == URL


def test_page_url_preserves_filters_and_replaces_cumulative_pagination():
    result = page_url(URL + "&page=3&page_plus=5&prt=123#bottom", 4)
    assert result == URL + "&page=4"


@pytest.mark.parametrize("bad", [0, -1, True, "2"])
def test_page_url_requires_positive_integer(bad):
    with pytest.raises(ValueError):
        page_url(URL, bad)


def test_price_placeholder_is_an_unset_filter(html):
    soup = BeautifulSoup(html, 'html.parser')
    for node in soup.select('#master_filter_right [checked], #master_filter_right option[selected]'):
        node.attrs.pop('checked', None)
        node.attrs.pop('selected', None)
    # A browser selects the first dash option when no explicit option is marked.
    page = parse_catalog(str(soup), 'https://www.b17.ru/psiholog/sankt-peterburg/')
    assert page['selected_filters']['price1'] == []
    assert page['selected_filters']['price2'] == []


def test_catalog_search_verifies_the_complete_phrase(html):
    soup = BeautifulSoup(html, 'html.parser')
    form = BeautifulSoup('<form action="/psiholog/sankt-peterburg/"><input name=tag minlength=3 value="сложности с целями"></form>', 'html.parser')
    soup.append(form)
    from urllib.parse import urlencode
    page = parse_catalog(str(soup), URL + '&' + urlencode({'tag': 'сложности с целями'}))
    assert page['selected_filters']['tag'] == ['сложности с целями']
    with pytest.raises(ValueError, match='not applied'):
        parse_catalog(str(soup), URL + '&' + urlencode({'tag': 'другой запрос'}))
