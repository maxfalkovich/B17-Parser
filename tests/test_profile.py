"""Profile extraction contracts on fictional and adversarial HTML."""
from pathlib import Path

import pytest

from b17_parser.profile import clean_text, parse_price, parse_profile, redact_contacts
from bs4 import BeautifulSoup

FIXTURE = Path(__file__).parent / 'fixtures' / 'profile_01.html'
URL = 'https://www.b17.ru/fixture_profile_01/'


def test_synthetic_profile_preserves_full_education_and_services():
    data = parse_profile(FIXTURE.read_text(), URL)
    assert data['name'] == 'Тестовый специалист 01'
    assert data['id'] == '900000001'
    assert data['cities'] == ['Москва', 'Санкт-Петербург', 'Петергоф']
    assert data['experience_years'] == 22
    assert data['reviews_count'] == 344
    assert data['price_rub'] == 4000
    assert data['duration_minutes'] == 50
    assert data['online'] is True and data['offline'] is True
    assert len(data['education_entries']) >= 20
    assert 'Синтетическая учебная программа 25' in data['education']
    assert 'Годы обучения: 2005 - 2010' in data['education']
    assert 'НАЧАЛО_ТЕСТОВОЙ_АНКЕТЫ_01' in data['raw_profile_text']
    assert 'КОНЕЦ_ТЕСТОВОЙ_АНКЕТЫ_01' in data['raw_profile_text']
    assert 'НЕ_ВКЛЮЧАТЬ_ОТЗЫВ_В_АНКЕТУ' not in data['raw_profile_text']
    assert 'НЕ_ВКЛЮЧАТЬ_СТАТЬЮ_В_АНКЕТУ' not in data['raw_profile_text']
    assert data['approaches'] == ['Тестовый подход А', 'Тестовый подход Б']
    assert data['raw_profile_text_chars'] == len(data['raw_profile_text'])
    assert '555' not in data['about']
    assert 't.me/' not in data['raw_profile_text']
    assert len(data['about']) > 6000


def test_long_hidden_content_and_absent_information():
    text = 'Полный текст без усечения. ' * 5000
    data = parse_profile('<h1>Иван Иванов</h1><div id="main" class="vkladki_body">' + text +
                         '<div style="display:none">Самый конец.</div></div>', URL)
    assert text.strip() in data['about']
    assert data['about'].endswith('Самый конец.')
    assert data['experience_years'] is None
    assert data['price_rub'] is None
    assert data['education'] is None
    assert data['online'] is None


@pytest.mark.parametrize('value,kind,low,high,exact', [
    ('Стоимость: 4 500 рублей за 50 минут', 'exact', 4500, 4500, 4500),
    ('От 3 000 до 7 500 руб.', 'range', 3000, 7500, None),
    ('4000–5000 рублей', 'range', 4000, 5000, None),
    ('от 5000 руб.', 'from', 5000, None, None),
    ('до 5000 руб.', 'up_to', None, 5000, None),
    ('Бесплатная публичная консультация', 'free', 0, 0, 0),
    ('Цена по договоренности', None, None, None, None),
])
def test_prices_preserve_bounds(value, kind, low, high, exact):
    result = parse_price(value)
    assert (result['price_kind'], result['price_min_rub'], result['price_max_rub'], result['price_rub']) == (kind, low, high, exact)


def test_different_services_do_not_become_one_cheap_price():
    html = '''<h1>Имя</h1><div id=main class=vkladki_body>12 лет на сайте</div>
    <div id=consultation><div class=master-cons-but>
    <div class=info0><div class=h>Личный приём</div></div>
    <div class=cons_itm><b>Консультация</b><div>6000 рублей за 60 минут</div></div>
    <div class=cons_itm><b>Короткая встреча</b><div>3000 рублей за 30 минут</div></div>
    </div></div>'''
    data = parse_profile(html, URL)
    assert data['experience_years'] is None
    assert data['price_rub'] is None
    assert data['price_min_rub'] == 3000
    assert data['duration_minutes'] is None
    assert [s['duration_minutes'] for s in data['services']] == [60, 30]


