"""Export observed catalog controls without assuming that every UI value works."""
from __future__ import annotations

import re
from collections import OrderedDict
from urllib.parse import parse_qsl, urljoin, urlsplit

from bs4 import BeautifulSoup, Tag

from .catalog import normalize_url


_UNSET = {'', '0', '-'}
_ROOTS = ('master_filter_right', 'master_filter_step', 'master_filter_quick')
_FIELD_LABELS = {'price1': 'Стоимость: от', 'price2': 'Стоимость: до',
                 'byfoto': 'Вид списка', 'sort': 'Порядок'}
_SCOPE_NOTES = [
    'Controls and values are observed on the source page, not an exhaustive list for every city or session.',
    'Sidebar options are separate from additional wizard-only values; the latter require live verification.',
    'Combining multiple topics or methods is supported by the UI, but AND/OR semantics are not established.',
    'A selected HTML control confirms a received selection, not matching quality or completeness of the result set.',
]


def _text(node: Tag | None) -> str:
    return re.sub(r'\s+', ' ', node.get_text(' ', strip=True)).strip() if node else ''


def _control_label(control: Tag, root: Tag) -> str:
    identifier = control.get('id')
    if identifier:
        label = root.find('label', attrs={'for': identifier})
        if label:
            return _text(label)
    for ancestor in control.parents:
        if ancestor is root:
            break
        if set(ancestor.get('class', [])) & {'radio', 'checkbox', 'css-radio', 'css-checkbox'}:
            return _text(ancestor)
    return str(control.get('value', ''))


def _group_label(control: Tag, key: str) -> str:
    if key in _FIELD_LABELS:
        return _FIELD_LABELS[key]
    group = control.find_parent('div', class_='f')
    heading = group.select_one('.fh') if group else None
    if heading:
        return _text(heading)
    group = control.find_parent('div', class_='step')
    heading = group.select_one('.h') if group else None
    return _text(heading) or key


def _control_options(control: Tag, root: Tag) -> list[dict]:
    if control.name == 'select':
        options = control.select('option')
        explicit = any(option.has_attr('selected') for option in options)
        return [{'value': str(option.get('value', option.get_text(' ', strip=True))),
                 'label': _text(option),
                 'selected': option.has_attr('selected') or (
                     not explicit and index == 0 and not control.has_attr('multiple'))}
                for index, option in enumerate(options)]
    return [{'value': str(control.get('value', '')),
             'label': _control_label(control, root),
             'selected': control.has_attr('checked')}]


def _routes(soup: BeautifulSoup, url: str) -> list[dict]:
    result, seen = [], set()
    for anchor in soup.select('.vkladki5_filter a[href]'):
        raw = anchor['href']
        path = urlsplit(urljoin(url, raw)).path
        if not path.startswith(('/psiholog/', '/online/')):
            continue
        try:
            route_url = normalize_url(raw, base=url)
        except ValueError:
            continue
        # Favorites are session-specific query controls, not format routes.
        if urlsplit(route_url).query or route_url in seen:
            continue
        seen.add(route_url)
        result.append({'label': _text(anchor), 'url': route_url,
                       'format': 'online' if path.startswith('/online/') else 'in_person',
                       'query_parameter': None, 'evidence': 'catalog_navigation_link'})
    return result


def _cities(html: str | None, base: str) -> list[dict]:
    if html is None:
        return []
    soup = BeautifulSoup(html, 'html.parser')
    seen, result = set(), []
    for anchor in soup.select('.masters_city_list a[href]'):
        path = urlsplit(urljoin(base, anchor['href'])).path
        if not re.fullmatch(r'/psiholog/[^/]+/', path):
            continue
        try:
            url = normalize_url(anchor['href'], base=base)
        except ValueError:
            continue
        if urlsplit(url).query or url in seen or not _text(anchor):
            continue
        seen.add(url)
        result.append({'label': _text(anchor), 'url': url,
                       'slug': path.strip('/').split('/')[-1],
                       'evidence': 'city_catalog_link'})
    return result


def _catalog_search(soup: BeautifulSoup, url: str) -> Tag | None:
    """Find only a same-catalog GET search input, never a remote/private form."""
    expected_path = urlsplit(url).path
    for control in soup.select('form input[name="tag"]'):
        form = control.find_parent('form')
        if form is None or str(form.get('method', 'get')).lower() != 'get':
            continue
        try:
            action = normalize_url(str(form.get('action', '')) or url, base=url)
        except ValueError:
            continue
        if urlsplit(action).path == expected_path:
            return control
    return None


