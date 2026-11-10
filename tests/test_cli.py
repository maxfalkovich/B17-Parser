import json
from pathlib import Path
from unittest.mock import Mock

from b17_parser.cli import main
from b17_parser.http import AccessError
from b17_parser.pacing import AccessGate


BASE = 'https://www.b17.ru/psiholog/sankt-peterburg/'


def test_inspect_with_active_cooldown_does_not_fetch(monkeypatch, tmp_path):
    access = tmp_path / 'access.json'
    AccessGate(access).block(3600)
    transport = Mock()
    monkeypatch.setattr('b17_parser.cli.HttpClient', lambda *a, **k: transport)
    assert main(['inspect', '--url', BASE, '--access-state', str(access)]) == 2
    transport.get.assert_not_called()


def test_login_cooldown_checked_before_browser_start(monkeypatch, tmp_path):
    access = tmp_path / 'access.json'
    AccessGate(access).block(3600)
    browser = Mock()
    monkeypatch.setattr('b17_parser.browser.BrowserClient', browser)
    assert main(['login', '--browser-profile', str(tmp_path / 'session'), '--access-state', str(access)]) == 2
    browser.assert_not_called()


def test_cli_export_is_lossless(tmp_path):
    source = tmp_path / 'records.jsonl'
    records = [{'url': 'https://www.b17.ru/name/', 'about': 'Текст\n' * 10000}]
    source.write_text(json.dumps(records[0], ensure_ascii=False) + '\n')
    target = tmp_path / 'records.json'
    assert main(['export', '--input', str(source), '--output', str(target), '--format', 'json']) == 0
    assert json.loads(target.read_text()) == records


def test_cli_rejects_nonfinite_delay(tmp_path):
    assert main(['inspect', '--url', BASE, '--delay', 'nan', '--access-state', str(tmp_path / 'access')]) == 2


def test_cli_saved_filter_export_and_builder_never_construct_http_client(monkeypatch, tmp_path, capsys):
    fixture = Path(__file__).parent / 'fixtures' / 'filter_controls.html'
    transport = Mock(side_effect=AssertionError('offline command touched network setup'))
    monkeypatch.setattr('b17_parser.cli.HttpClient', transport)
    reference, guide = tmp_path / 'filters.json', tmp_path / 'filters.md'
    assert main(['filters', '--url', BASE, '--html', str(fixture), '--output', str(reference), '--markdown', str(guide)]) == 0
    data = json.loads(reference.read_text())
    assert len(data['filters']) == 14
    assert data['source']['provenance']['mode'] == 'saved_html'
    assert 'Когнитивно-поведенческая' in guide.read_text()
    assert main(['build-url', '--catalog', str(reference), '--set', 'vid=1', '--set', 'price2=5000']) == 0
    assert capsys.readouterr().out.strip() == BASE + '?vid=1&price2=5000'
    transport.assert_not_called()


def test_cli_invalid_reference_reports_error_without_traceback(tmp_path, capsys):
    path = tmp_path / 'bad.json'
    path.write_text('[]')
    assert main(['build-url', '--catalog', str(path)]) == 2
    assert 'Error:' in capsys.readouterr().err


def test_cli_filter_outputs_cannot_overwrite_inputs_or_each_other(tmp_path):
    fixture = Path(__file__).parent / 'fixtures' / 'filter_controls.html'
    source = tmp_path / 'input.html'
    source.write_bytes(fixture.read_bytes())
    original = source.read_bytes()
    assert main(['filters', '--url', BASE, '--html', str(source), '--output', str(source)]) == 2
    assert source.read_bytes() == original
    output = tmp_path / 'output.json'
    assert main(['filters', '--url', BASE, '--html', str(source), '--output', str(output), '--markdown', str(output)]) == 2
    assert not output.exists()


def test_cli_reads_legacy_cp1251_filter_capture(tmp_path):
    fixture = Path(__file__).parent / 'fixtures' / 'filter_controls.html'
    source, target = tmp_path / 'legacy.html', tmp_path / 'reference.json'
    source.write_bytes(fixture.read_text().encode('cp1251'))
    assert main(['filters', '--url', BASE, '--html', str(source), '--output', str(target)]) == 0
    data = json.loads(target.read_text())
    assert data['filters']['vid']['options'][0]['label'] == 'Индивидуально'
