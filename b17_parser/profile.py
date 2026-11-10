"""Extract public professional profile content without fetching contact endpoints."""

from __future__ import annotations

import copy
import re
from datetime import datetime, timezone
from urllib.parse import urljoin

from bs4 import BeautifulSoup, Tag


_BLOCKS = ('p', 'div', 'li', 'tr', 'h1', 'h2', 'h3', 'h4', 'section', 'blockquote')
_EMAIL = re.compile(r"[\w.!#$%&'*+/=?^`{|}~-]+@[\w-]+(?:\.[\w-]+)+", re.I)
_PHONE = re.compile(r"(?<!\w)(?:\+?\d[\d\s().\-‐‑‒–—]{7,}\d)(?!\w)")
_MESSENGER = re.compile(
    r"(?:https?://)?(?:www\.)?(?:t\.me|telegram\.me|wa\.me|api\.whatsapp\.com|"
    r"whatsapp\.com|viber\.com|signal\.me|skype\.com|m\.me|max\.ru)/[^\s<>\"']+|"
    r"(?:tg|viber|skype|whatsapp)://[^\s<>\"']+|(?<![\w.])@[A-Za-z][A-Za-z0-9_]{3,}", re.I
)


def redact_contacts(text: str) -> str:
    """Redact recognizable contact details embedded in public prose.

    This is intentionally best effort: obfuscated human-readable contacts cannot
    be identified reliably without changing the meaning of the profile prose.
    """
    text = _EMAIL.sub('[contact redacted]', text)
    text = _MESSENGER.sub('[contact redacted]', text)

    def phone(match: re.Match) -> str:
        value = match.group()
        digits = re.sub(r'\D', '', value)
        if 10 <= len(digits) <= 15 and (value.startswith('+') or len(digits) in (10, 11)):
            return '[contact redacted]'
        return value

    return _PHONE.sub(phone, text)


def clean_text(node: Tag | None) -> str:
    """Return all textual content, including collapsed sections, with block breaks.

    Scripts, style sheets and form controls are excluded. Hidden text is retained
    because B17 places full education and service details in collapsed panels.
    No length limit is applied. Recognizable contact details are redacted.
    """
    if node is None:
        return ''
    node = copy.deepcopy(node)
    for el in node.select('script, style, noscript, input, button, select, textarea'):
        el.decompose()
    for br in node.find_all('br'):
        br.replace_with('\n')
    for el in node.find_all(_BLOCKS):
        el.insert_before('\n')
        el.insert_after('\n')
    text = node.get_text('', strip=False)
    lines = [re.sub(r'[^\S\n]+', ' ', line).strip() for line in text.splitlines()]
    return redact_contacts('\n'.join(line for line in lines if line))


def _number(value: str) -> int:
    return int(re.sub(r'\D', '', value))


def parse_price(text: str) -> dict:
    """Normalize a RUB amount or range while preserving uncertainty and source.

    The absence of a stated RUB price is not interpreted as zero. Public free
    consultation is represented separately from paid therapy services.
    """
    text = re.sub(r'\s+', ' ', text)
    number = r'\d+(?:[ \u00a0\u202f]\d{3})*'
    rub = r'(?:руб(?:лей|ля|ль|\.)?|₽)'
    result = {'price_rub': None, 'price_min_rub': None, 'price_max_rub': None,
              'price_kind': None, 'currency': None}
    match = re.search(rf'(?:от\s+)?({number})\s*(?:до|[-–—])\s*({number})\s*{rub}', text, re.I)
    if match:
        result.update(price_min_rub=_number(match[1]), price_max_rub=_number(match[2]),
                      price_kind='range', currency='RUB')
        return result
    match = re.search(rf'(от|до)?\s*({number})\s*{rub}', text, re.I)
    if match:
        value, bound = _number(match[2]), (match[1] or '').lower()
        result.update(currency='RUB', price_kind={'от': 'from', 'до': 'up_to'}.get(bound, 'exact'))
        if bound != 'до':
            result['price_min_rub'] = value
        if bound != 'от':
            result['price_max_rub'] = value
        if not bound:
            result['price_rub'] = value
    elif re.search(r'бесплатн', text, re.I):
        result.update(price_rub=0, price_min_rub=0, price_max_rub=0,
                      price_kind='free', currency='RUB')
    return result


