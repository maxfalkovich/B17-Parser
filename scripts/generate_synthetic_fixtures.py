"""Generate fictional parser fixtures without downloading or copying biographies.

Run from any directory. The four profile fixtures and catalog cards are generated
from explicit test values. Filter controls are reused from the separate public
UI taxonomy fixture. No real person's name, profile, contact, or document is used.
"""
from __future__ import annotations

import copy
from html import escape
from pathlib import Path

from bs4 import BeautifulSoup


FIXTURES = Path(__file__).resolve().parents[1] / 'tests' / 'fixtures'
NOTICE = '<!-- Synthetic parser fixture: all specialists and education records are fictional. -->'


def _service(label: str, amount: int | None, duration: int | None) -> str:
    price = f'{amount} рублей' if amount is not None else ''
    period = f' за {duration} минут' if duration is not None else ''
    return f'<div class="cons_itm"><b>{escape(label)}</b><div>Стоимость: {price}{period}</div></div>'


def _group(label: str, services: list[tuple[str, int | None, int | None]]) -> str:
    return '<div class="master-cons-but"><div class="info0"><div class="h">' + escape(label) + \
           '</div></div><div class="info1">' + ''.join(_service(*service) for service in services) + '</div></div>'


def _demo() -> str:
    return '''<div class="master-cons-but"><div class="info0"><div class="h">Демо-консультация на форуме</div>
    <div class="cons_rub">Бесплатная публичная консультация</div></div>
    <div class="info1"><b>Условия тестовой демо-консультации:</b>
    Переписка закрывается при отсутствии ответа более 24 часов. Это условие ожидания, а не длительность услуги.
    </div></div>'''


def _education(number: int, count: int) -> str:
    entries = []
    for index in range(1, count + 1):
        title = 'Тестовое основное образование' if index == 1 else f'Синтетическая учебная программа {index:02}'
        dates = 'Годы обучения: 2005 - 2010' if index == 1 else f'Год получения: {2010 + index % 10}'
        entries.append(f'''<div><b>{title}</b><p>Организация: Тестовый учебный центр {number:02}</p>
        <p>{dates}</p><p>Продолжительность: 120 часов</p>
        <a href="/foto/vuz/synthetic_certificate_{number:02}_{index:02}.png">Тестовый документ {index:02}</a></div>''')
    return '<div id="vuz" class="vkladki_body"><h2>Образование и работа</h2>' + \
           '<div id="vuz_list_s">Краткий список. Показать больше</div>' + \
           '<div id="vuz_list_f" style="display:none">' + ''.join(entries) + '</div></div>'


