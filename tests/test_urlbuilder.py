"""URL generation is offline, scoped to observed controls, and lossless."""
from copy import deepcopy
from pathlib import Path
from urllib.parse import parse_qs, urlencode, urlsplit

from bs4 import BeautifulSoup
import pytest

from b17_parser.catalog import parse_catalog
from b17_parser.filters import extract_filter_catalog
from b17_parser.urlbuilder import build_url, parse_assignments


FIXTURE = Path(__file__).parent / 'fixtures' / 'filtered.html'
BASE = 'https://www.b17.ru/psiholog/sankt-peterburg/'
CAPTURE_URL = BASE + '?vid=1&price1=3000&price2=5000'


@pytest.fixture
def html():
    soup = BeautifulSoup(FIXTURE.read_text(encoding='utf-8'), 'html.parser')
    # The minimized card fixture omits the separate catalog search form.
    soup.append(BeautifulSoup(
        '<form method=get action="/psiholog/sankt-peterburg/">'
        '<input type=text name=tag minlength=3 placeholder="Найти специалиста" value="">'
        '</form>', 'html.parser'))
    # This price occurs in the site's wizard, but not in the sidebar verifier.
    soup.append(BeautifulSoup(
        '<div id=master_filter_step><div class=step><div class=h>Стоимость</div>'
        '<input type=radio name=f_price2 value=8000 id=wizard8000>'
        '<label for=wizard8000>до 8000 рублей</label></div></div>', 'html.parser'))
    return str(soup)


@pytest.fixture
def reference(html):
    return extract_filter_catalog(html, CAPTURE_URL)


def decoded(url):
    return parse_qs(urlsplit(url).query, keep_blank_values=True)


def test_generated_url_replaces_snapshot_selections(reference):
    result = build_url(reference, {'vid': '1', 'price2': '7000'})
    assert urlsplit(result).path == '/psiholog/sankt-peterburg/'
    assert decoded(result) == {'vid': ['1'], 'price2': ['7000']}
    assert 'price1' not in result


def test_empty_selection_means_unfiltered_catalog(reference):
    assert build_url(reference, {}) == BASE


def test_same_context_base_url_does_not_inherit_old_query(reference):
    result = build_url(reference, {'sex': '2'}, base_url=CAPTURE_URL + '&prt=123#bottom')
    assert decoded(result) == {'sex': ['2']}
    assert not urlsplit(result).fragment


def test_unset_values_are_omitted(reference):
    assert build_url(reference, {'sex': '0', 'byfoto': '0', 'price1': '-', 'spec': ''}) == BASE


def test_boolean_flags_use_observed_numeric_values(reference):
    assert decoded(build_url(reference, {'video': 1, 'cotherapist': '1', 'club_100': '1'})) == {
        'video': ['1'], 'cotherapist': ['1'], 'club_100': ['1'],
    }


def test_multiselect_ids_are_one_query_value_and_deduplicated(reference):
    result = build_url(reference, {'metod': ['97,107', '97'], 'vopros': ['74', '169'], 'location': ['301,345']})
    assert decoded(result) == {'metod': ['97,107'], 'vopros': ['74,169'], 'location': ['301,345']}


def test_literal_cyrillic_search_phrase_is_not_split_or_double_encoded(reference):
    phrase = 'цели, желания и самоопределение = выбор'
    result = build_url(reference, parse_assignments(['tag=' + phrase]))
    assert decoded(result) == {'tag': [phrase]}
    assert '%25D0' not in result


def test_built_url_round_trips_through_selected_control_verifier(reference, html):
    requested = {'vid': '1', 'price1': '3000', 'price2': '5000',
                 'metod': '97,107', 'tag': 'цели, желания и выбор'}
    result = build_url(reference, requested)
    soup = BeautifulSoup(html, 'html.parser')
    for control in soup.select('#master_filter_right input[name=f_metod]'):
        if control.get('value') in {'97', '107'}:
            control['checked'] = ''
    soup.select_one('input[name=tag]')['value'] = requested['tag']
    page = parse_catalog(str(soup), result)
    assert page['selected_filters']['metod'] == ['97', '107']
    assert page['selected_filters']['tag'] == [requested['tag']]
    assert page['requested_filters']['tag'] == [requested['tag']]