def _duration(text: str) -> dict:
    result = {'duration_minutes': None, 'duration_min_minutes': None,
              'duration_max_minutes': None}
    match = re.search(r'(\d+(?:[.,]\d+)?)\s*(?:[-–—]|до)\s*(\d+(?:[.,]\d+)?)\s*(минут\w*|час\w*)', text, re.I)
    if match:
        factor = 60 if match[3].lower().startswith('час') else 1
        result['duration_min_minutes'] = float(match[1].replace(',', '.')) * factor
        result['duration_max_minutes'] = float(match[2].replace(',', '.')) * factor
    else:
        match = re.search(r'(?:за|длительность[: ]*)?\s*(\d+(?:[.,]\d+)?)\s*(минут\w*|час\w*)', text, re.I)
        if match:
            value = float(match[1].replace(',', '.')) * (60 if match[2].lower().startswith('час') else 1)
            result.update(duration_minutes=value, duration_min_minutes=value, duration_max_minutes=value)
    return {key: int(value) if isinstance(value, float) and value.is_integer() else value
            for key, value in result.items()}


def _format(label: str, group: str) -> str | None:
    if re.search(r'демо|бесплатн.*(?:форум|публичн)|публичн.*консультац', group + ' ' + label, re.I):
        return 'public_demo'
    if re.search(r'онлайн|он-лайн|видео|мессенджер|чат|аудио|скайп|zoom|форум', label, re.I):
        return 'online'
    if re.search(r'\bочн|личный при[её]м', label, re.I):
        return 'offline'
    if re.search(r'онлайн|видео|мессенджер|чат', group, re.I):
        return 'online'
    if re.search(r'\bочн|личный при[её]м', group, re.I):
        return 'offline'
    return None


def _services(consultation: Tag | None) -> list[dict]:
    if consultation is None:
        return []
    services = []
    for group in consultation.select('.master-cons-but'):
        group_label = clean_text(group.select_one('.info0 .h'))
        items = group.select('.cons_itm, .cons_itm2')
        # Some service groups, notably public demos, have only a group summary.
        for item in items or [group.select_one('.info1') or group]:
            label = clean_text(item.select_one('b')) or group_label
            source = clean_text(item)
            if not items:
                source = group_label + '\n' + clean_text(group.select_one('.cons_rub')) + '\n' + source
            format = _format(label, group_label)
            # Public demo conditions describe reply deadlines, inactivity timeouts,
            # and paid follow-up options. Only the dedicated tariff summary can
            # establish numeric service terms; preserve the full prose as evidence.
            numeric_source = clean_text(group.select_one('.cons_rub')) if format == 'public_demo' else source
            services.append({'label': label, 'group': group_label,
                             'format': format,
                             **parse_price(numeric_source), **_duration(numeric_source),
                             'source_text': source})
    # Keep duplicates with distinct labels or groups; identical rows add no data.
    unique = []
    for service in services:
        if service not in unique:
            unique.append(service)
    return unique


def _education(node: Tag | None, url: str) -> tuple[str, list[dict]]:
    if node is None:
        return '', []
    full = node.select_one('#vuz_list_f')
    selected = full or node
    entries = []
    for entry in selected.find_all('div', recursive=False) if full else []:
        text = clean_text(entry)
        title = clean_text(entry.select_one('b'))
        if text:
            # Image URLs are evidence links only; images are not fetched or OCR'd.
            links = [urljoin(url, a['href']) for a in entry.select('a[href]')
                     if '/foto/vuz/' in a['href']]
            entries.append({'title': title or None, 'text': text, 'document_urls': links})
    return clean_text(selected), entries