def test_contact_redaction_does_not_remove_prices_or_education_dates():
    value = redact_contacts('Телефон +1‑202‑555‑0142, mail@example.invalid; https://t.me/example @my_telegram. Цена 4 000 рублей, годы 2001 - 2006.')
    assert '555' not in value and 'example.invalid' not in value and 't.me' not in value and '@my_' not in value
    assert '4 000 рублей' in value and '2001 - 2006' in value
    data = parse_profile('<h1>Имя</h1><div id=main class=vkladki_body>Описание</div>', URL,
                         {'description': 'Пишите mail@example.invalid'})
    assert 'mail@example.invalid' not in str(data)


def test_text_extraction_keeps_blocks_without_executing_scripts():
    html = BeautifulSoup('<div><p>Первый <b>абзац</b>.</p><p style="display:none">Второй.</p><script>secret()</script></div>', 'html.parser')
    result = clean_text(html.div)
    assert 'Первый абзац.' in result
    assert '\nВторой.' in result
    assert 'secret' not in result


def test_non_profile_page_fails_closed():
    with pytest.raises(ValueError, match='Expected a B17 profile'):
        parse_profile('<h1>Войти</h1><p>Authentication required</p>', URL)


def test_private_forum_is_paid_online_not_a_public_demo():
    html = """<h1>Имя</h1><div id=main class=vkladki_body>Описание</div>
    <div id=consultation><div class=master-cons-but>
    <div class=info0><div class=h>Онлайн-консультация</div></div>
    <div class=cons_itm2><b>Приватная консультация на форуме</b>3500 рублей</div>
    </div></div>"""
    data = parse_profile(html, URL)
    assert data['services'][0]['format'] == 'online'
    assert data['services'][0]['price_rub'] == 3500
    assert data['price_rub'] == 3500


@pytest.mark.parametrize('slug,expected_id,education_count,service_count,expected_prices', [
    ('profile_02', '900000002', 24, 8, [4000, 8000, 3500, 4000, 6500, 4000, 0, None]),
    ('profile_03', '900000003', 23, 8, [5000, 5500, 4000, 4000, 4000, 7000, 7000, 0]),
    ('profile_04', '900000004', 18, 5, [4000, 4000, 3500, 6000, 0]),
])
def test_additional_synthetic_profiles(slug, expected_id, education_count, service_count, expected_prices):
    html = (FIXTURE.parent / f'{slug}.html').read_text()
    data = parse_profile(html, f'https://www.b17.ru/fixture_{slug}/')
    assert data['id'] == expected_id
    assert data['cities'] == ['Санкт-Петербург']
    assert len(data['education_entries']) == education_count
    assert len(data['services']) == service_count
    assert [service['price_rub'] for service in data['services']] == expected_prices
    assert data['price_rub'] is None
    assert data['duration_minutes'] is None
    assert data['online'] is True and data['offline'] is True
    assert 'Образование' not in data['about'] or len(data['about']) > 1000
    assert data['raw_profile_text_chars'] == len(data['raw_profile_text'])
    assert BeautifulSoup(html, 'html.parser').select_one('#otzyv') is None
    assert 'mailto:' not in html


def test_srochnaya_does_not_mean_offline_and_forum_does_not_mean_free():
    data = parse_profile((FIXTURE.parent / 'profile_03.html').read_text(), URL)
    emergency = next(service for service in data['services'] if 'Срочная' in service['label'])
    assert emergency['format'] == 'online'
    assert emergency['price_rub'] == 7000
    private_forum = next(service for service in data['services'] if 'Приватная' in service['label'])
    assert private_forum['format'] == 'online'
    assert private_forum['price_rub'] == 4000
    assert private_forum['duration_minutes'] is None