def _profile(number: int) -> str:
    name = f'Тестовый специалист {number:02}'
    identifier = str(900000000 + number)
    cities = [('moskva', 'Москва'), ('sankt-peterburg', 'Санкт-Петербург'), ('petergof', 'Петергоф')] if number == 1 else [('sankt-peterburg', 'Санкт-Петербург')]
    city_links = ', '.join(f'<a href="/psiholog/{slug}/">г. {city}</a>' for slug, city in cities)
    experience = '<p>Опыт работы 22 года.</p>' if number == 1 else '<p>Опыт работы 7 лет.</p>'
    if number == 4:
        experience = '<p>Опыт работы 18 лет.</p><p>Уже 19 л<b>ет</b> работаю в тестовом проекте.</p>'
    paragraphs = ''.join(f'<p>Синтетический абзац {index:03}: описание учебного примера полностью придумано для проверки сохранения длинного текста анкеты без усечения.</p>' for index in range(1, 61))
    about = f'''<p>НАЧАЛО_ТЕСТОВОЙ_АНКЕТЫ_{number:02}</p>{experience}
    <p>Консультирую взрослых и пары. Помогаю с тестовыми запросами и проблемами самоорганизации.</p>
    <p>Специализируюсь на учебных примерах. Целевая аудитория указана исключительно для проверки извлечения.</p>
    <p>Не работаю с тестовыми противопоказаниями. Регулярная супервизия и личная терапия.</p>
    {paragraphs}<div style="display:none">КОНЕЦ_ТЕСТОВОЙ_АНКЕТЫ_{number:02}</div>'''
    if number == 1:
        about += '<p>Синтетические контакты: +1‑202‑555‑0142, demo@example.invalid, https://t.me/synthetic_fixture_contact.</p>'
    approaches = '<div class="napr_list"><b>Работаю в направлениях:</b><span>Тестовый подход А</span>, <span>Тестовый подход Б</span></div>'
    if number == 1:
        services = _group('Личный приём', [('Очная консультация', 4000, 50), ('Онлайн', 4000, 50)]) + \
                   _group('Онлайн-консультация', [('Видео-консультация', 4000, 50)]) + _demo()
    elif number == 2:
        services = _group('Личный приём', [('Очная консультация', 4000, 60), ('Семейная консультация для пары', 8000, 90),
                   ('Консультация для подростка', 3500, 60), ('Супервизия', 4000, 75),
                   ('Семейная консультация: взрослый и ребёнок', 6500, 90)]) + \
                   _group('Онлайн-консультация', [('Видео-консультация', 4000, 60)]) + _demo() + \
                   '<div class="master-cons-but"><div class="info0"><div class="h">Супервизия</div></div><div class="info1"><b>Супервизия</b><p>4000 / 60 минут</p></div></div>'
    elif number == 3:
        services = _group('Личный приём', [('Очная консультация', 5000, 60), ('Семейная консультация', 5500, 75)]) + \
                   _group('Онлайн-консультация', [('Видео-консультация', 4000, 60), ('Аудио-консультация', 4000, 60),
                   ('Приватная консультация на форуме', 4000, None), ('Семейная онлайн-консультация', 7000, 90),
                   ('Срочная экстренная консультационная помощь', 7000, 60)]) + _demo()
    else:
        services = _group('Личный приём', [('Очная консультация', 4000, 55)]) + \
                   _group('Онлайн-консультация', [('Видео-консультация', 4000, 60), ('Приватная консультация на форуме', 3500, None),
                   ('Семейная консультация', 6000, 90)]) + _demo()
    extra = ''
    if number == 1:
        extra = '<div id="otzyv" class="vkladki_body">НЕ_ВКЛЮЧАТЬ_ОТЗЫВ_В_АНКЕТУ</div><div id="article" class="vkladki_body">НЕ_ВКЛЮЧАТЬ_СТАТЬЮ_В_АНКЕТУ</div>'
    return f'''<!DOCTYPE html><html><head><meta charset="utf-8"><title>{name}</title><script>var uid_id = 0;</script></head><body>
    {NOTICE}<h1>{name}</h1><div class="status-grey">Психолог — {city_links}</div>
    <div id="main" class="vkladki_body vkladki_body_first"><div class="photo_box"><img src="/foto/users/user_{identifier}_200.jpg"></div>
    {about}{approaches}</div>{_education(number, [25,24,23,18][number-1])}
    <div id="consultation" class="vkladki_body">{services}</div>
    <a id="vkl_otzyv" href="#otzyv">Отзывы<span class="n">344</span></a>{extra}</body></html>'''


def _catalog() -> str:
    source = BeautifulSoup((FIXTURES / 'filter_controls.html').read_text(encoding='utf-8'), 'html.parser')
    soup = BeautifulSoup('<!DOCTYPE html><html><head><meta charset="utf-8"><title>Синтетический каталог</title></head><body></body></html>', 'html.parser')
    soup.body.append(BeautifulSoup(NOTICE, 'html.parser'))
    for selector in ['h1', '#master_filter_right', '#maket_body_right_content']:
        node = source.select_one(selector)
        if node is None:
            raise ValueError(f'Missing safe taxonomy fixture component: {selector}')
        soup.body.append(copy.deepcopy(node))
    cards = []
    for number in range(1, 11):
        identifier = str(900000000 + number)
        cards.append(f'''<div class="item"><div class="yak" id="spec_{identifier}"></div><div class="text">
        <a class="h" name="spec{identifier}" href="/fixture_profile_{number:02}/">Тестовый специалист {number:02}</a>
        <div class="s">Психолог — 10 лет на сайте</div><div class="t">Придуманное краткое описание тестового специалиста {number:02}.</div>
        <div class="price price1"><div><b>Очная консультация:</b> 4<span>000</span> рублей за 50 минут</div></div>
        <div class="price price2">Обращения в синтетическом примере: {number}</div>
        <a href="/fixture_profile_{number:02}/#otzyv">344 отзыва</a></div></div>''')
    listing = '<div id="items_list" class="items_list"><div class="list_blue_info list_blue_info_filter"><span title="Применены фильтры: индивидуально, от 3000 руб, до 5000 руб">Найдены 300 специалистов</span></div>' + ''.join(cards) + '</div>'
    pager = '<div id="items_page"><input id="backend_page" name="backend_page" type="hidden" value="2"><input id="backend_page_plus" name="backend_page_plus" type="hidden" value="2"><div id="ajax_page_next">Показать ещё 10 специалистов. Показаны 10 специалистов из 300</div></div>'
    soup.body.append(BeautifulSoup(listing + pager, 'html.parser'))
    return str(soup)


def main() -> None:
    for number in range(1, 5):
        (FIXTURES / f'profile_{number:02}.html').write_text(_profile(number), encoding='utf-8')
    (FIXTURES / 'filtered.html').write_text(_catalog(), encoding='utf-8')
    print('Generated four fictional profiles and one fictional catalog; no network access')


if __name__ == '__main__':
    main()
