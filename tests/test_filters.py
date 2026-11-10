from pathlib import Path

import pytest

from b17_parser.filters import extract_filter_catalog, render_filter_guide


FIXTURE = Path(__file__).parent / 'fixtures' / 'filter_controls.html'
URL = 'https://www.b17.ru/psiholog/sankt-peterburg/?vid=1&price1=3000&price2=5000'


def reference():
    return extract_filter_catalog(FIXTURE.read_text(), URL, {'capture_type': 'reduced real HTML'})


def test_all_observed_filter_families_and_exact_option_counts():
    result = reference()
    assert list(result['filters']) == ['vid', 'location', 'price1', 'price2', 'vopros', 'metod', 'sex', 'spec',
                                       'video', 'cotherapist', 'club_100', 'byfoto', 'sort', 'tag']
    assert len(result['filters']['vopros']['options']) == 46
    assert len(result['filters']['metod']['options']) == 37
    assert len([x for x in result['filters']['location']['options'] if x['value']]) == 76
    assert result['scope']['city_id'] == '143'
    assert result['scope']['city'] == 'Санкт-Петербург'


def test_prices_keep_wizard_only_values_separate_from_crawler_options():
    field = reference()['filters']['price2']
    assert [o['value'] for o in field['options']] == ['-', '1000', '1500', '2000', '3000', '5000', '7000']
    assert [o['value'] for o in field['ui_additional_values']] == ['2500', '4500', '6000', '8000']
    assert '7500' not in {o['value'] for o in field['options'] + field['ui_additional_values']}
    assert field['label'] == 'Стоимость: до'
    assert field['bound'] == 'maximum'
    assert field['default_values'] == ['-']
    assert field['selected_values'] == ['5000']
    assert field['verified_selected_values'] == ['5000']


def test_multi_select_cardinality_and_semantics_do_not_invent_and_or():
    fields = reference()['filters']
    for key in ['vopros', 'metod', 'location']:
        assert fields[key]['multiple'] is True
        assert fields[key]['max_values'] is None
        assert fields[key]['multi_value_encoding']['query_separator'] == ','
        assert fields[key]['multi_value_encoding']['boolean_combination'] == 'unknown'
    assert fields['sex']['multiple'] is False
    assert fields['sex']['max_values'] == 1
    assert {o['value']:o['label'] for o in fields['sex']['options']} == {'0':'Любой', '2':'Жен', '1':'Муж'}


def test_specific_flags_do_not_share_ambiguous_more_label():
    fields = reference()['filters']
    assert fields['video']['label'] == 'Видеоприветствие'
    assert fields['cotherapist']['label'] == 'Ко-терапевты'
    assert fields['club_100']['label'] == '«Клуб 100»'
    assert fields['sort']['label'] == 'Порядок'
    assert fields['sort']['role'] == 'sort'
    assert fields['byfoto']['role'] == 'display'
    assert fields['byfoto']['unsupported_crawl_values'] == ['1']
    assert fields['byfoto']['options'][0]['crawl_compatible'] is True
    assert fields['byfoto']['options'][1]['crawl_compatible'] is False


def test_route_switch_is_not_misrepresented_as_online_query():
    result = reference()
    assert [r['url'] for r in result['routes']] == ['https://www.b17.ru/psiholog/sankt-peterburg/', 'https://www.b17.ru/online/']
    assert 'frmt' not in result['filters']
    assert 'online' not in result['filters']
    assert len(result['route_controls']) == 2
    assert all(r['query_parameter'] is None for r in result['route_controls'])
    assert {r['name'] for r in result['internal_controls']} == {'f_city', 'f_mod'}


def test_search_form_preserves_exact_text_and_minimum_without_keyword_classification():
    html = FIXTURE.read_text().replace('name="tag"', 'name="tag"', 1)
    from bs4 import BeautifulSoup
    soup = BeautifulSoup(html, 'html.parser')
    soup.select_one('input[name=tag]')['value'] = 'Принятие решения, цель'
    field = extract_filter_catalog(str(soup), URL)['filters']['tag']
    assert field['kind'] == 'text'
    assert field['minimum_length'] == field['min_length'] == 3
    assert field['selected_values'] == ['Принятие решения, цель']
    assert field['crawl_compatible'] is True