def extract_filter_catalog(html: str, url: str, provenance: dict | None = None,
                           city_html: str | None = None) -> dict:
    """Return LLM-readable filter metadata from a decoded catalog snapshot.

    This pure function makes no requests and does not require parseable cards or
    a matching query. The right panel is authoritative for crawler-verifiable
    values and selected state. Other UI variants contribute labels, provenance,
    and explicitly separate additional values rather than quietly broadening the
    verified option set. City links may be supplied from a separate city-index
    snapshot. Personal navigation, credentials, event handlers, and raw HTML are
    never exported. Missing expected filter markup raises ValueError.
    """
    url = normalize_url(url)
    soup = BeautifulSoup(html, 'html.parser')
    sidebar = soup.select_one('#master_filter_right')
    if sidebar is None:
        raise ValueError('No supported B17 filter panel found in the source HTML')
    merged: dict[str, dict] = OrderedDict()
    internal = []
    for rid in _ROOTS:
        root = soup.select_one('#' + rid)
        if root is None:
            continue
        grouped: dict[str, list[Tag]] = OrderedDict()
        for control in root.select('input[name], select[name]'):
            name = str(control.get('name', ''))
            if name in {'f_mod', 'f_city'}:
                if rid == 'master_filter_right':
                    internal.append({'name': name, 'value': str(control.get('value', '')),
                                     'query_parameter': None, 'role': 'internal_context'})
                continue
            if name.startswith('f_'):
                grouped.setdefault(name[2:], []).append(control)
        for key, controls in grouped.items():
            field = merged.setdefault(key, {'parameter': key, 'label': _group_label(controls[0], key),
                'role': 'display' if key == 'byfoto' else 'sort' if key == 'sort' else 'filter',
                'source_control_names': [], 'observed_in': [], 'options': [],
                'ui_additional_values': [], 'selected_values': [], 'selected_control_values': [],
                'default_values': [], 'query_mapping_evidence': 'f_ prefix convention; each requested value must be verified in returned HTML',
                'crawl_compatible': True, 'value_type': 'enum', 'notes': []})
            if rid not in field['observed_in']:
                field['observed_in'].append(rid)
            for control in controls:
                if control['name'] not in field['source_control_names']:
                    field['source_control_names'].append(control['name'])
            # Multiple checkbox choices and <select multiple> support a list.
            kind = str(controls[0].get('type', 'select' if controls[0].name == 'select' else 'text'))
            if rid == 'master_filter_right' or 'kind' not in field:
                field['control_kind'] = kind
                field['multiple'] = any(control.has_attr('multiple') for control in controls) or (kind == 'checkbox' and len(controls) > 1)
                field['kind'] = 'multi_enum' if field['multiple'] else 'boolean' if kind == 'checkbox' else 'enum'
                if field['multiple']:
                    field['multi_value_encoding'] = {'query_separator': ',',
                        'evidence': 'site JavaScript reads comma-delimited selections; form submission joins repeated values with spaces',
                        'boolean_combination': 'unknown'}
            for control in controls:
                for item in _control_options(control, root):
                    value = item['value']
                    if value in _UNSET and value not in field['default_values']:
                        field['default_values'].append(value)
                    options = field['options'] if rid == 'master_filter_right' else field['options'] + field['ui_additional_values']
                    option = next((o for o in options if o['value'] == value), None)
                    if option is None:
                        option = {'value': value, 'label': item['label'], 'observed_in': [], 'labels_by_control': {},
                                  'is_default': value in _UNSET, 'selected_in': []}
                        target = field['options'] if rid == 'master_filter_right' else field['ui_additional_values']
                        target.append(option)
                    if rid not in option['observed_in']:
                        option['observed_in'].append(rid)
                    option['labels_by_control'][rid] = item['label']
                    if item['selected']:
                        option['selected_in'].append(rid)
                        if rid == 'master_filter_right':
                            field['selected_control_values'].append(value)
                            if value not in _UNSET:
                                field['selected_values'].append(value)
            if kind == 'checkbox' and len(controls) == 1 and rid == 'master_filter_right':
                # 'More...' is a visual section, not a useful label for each flag.
                field['label'] = _control_label(controls[0], root)
    for key, field in merged.items():
        field['max_values'] = None if field['multiple'] else 1
        field['crawl_compatible'] = 'master_filter_right' in field['observed_in']
        if key == 'byfoto':
            field['unsupported_crawl_values'] = ['1']
            for option in field['options']:
                option['crawl_compatible'] = option['value'] != '1'
            field['notes'].append('Photo-only view is exposed by B17 but is not supported by the profile-card crawler; use byfoto=0 or omit it.')
        if key in {'price1', 'price2'}:
            field['unit'] = 'RUB'
            field['bound'] = 'minimum' if key == 'price1' else 'maximum'
            field['notes'].append('The site exposes discrete thresholds; do not invent unsupported amounts or silently round a user budget.')
        if field['ui_additional_values']:
            field['notes'].append('Additional UI values are not sidebar-verifiable in this snapshot and must not be treated as verified crawler options.')
        field['verified_selected_values'] = [value for value in field['selected_values'] if value in
            {part for qkey, raw in parse_qsl(urlsplit(url).query) if qkey == key for part in re.split(r'[,\s]+', raw) if part}]
    # This separate GET form is an actual public catalog control, not a f_* field.
    search = _catalog_search(soup, url)
    if search is not None:
        form = search.find_parent('form')
        minimum = search.get('minlength')
        merged['tag'] = {'parameter': 'tag', 'label': str(search.get('placeholder', 'Найти специалиста')),
            'role': 'filter', 'kind': 'text', 'value_type': 'text', 'multiple': False,
            'source_control_names': ['tag'], 'observed_in': ['catalog_search_form'],
            'options': [], 'ui_additional_values': [], 'default_values': [''],
            'selected_values': [str(search.get('value'))] if search.get('value') else [],
            'selected_control_values': [str(search.get('value', ''))],
            'minimum_length': int(minimum) if minimum and str(minimum).isdigit() else None,
            'min_length': int(minimum) if minimum and str(minimum).isdigit() else None, 'max_values': 1,
            'query_mapping_evidence': 'GET form input name=tag; dedicated response verifier is implemented, live behavior remains unverified', 'crawl_compatible': True,
            'form_method': str(form.get('method', 'get')).lower() if form else None,
            'notes': ['Text search must be compared with the returned search-input value; its live behavior has not been verified. It is not a replacement for semantic analysis of full profiles.']}
    routes = _routes(soup, url)
    city_value = sidebar.select_one('[name="f_city"]')
    city_label = soup.select_one("#maket_body_right_content [onclick*='city_ppp_search_show'], #maket_body_right_content > .menu-blue-box3 > span.like_a")
    scope = {'source_path': urlsplit(url).path,
             'city_id': str(city_value.get('value')) if city_value else None,
             'city': re.sub(r'^г\.\s*', '', _text(city_label)) or None,
             'consultation_catalog': 'online' if urlsplit(url).path.startswith('/online/') else 'in_person',
             'notes': list(_SCOPE_NOTES)}
    controls = []
    for control in soup.select('#master_filter_step [name="frmt"]'):
        root = soup.select_one('#master_filter_step')
        controls.append({'control_name': 'frmt', 'label': _control_label(control, root),
                         'query_parameter': None, 'role': 'catalog_route_switch',
                         'notes': ['This UI switch changes the catalog route; do not send frmt as a query parameter.']})
    unsupported = []
    if soup.select_one('a[href*="fav=1"]'):
        unsupported.append({'parameter': 'fav', 'role': 'session_filter', 'requires_login': True,
                            'crawl_compatible': False, 'evidence': 'favorites_navigation_link'})
    return {'schema_version': 1, 'source': {'url': url, 'provenance': provenance or {}},
            'scope': scope, 'routes': routes, 'filters': merged,
            'route_controls': controls, 'internal_controls': internal,
            'unsupported_controls': unsupported, 'cities': _cities(city_html, url),
            'selection_check': {'requested_query': dict(parse_qsl(urlsplit(url).query)),
                                'note': 'Metadata extraction does not validate requested selections; inspect/crawl performs strict response verification.'}}