@pytest.mark.parametrize('amount', ['7500', '8000'])
def test_unlisted_and_wizard_only_thresholds_are_not_silently_allowed(reference, amount):
    assert '8000' in {option['value'] for option in reference['filters']['price2']['ui_additional_values']}
    with pytest.raises(ValueError, match='Unsupported value'):
        build_url(reference, {'price2': amount})


def test_contradictory_price_bounds_are_rejected(reference):
    with pytest.raises(ValueError, match='Minimum price'):
        build_url(reference, {'price1': '5000', 'price2': '3000'})


@pytest.mark.parametrize('parameter,value', [('vid', '1,2'), ('sex', ['1', '2']), ('price2', ['3000', '5000']), ('spec', ['1', '2'])])
def test_single_choice_filter_rejects_multiple_values(reference, parameter, value):
    with pytest.raises(ValueError, match='only one value'):
        build_url(reference, {parameter: value})


@pytest.mark.parametrize('parameter', ['online', 'frmt', 'f_vid', 'fav', 'page', 'unknown'])
def test_unknown_or_non_query_controls_are_rejected(reference, parameter):
    with pytest.raises(ValueError, match='Unknown filter'):
        build_url(reference, {parameter: '1'})


def test_unknown_radio_value_is_rejected(reference):
    with pytest.raises(ValueError, match='Unsupported value'):
        build_url(reference, {'sex': '3'})


def test_photo_only_view_is_not_accepted_by_card_crawler(reference):
    with pytest.raises(ValueError, match='unsupported by crawl'):
        build_url(reference, {'byfoto': '1'})


def test_short_search_text_is_rejected(reference):
    with pytest.raises(ValueError, match='at least 3 characters'):
        build_url(reference, {'tag': 'я'})


def test_two_literal_search_phrases_are_not_joined(reference):
    with pytest.raises(ValueError, match='only one value'):
        build_url(reference, {'tag': ['первая фраза', 'вторая фраза']})


@pytest.mark.parametrize('target', ['https://www.b17.ru/psiholog/moskva/', 'https://www.b17.ru/online/'])
def test_city_or_format_change_requires_its_own_reference(reference, target):
    with pytest.raises(ValueError, match='another catalog'):
        build_url(reference, {'location': '301'}, base_url=target)


def test_external_base_is_rejected_before_url_creation(reference):
    with pytest.raises(ValueError, match='b17.ru'):
        build_url(reference, {}, base_url='https://example.org/psiholog/sankt-peterburg/')


@pytest.mark.parametrize('value', [True, None, {'value': '1'}, 1.5])
def test_non_scalar_or_boolean_option_values_are_rejected(reference, value):
    with pytest.raises(ValueError, match='string or numeric'):
        build_url(reference, {'vid': value})


@pytest.mark.parametrize('invalid', [None, [], {}, {'schema_version': 99}, {'schema_version': 1, 'source': []}, {'schema_version': 1, 'source': {}}])
def test_malformed_reference_fails_as_a_validation_error(invalid):
    with pytest.raises(ValueError):
        build_url(invalid, {})


@pytest.mark.parametrize('options', [None, 'not-options', [1], [{}]])
def test_malformed_option_metadata_fails_as_a_validation_error(reference, options):
    broken = deepcopy(reference)
    broken['filters']['vid']['options'] = options
    with pytest.raises(ValueError, match='Invalid option list'):
        build_url(broken, {'vid': '1'})


def test_assignments_preserve_equals_in_text_and_repeated_fields():
    assert parse_assignments(['tag=выбор = цель', 'metod=97', 'metod=107']) == {
        'tag': ['выбор = цель'], 'metod': ['97', '107'],
    }


@pytest.mark.parametrize('assignment', ['vid', '=1', ' =1'])
def test_malformed_assignment_is_rejected(assignment):
    with pytest.raises(ValueError):
        parse_assignments([assignment])