def test_unknown_currency_does_not_become_a_ruble_price():
    data = parse_profile((FIXTURE.parent / 'profile_02.html').read_text(), URL)
    supervision = data['services'][-1]
    assert supervision['format'] is None
    assert supervision['price_rub'] is None
    assert supervision['currency'] is None
    assert '4000 / 60 минут' in supervision['source_text']
    assert supervision['duration_minutes'] == 60


def test_body_evidence_preserves_conflicting_experience_without_guessing():
    data = parse_profile((FIXTURE.parent / 'profile_04.html').read_text(), URL)
    assert data['experience_years'] is None
    assert {claim['years'] for claim in data['experience_claims']} == {18, 19}
    assert any('conflicting experience' in warning for warning in data['warnings'])
    assert '19 лет' in data['about']
    assert data['supervision'] and data['personal_therapy']


def test_card_fallback_is_only_used_when_profile_values_are_missing():
    html = '<div id=main class=vkladki_body>Описание</div>'
    card = {'name': 'Имя из карточки', 'city': 'Санкт-Петербург', 'id': '123'}
    data = parse_profile(html, URL, card)
    assert data['name'] == card['name']
    assert data['city'] == card['city']
    assert data['id'] == card['id']
    data = parse_profile(FIXTURE.read_text(), URL, card)
    assert data['name'] == 'Тестовый специалист 01'
    assert data['cities'] == ['Москва', 'Санкт-Петербург', 'Петергоф']


def test_source_identity_is_not_redacted_as_a_phone_number():
    source_url = 'https://www.b17.ru/12345678901/'
    html = '<h1>Имя</h1><div id=main class=vkladki_body>Телефон +1 202 555 0142</div>'
    data = parse_profile(html, source_url, {'id': '12345678901', 'url': source_url})
    assert data['url'] == source_url
    assert data['id'] == '12345678901'
    assert data['catalog_card']['url'] == source_url
    assert '555' not in data['about']


def test_open_price_range_does_not_create_a_finite_overall_maximum():
    html = """<h1>Имя</h1><div id=main class=vkladki_body>Описание</div>
    <div id=consultation><div class=master-cons-but>
    <div class=info0><div class=h>Онлайн-консультация</div></div>
    <div class=cons_itm2><b>Видео-консультация</b>от 5000 рублей за 60 минут</div>
    <div class=cons_itm2><b>Приватная консультация на форуме</b>4000 рублей</div>
    </div></div>"""
    data = parse_profile(html, URL)
    assert data['price_rub'] is None
    assert data['price_min_rub'] == 4000
    assert data['price_max_rub'] is None


def test_logged_in_avatar_cannot_become_specialist_id():
    html = '<nav><img src="/foto/users/user_999_100.jpg"></nav><h1>Specialist</h1><div id=main class=vkladki_body><div class=photo_box><img src="/foto/users/user_123_100.jpg"></div>About</div>'
    assert parse_profile(html, 'https://www.b17.ru/specialist/')['id'] == '123'


def test_demo_inactivity_timeout_and_paid_followup_are_not_service_terms():
    html = '''<h1>Специалист</h1><div id=main class=vkladki_body>Описание</div>
    <div id=consultation><div class=master-cons-but>
      <div class=info0><div class=h>Демо-консультация на форуме</div>
      <div class=cons_rub>Бесплатная публичная консультация</div></div>
      <div class=info1><b>Условия проведения демо-консультации:</b>
      Консультация закрывается, если нет ответов более 24 часов без предупреждения.
      После демо можно записаться на платную консультацию: 4000 рублей за 60 минут.
      </div></div></div>'''
    record = parse_profile(html, 'https://www.b17.ru/specialist/')
    service = record['services'][0]
    assert service['format'] == 'public_demo'
    assert service['price_kind'] == 'free' and service['price_rub'] == 0
    assert service['duration_minutes'] is None
    assert service['duration_min_minutes'] is None and service['duration_max_minutes'] is None
    assert '24 часов' in service['source_text'] and '4000 рублей' in service['source_text']
    assert '24 часов' in record['raw_profile_text']