def _md(value: object) -> str:
    return str(value if value is not None else '').replace('|', '\\|').replace('\n', ' ')


_GUIDE_NOTES_RU = {
    'Photo-only view is exposed by B17 but is not supported by the profile-card crawler; use byfoto=0 or omit it.':
        'Для сбора используйте `byfoto=0` (подробный вид) или не задавайте параметр.',
    'The site exposes discrete thresholds; do not invent unsupported amounts or silently round a user budget.':
        '',
    'Additional UI values are not sidebar-verifiable in this snapshot and must not be treated as verified crawler options.':
        '',
    'Text search must be compared with the returned search-input value; its live behavior has not been verified. It is not a replacement for semantic analysis of full profiles.':
        '',
}
_GUIDE_UI_RU = {
    'master_filter_right': 'боковая панель',
    'master_filter_step': 'пошаговый подбор',
    'master_filter_quick': 'быстрая форма',
    'catalog_search_form': 'поиск по каталогу',
}
_GUIDE_ROLES_RU = {
    'filter': 'фильтр', 'display': 'отображение', 'sort': 'сортировка',
    'session_filter': 'фильтр личной сессии',
}
_GUIDE_KINDS_RU = {
    'enum': 'один вариант', 'multi_enum': 'несколько вариантов',
    'boolean': 'флажок', 'text': 'текст',
}
_GUIDE_FORMATS_RU = {'online': 'онлайн', 'in_person': 'очно'}