def test_metadata_needs_no_cards_and_does_not_validate_snapshot_query():
    result = extract_filter_catalog(FIXTURE.read_text(), 'https://www.b17.ru/psiholog/sankt-peterburg/?metod=107')
    assert result['filters']['vid']['selected_values'] == ['1']
    assert result['filters']['vid']['verified_selected_values'] == []
    assert 'cards' not in result
    with pytest.raises(ValueError, match='filter panel'):
        extract_filter_catalog('<h1>Blocked or missing</h1>', URL)


def test_city_links_are_scoped_to_actual_city_list_and_deduplicated():
    cities = '''<nav><a href=/psiholog/moskva/>Wrong heading</a></nav><div class=masters_city_list>
    <div><a href=/psiholog/moskva/>Москва</a></div><div><a href=/psiholog/sankt-peterburg/>Санкт-Петербург</a></div>
    <a href=/psiholog/moskva/>Duplicate</a><a href=https://evil.example/psiholog/evil/>Foreign</a>
    <a href=/psiholog/>Index</a><a href=/psiholog/moskva/?fav=1>Favorites</a></div>'''
    result = extract_filter_catalog(FIXTURE.read_text(), URL, city_html=cities)
    assert [(c['label'],c['slug']) for c in result['cities']] == [('Москва','moskva'), ('Санкт-Петербург','sankt-peterburg')]


def test_no_navigation_secrets_event_handlers_or_full_html_are_exported():
    injected = FIXTURE.read_text().replace('</body>', '<nav><a href="/privat.php?skey=secret_token_123">My messages</a><input name=session_cookie value=secret_cookie_456></nav></body>')
    result = extract_filter_catalog(injected, URL)
    import json
    encoded = json.dumps(result, ensure_ascii=False)
    assert 'secret_token_123' not in encoded
    assert 'secret_cookie_456' not in encoded
    assert 'onclick' not in encoded
    assert '<input' not in encoded


def test_complete_standalone_guide_preserves_every_option_label_and_value():
    result = reference()
    guide = render_filter_guide(result)
    for key, field in result['filters'].items():
        assert f'`{key}`' in guide
        for option in field['options'] + field['ui_additional_values']:
            assert option['label'] in guide
            assert f"`{option['value']}`" in guide
    assert 'логика «И»/«ИЛИ» не установлена' in guide
    assert 'Не округляйте бюджет' in guide
    assert 'Дополнительные варианты вне боковой панели' in guide
    assert 'Построение URL не выполняет сетевых запросов' in guide


def test_html_snapshot_input_is_not_mutated():
    html = FIXTURE.read_text()
    assert extract_filter_catalog(html, URL) == extract_filter_catalog(html, URL)


@pytest.mark.parametrize('method,action', [('post','/psiholog/sankt-peterburg/'), ('get','https://evil.example/psiholog/sankt-peterburg/'), ('get','/privat.php')])
def test_unrelated_or_post_search_forms_are_not_filters(method, action):
    from bs4 import BeautifulSoup
    soup = BeautifulSoup(FIXTURE.read_text(), 'html.parser')
    form = soup.select_one('input[name=tag]').find_parent('form')
    form['method'], form['action'] = method, action
    assert 'tag' not in extract_filter_catalog(str(soup), URL)['filters']


def test_valid_search_after_invalid_form_is_discovered():
    html = FIXTURE.read_text().replace('<body>', '<body><form method=post action=https://evil.example/psiholog/sankt-peterburg/><input name=tag placeholder=Private value=do_not_export></form>')
    result = extract_filter_catalog(html, URL)
    assert result['filters']['tag']['label'] == 'Найти специалиста'
    assert 'do_not_export' not in str(result)
