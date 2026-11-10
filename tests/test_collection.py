import json
from pathlib import Path
from urllib.parse import parse_qs, urlsplit

import pytest

from b17_parser.crawler import Collector
from b17_parser.http import AccessError, HttpClient, validate_page
from b17_parser.storage import append_record, export_records, read_jsonl

BASE = 'https://www.b17.ru/psiholog/sankt-peterburg/'


def catalog(page, count=10, reported=300, last=32):
    start = (page - 1) * 10
    cards = ''.join(f'<div class=item><a class=h name=spec{i} href=/person{i}/>Person {i}</a></div>'
                    for i in range(start, start + count))
    return f'''<h1>Catalog</h1><div id=master_filter_right><input name=f_city value=143></div>
    <div id=items_list><div class=list_blue_info_filter>Найдены {reported} специалистов</div>{cards}</div>
    <div id=page_list><a class=on href="?page={page}">{page}</a><a href="?page={last}">{last}</a></div>'''


def profile(i):
    return f'<h1>Person {i}</h1><div id=main class=vkladki_body><p>Complete description {i}</p></div>'


class FakeClient:
    def __init__(self, fail=None, last=32):
        self.calls = []
        self.fail = fail
        self.last = last

    def get(self, url):
        self.calls.append(url)
        if self.fail and self.fail in url:
            raise AccessError('IP temporarily blocked')
        if '/psiholog/' in url:
            page = int(parse_qs(urlsplit(url).query).get('page', ['1'])[0])
            return catalog(page, last=self.last)
        return profile(urlsplit(url).path)


def source():
    return {'mode': 'crawl', 'url': BASE, 'start_page': 1}


def test_more_than_300_and_resume_without_duplicates(tmp_path):
    output = tmp_path / 'data.jsonl'
    first = FakeClient()
    report = Collector(first, output, source()).run(305)
    assert report['completed'] == 305
    assert report['pages_collected'] == 31
    assert len(read_jsonl(output)) == 305
    second = FakeClient()
    report = Collector(second, output, source(), resume=True).run(400)
    assert report['completed'] == 320
    assert report['status'] == 'available_results_exhausted'
    assert len({r['url'] for r in read_jsonl(output)}) == 320
    assert len([u for u in second.calls if '/psiholog/' in u]) == 1


@pytest.mark.parametrize('start_page, expected_status', [
    (1, 'pagination_unverified'),
    (31, 'available_results_exhausted'),
])
def test_numbered_end_checks_total_only_from_first_page(tmp_path, start_page, expected_status):
    client = FakeClient(last=32)
    # From page 1 the fixture omits ten profiles from the reported full total.
    reported = 330 if start_page == 1 else 320
    client.get = lambda u: catalog(
        int(parse_qs(urlsplit(u).query).get('page', ['1'])[0]), reported=reported, last=32
    ) if '/psiholog/' in u else profile(u)
    config = {'mode': 'crawl', 'url': BASE + f'?page={start_page}', 'start_page': start_page}
    result = Collector(client, tmp_path / 'out.jsonl', config).run(400)
    assert result['status'] == expected_status
    assert result['completed'] == (320 if start_page == 1 else 20)
    assert result['terminal_evidence'] == 'numbered_pagination_end'
    assert result['catalog_exhausted'] is True
    assert result['fatal_error'] is None
    assert f'catalog page {start_page}' in result['coverage_note']


@pytest.mark.parametrize('start_page, expected_status', [
    (1, 'stopped_error'),
    (31, 'available_results_exhausted'),
])
def test_empty_end_checks_total_only_from_first_page(tmp_path, start_page, expected_status):
    client = FakeClient()
    def get(url):
        if '/psiholog/' not in url:
            return profile(url)
        page = int(parse_qs(urlsplit(url).query).get('page', ['1'])[0])
        return catalog(page, count=10 if page == start_page else 0, reported=320, last=33)
    client.get = get
    config = {'mode': 'crawl', 'url': BASE + f'?page={start_page}', 'start_page': start_page}
    result = Collector(client, tmp_path / 'out.jsonl', config).run(100)
    assert result['status'] == expected_status
    assert result['completed'] == 10
    if start_page == 1:
        assert 'before reported result count' in result['fatal_error']
    else:
        assert result['terminal_evidence'] == 'empty_catalog_page'
        assert result['fatal_error'] is None