def _evidence(text: str, pattern: str) -> list[str]:
    # Return source passages rather than invented classifications or conclusions.
    return [line for line in text.splitlines() if re.search(pattern, line, re.I)]


def _experience(text: str) -> tuple[int | None, str | None, list[dict]]:
    patterns = [
        r'(?:опыт(?:ом|а)?\s+(?:работы|практики)|стаж(?:\s+работы)?)\D{0,25}?(\d{1,2})(?:\s*[-–]?\s*[хти]+)?\s*(?:лет|год|года)',
        r'(?:более|уже|около)\s+(\d{1,2})(?:\s*[-–]?\s*[хти]+)?\s*(?:лет|год|года)\s+(?:я\s+)?(?:практикую|оказываю|помогаю|работаю)',
        r'(\d{1,2})\s*(?:лет|года?|год)\s+(?:практикую|оказываю\s+психологическую\s+помощь)',
    ]
    claims = []
    for pattern in patterns:
        for match in re.finditer(pattern, text, re.I):
            claim = {'years': int(match[1]), 'source_text': match.group()}
            if claim not in claims:
                claims.append(claim)
    years = {claim['years'] for claim in claims}
    if len(years) == 1:
        return next(iter(years)), claims[0]['source_text'], claims
    return None, None, claims


def _redact_tree(value, key=None):
    # Source identity and diploma evidence URLs are not contact prose. Numeric
    # slugs/cache timestamps in these fields must not be mistaken for phones.
    if key in {'id', 'url', 'document_urls'}:
        return value
    if isinstance(value, str):
        return redact_contacts(value)
    if isinstance(value, list):
        return [_redact_tree(item, key) for item in value]
    if isinstance(value, dict):
        return {item_key: _redact_tree(item, item_key) for item_key, item in value.items()}
    return value