def render_filter_guide(reference: dict) -> str:
    """Render a concise Russian guide with complete option and route tables.

    Shared constraints appear once in the instructions or beside their tables.
    Original labels, values and technical names remain unchanged. No field is
    shortened, and the machine-readable reference is not modified.
    """
    fields = reference.get('filters', {})
    lines = ['# Фильтры B17', '']
    lines += ['## Для LLM', '',
              '- Начните с обязательных ограничений пользователя. Если подходящей темы нет в списке, соберите более широкую выборку и изучите полные анкеты.',
              '- Передавайте значения из таблиц, а не отображаемые подписи. Пустые значения и значения по умолчанию можно не задавать.',
              '- Не округляйте бюджет и не добавляйте отсутствующие пороги цены. Дополнительные варианты пошагового подбора перечислены отдельно.',
              '- Город и формат задаются адресом каталога. Идентификаторы локаций действуют только в исходном городе; при его смене получите новый справочник.',
              '- Несколько значений перечисляйте через запятую; логика «И»/«ИЛИ» не установлена.',
              '- Составьте URL через `build-url`, затем проверьте выбранные значения командой `inspect` в той же сессии. Построение URL не выполняет сетевых запросов.', '',
              '## Формат консультации', '',
              '| Подпись | Адрес | Формат |', '| --- | --- | --- |']
    for route in reference.get('routes', []):
        format_value = route.get('format')
        lines.append(f"| {_md(route.get('label'))} | {_md(route.get('url'))} | {_md(_GUIDE_FORMATS_RU.get(format_value, format_value))} |")
    lines += ['', 'Для смены формата меняйте адрес каталога. `frmt`, `f_city` и `f_mod` не передаются в URL.', '',
              '## Параметры и варианты', '']
    for key, field in fields.items():
        role, kind = field.get('role'), field.get('kind')
        defaults = ', '.join('`' + (str(value) if str(value) else '(пусто)') + '`'
                             for value in field.get('default_values', [])) or 'параметр не задан'
        description = _md(_GUIDE_KINDS_RU.get(kind, kind))
        if role and role != 'filter':
            description += '; ' + _md(_GUIDE_ROLES_RU.get(role, role))
        lines += [f"### `{key}` — {_md(field.get('label'))}", '',
                  f"{description.capitalize()}. По умолчанию: {defaults}.", '']
        selected = field.get('selected_values', [])
        if selected:
            lines += ["В снимке выбрано: " + ', '.join('`' + str(value) + '`' for value in selected) + '.', '']
        if kind == 'text':
            minimum = field.get('minimum_length')
            if minimum is not None:
                lines += [f"Минимальная длина: {_md(minimum)}. Кодируйте текст для URL один раз.", '']
        if field.get('options'):
            lines += ['| Значение | Исходная подпись | Примечание |', '| --- | --- | --- |']
            for option in field['options']:
                notes = []
                if option.get('is_default'):
                    notes.append('по умолчанию')
                if option.get('value') in field.get('unsupported_crawl_values', []):
                    notes.append('CLI не поддерживает')
                lines.append(f"| `{_md(option.get('value'))}` | {_md(option.get('label'))} | {'; '.join(notes)} |")
            lines.append('')
        extras = field.get('ui_additional_values', [])
        if extras:
            lines += ['Дополнительные варианты вне боковой панели (CLI пока не принимает):', '',
                      '| Значение | Исходная подпись | Где найдено |', '| --- | --- | --- |']
            for option in extras:
                observed = ', '.join(_GUIDE_UI_RU.get(value, value) for value in option.get('observed_in', []))
                lines.append(f"| `{_md(option.get('value'))}` | {_md(option.get('label'))} | {_md(observed)} |")
            lines.append('')
        for note in field.get('notes', []):
            translated = _GUIDE_NOTES_RU.get(str(note), str(note))
            if translated:
                lines += [translated, '']
    if reference.get('unsupported_controls'):
        lines += ['## Другие неподдерживаемые контролы', '']
        for field in reference['unsupported_controls']:
            role = field.get('role')
            lines += [f"- `{_md(field.get('parameter'))}`: {_md(_GUIDE_ROLES_RU.get(role, role))}; CLI не поддерживает."]
        lines.append('')
    cities = reference.get('cities', [])
    lines += ['## Города', '', f"Адреса из снимка индекса: {len(cities)}.", '']
    if cities:
        lines += ['| Город | Адрес |', '| --- | --- |']
        for city in cities:
            lines.append(f"| {_md(city.get('label'))} | {_md(city.get('url'))} |")
        lines.append('')
    return '\n'.join(lines)