def test_access_denial_stops_without_discarding_pending(tmp_path):
    path = tmp_path / 'data.jsonl'
    report = Collector(FakeClient(fail='person3/'), path, source()).run(8)
    assert report['status'] == 'stopped_error'
    assert report['completed'] == 3
    retry = FakeClient()
    report = Collector(retry, path, source(), resume=True).run(8)
    assert report['completed'] == 8
    assert not any('/psiholog/' in u for u in retry.calls)


def test_repeat_page_is_error_not_exhaustion(tmp_path):
    client = FakeClient()
    client.get = lambda u: catalog(1) if '/psiholog/' in u else profile(u)
    result = Collector(client, tmp_path / 'out.jsonl', source()).run(20)
    assert result['status'] == 'stopped_error'
    assert result['completed'] == 10


def test_unverifiable_pagination_is_reported(tmp_path):
    client = FakeClient()
    client.get = lambda u: catalog(1).split('<div id=page_list>')[0] if '/psiholog/' in u else profile(u)
    result = Collector(client, tmp_path / 'out.jsonl', source()).run(30)
    assert result['status'] == 'pagination_unverified'
    assert result['warnings']


def test_changed_resume_source_rejected(tmp_path):
    path = tmp_path / 'out.jsonl'
    Collector(FakeClient(), path, source()).run(1)
    with pytest.raises(ValueError, match='source differs'):
        Collector(FakeClient(), path, {**source(), 'url': BASE + '?sex=1'}, resume=True)


def test_resume_repairs_only_partial_tail(tmp_path):
    path = tmp_path / 'data.jsonl'
    append_record(path, {'url': 'https://www.b17.ru/test/', 'about': 'длинный текст'})
    with path.open('ab') as f:
        f.write(b'{"url":')
    assert len(read_jsonl(path, repair_tail=True)) == 1
    path.write_text('{"not_a_record":true}')
    with pytest.raises(ValueError, match='source URL'):
        read_jsonl(path, repair_tail=True)


def test_csv_json_preserve_long_unicode_and_nested_fields(tmp_path):
    records = [{'url': 'https://www.b17.ru/test/', 'about': 'Текст\n"' * 10000, 'services': [{'price': 4000}]}]
    export_records(records, tmp_path / 'x.json', 'json')
    assert json.loads((tmp_path / 'x.json').read_text()) == records
    export_records(records, tmp_path / 'x.csv', 'csv')
    import csv
    csv.field_size_limit(1_000_000)
    with (tmp_path / 'x.csv').open(encoding='utf-8-sig', newline='') as f:
        row = next(csv.DictReader(f))
    assert row['about'] == records[0]['about']
    assert json.loads(row['services']) == records[0]['services']


@pytest.mark.parametrize('html', ['<img src=/img/b17_guard.png>', '<title>Доступ ограничен</title>', 'Ваш IP заблокирован'])
def test_russian_block_stops(html):
    with pytest.raises(AccessError):
        validate_page(html, BASE)


def test_alias_redirect_is_deduplicated_by_final_url_and_id(tmp_path):
    client = FakeClient()
    def get(url):
        client.last_url = 'https://www.b17.ru/real_name/'
        return '<h1>Name</h1><div id=main class=vkladki_body><img src=/foto/users/user_123_100.jpg>Profile</div>'
    client.get = get
    config = {'mode': 'profiles', 'urls': ['https://www.b17.ru/alias/', 'https://www.b17.ru/another_alias/']}
    path = tmp_path / 'out.jsonl'
    result = Collector(client, path, config).run(10)
    assert result['completed'] == 1
    assert result['pending_profiles'] == 0
    assert read_jsonl(path)[0]['url'] == 'https://www.b17.ru/real_name/'


def test_aliases_deduplicated_by_id_without_same_final_url(tmp_path):
    client = FakeClient()
    def get(url):
        client.last_url = url
        return '<h1>Name</h1><div id=main class=vkladki_body><img src=/foto/users/user_123_100.jpg>Profile</div>'
    client.get = get
    config = {'mode': 'profiles', 'urls': ['https://www.b17.ru/alias/', 'https://www.b17.ru/another_alias/']}
    report = Collector(client, tmp_path / 'out.jsonl', config).run(10)
    assert report['completed'] == 1 and report['pending_profiles'] == 0