def parse_profile(html: str, url: str, card: dict | None = None) -> dict:
    """Parse one public B17 profile, retaining the complete useful source prose.

    No network request is made. The caller supplies decoded HTML and the verified
    final page URL. Missing fields stay null/empty. Prices, approaches and source
    passages describe the specialist's own published claims, not verified quality.
    Raises ValueError if the expected profile layout is absent.
    """
    soup = BeautifulSoup(html, 'html.parser')
    main = soup.select_one('#main.vkladki_body, .vkladki_body_first')
    name = clean_text(soup.select_one('h1')) or redact_contacts((card or {}).get('name') or '')
    if main is None or not name:
        raise ValueError('Expected a B17 profile with h1 and the main profile section')
    status_node = soup.select_one('.status-grey')
    status = clean_text(status_node)
    cities = []
    if status_node:
        for anchor in status_node.select('a[href*="/psiholog/"]'):
            text = clean_text(anchor)
            match = re.search(r'г\.\s*(.+)$', text)
            if match and match[1] not in cities:
                cities.append(match[1])
    if not cities and card:
        card_cities = card.get('cities') or ([card['city']] if card.get('city') else [])
        cities = list(dict.fromkeys(card_cities))
    main_copy = copy.deepcopy(main)
    for node in main_copy.select('.photo_box, .box-clients-n, .no-print'):
        node.decompose()
    about = clean_text(main_copy)
    education, education_entries = _education(soup.select_one('#vuz'), url)
    consultation_node = soup.select_one('#consultation')
    consultation_copy = copy.deepcopy(consultation_node)
    if consultation_copy:
        for node in consultation_copy.select('.submit_yellow2, .vkladki_body_r'):
            node.decompose()
    consultation = clean_text(consultation_copy)
    sections = {'about': about, 'education': education, 'consultation': consultation}
    # B17 sometimes adds professional profile panels; preserve unknown substantive
    # panels while excluding client reviews, publications, contacts and discussions.
    excluded = {'main', 'vuz', 'consultation', 'article', 'otzyv', 'demo', 'contact'}
    for node in soup.select('.vkladki_body[id]'):
        key = node.get('id')
        if key not in excluded:
            value = clean_text(node)
            if value:
                sections[key] = value
    approaches = []
    for node in main.select('.napr_list span'):
        value = clean_text(node)
        if value and value not in approaches:
            approaches.append(value)
    services = _services(consultation_node)
    paid = [s for s in services if s['format'] != 'public_demo' and s['price_kind'] != 'free']
    exact = {s['price_rub'] for s in paid}
    price = next(iter(exact)) if len(exact) == 1 and None not in exact else None
    minimums = [s['price_min_rub'] for s in paid if s['price_min_rub'] is not None]
    maximums = [s['price_max_rub'] for s in paid if s['price_max_rub'] is not None]
    durations = {s['duration_minutes'] for s in paid}
    duration = next(iter(durations)) if len(durations) == 1 and None not in durations else None
    experience, experience_evidence, experience_claims = _experience(about)
    ids = []
    for image in main.select('img[src*="/users/user_"]'):
        match = re.search(r'/users/user_(\d+)_', image.get('src', ''))
        if match:
            ids.append(match[1])
    profile_id = ids[0] if ids else (card or {}).get('id')
    reviews = clean_text(soup.select_one('#vkl_otzyv .n'))
    review_count = _number(reviews) if reviews and re.search(r'\d', reviews) else None
    summary = (card or {}).get('summary') or (card or {}).get('description') or (card or {}).get('short_description')
    if not summary:
        meta = soup.select_one('meta[name="description"]')
        summary = meta.get('content') if meta else None
    raw_parts = [name, status]
    raw_parts.extend(f'[{key}]\n{value}' for key, value in sections.items() if value)
    raw_text = '\n\n'.join(value for value in raw_parts if value)
    flags = []
    if not education:
        flags.append('No education text found in the public HTML')
    if not services:
        flags.append('No structured services found; consult raw_profile_text')
    if len(exact) > 1:
        flags.append('Services have different prices; use services rather than one aggregate price')
    if len({claim['years'] for claim in experience_claims}) > 1:
        flags.append('Profile contains conflicting experience claims; inspect experience_claims')
    return _redact_tree({
        'schema_version': 1,
        'id': profile_id, 'name': name, 'url': url,
        'city': cities[0] if cities else None, 'cities': cities,
        'professional_status': status or None,
        'short_description': summary,
        'price_rub': price,
        'price_min_rub': min(minimums) if minimums and len(minimums) == len(paid) else None,
        'price_max_rub': max(maximums) if maximums and len(maximums) == len(paid) else None,
        'duration_minutes': duration,
        'online': True if any(s['format'] == 'online' for s in services) else None,
        'offline': True if any(s['format'] == 'offline' for s in services) else None,
        'experience_years': experience, 'experience_evidence': experience_evidence,
        'experience_claims': experience_claims,
        'approaches': approaches,
        'specializations': _evidence(about, r'специализи[рз]|работаю\s+с|помогаю\s+(?:при|с)|запрос|проблем|обратиться\s+за\s+помощью'),
        'target_audience': _evidence(about, r'консультиру\w*.*(?:дет|подрост|взросл|пар|сем)|помо[гщ]\w*.*(?:дет|подрост|взросл|пар|сем)'),
        'limitations': _evidence(about, r'не\s+работаю|не\s+консультирую|противопоказан|не\s+беру'),
        'supervision': _evidence(about, r'супервиз'),
        'personal_therapy': _evidence(about, r'личн\w*\s+терап|собственн\w*\s+терап'),
        'services': services, 'education': education or None,
        'education_entries': education_entries, 'about': about,
        'sections': sections, 'raw_profile_text': raw_text,
        'raw_profile_text_chars': len(raw_text), 'reviews_count': review_count,
        'rating': None, 'catalog_card': card, 'contacts_redacted': True,
        'warnings': flags,
        'scraped_at': datetime.now(timezone.utc).isoformat(),
    })
