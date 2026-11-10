"""Optional Chrome session setup tested only with fake cookie stores/decryption."""
from __future__ import annotations

import hashlib
import http.cookiejar
import importlib.util
from pathlib import Path
import sqlite3
import stat
from types import SimpleNamespace

import pytest


SCRIPT = Path(__file__).parents[1] / 'scripts/import_chrome_session.py'
spec = importlib.util.spec_from_file_location('b17_session_setup', SCRIPT)
helper = importlib.util.module_from_spec(spec)
spec.loader.exec_module(helper)


def cookie(domain='.b17.ru', name='session', expires=None):
    return http.cookiejar.Cookie(
        version=0, name=name, value='private-value-' + name, port=None, port_specified=False,
        domain=domain, domain_specified=domain.startswith('.'), domain_initial_dot=domain.startswith('.'),
        path='/psiholog/', path_specified=True, secure=True, expires=expires,
        discard=expires is None, comment=None, comment_url=None, rest={'HTTPOnly': ''}, rfc2109=False,
    )


def database(root, profile='Default', network=False, domains=None):
    path = root / profile / ('Network/Cookies' if network else 'Cookies')
    path.parent.mkdir(parents=True)
    with sqlite3.connect(path) as con:
        con.execute('CREATE TABLE cookies (host_key TEXT, name TEXT, encrypted_value BLOB)')
        con.executemany('INSERT INTO cookies VALUES (?,?,?)',
                        [(domain, f'cookie-{index}', b'encrypted-data') for index, domain in enumerate(
                            domains if domains is not None else ['b17.ru', '.b17.ru', 'www.b17.ru',
                                                                'example.org', 'evilb17.ru', 'b17.ru.evil.org'])])
        con.execute('CREATE TABLE meta (key TEXT PRIMARY KEY, value TEXT)')
        con.executemany('INSERT INTO meta VALUES (?,?)', [('version', '24'), ('unrelated', 'private-unrelated')])
        con.execute('CREATE TABLE unrelated (secret TEXT)')
        con.execute("INSERT INTO unrelated VALUES ('never-copy-this')")
    return path


def backend(monkeypatch, chrome):
    original = helper.importlib.import_module
    fake = SimpleNamespace(chrome=chrome)
    monkeypatch.setattr(helper.importlib, 'import_module',
                        lambda name: fake if name == 'browser_cookie3' else original(name))


def test_subset_and_export_are_exactly_b17_scoped_private_and_temporary(tmp_path, monkeypatch, capsys):
    root = tmp_path / 'chrome'
    original = database(root)
    before = hashlib.sha256(original.read_bytes()).hexdigest()
    destination = tmp_path / 'private' / 'cookies.txt'
    subset_paths = []

    def decrypt(*, cookie_file, domain_name):
        assert domain_name == 'b17.ru'
        path = Path(cookie_file)
        subset_paths.append(path)
        assert stat.S_IMODE(path.stat().st_mode) == 0o600
        assert stat.S_IMODE(path.parent.stat().st_mode) == 0o700
        with sqlite3.connect(path) as con:
            assert set(con.execute('SELECT host_key FROM cookies')) == {('b17.ru',), ('.b17.ru',), ('www.b17.ru',)}
            assert con.execute('SELECT key,value FROM meta').fetchall() == [('version', '24')]
            assert {row[0] for row in con.execute("SELECT name FROM sqlite_master WHERE type='table'")} == {'cookies', 'meta'}
        return [cookie('b17.ru', 'one'), cookie('.b17.ru', 'two'), cookie('www.b17.ru', 'three'),
                cookie('example.org', 'foreign'), cookie('evilb17.ru', 'similar'), cookie('.b17.ru', 'expired', expires=1)]

    backend(monkeypatch, decrypt)
    assert helper.import_profile('Default', destination, chrome_root=root) == 3
    assert stat.S_IMODE(destination.stat().st_mode) == 0o600
    assert stat.S_IMODE(destination.parent.stat().st_mode) == 0o700
    jar = http.cookiejar.MozillaCookieJar(str(destination))
    jar.load(ignore_discard=True, ignore_expires=False)
    assert {c.name for c in jar} == {'one', 'two', 'three'}
    assert all(c.secure and c.path == '/psiholog/' for c in jar)
    assert 'foreign' not in destination.read_text() and 'expired' not in destination.read_text()
    assert all(not path.exists() and not path.parent.exists() for path in subset_paths)
    assert list(destination.parent.glob('.b17-session-*')) == []
    assert hashlib.sha256(original.read_bytes()).hexdigest() == before
    assert not capsys.readouterr().out


def test_existing_export_is_not_overwritten_and_decryption_is_not_attempted(tmp_path, monkeypatch):
    destination = tmp_path / 'cookies.txt'
    destination.write_text('existing-private-export')
    backend(monkeypatch, lambda **kwargs: pytest.fail('must not decrypt existing output'))
    with pytest.raises(helper.SessionImportError, match='already exists'):
        helper.import_profile('Default', destination, chrome_root=tmp_path)
    assert destination.read_text() == 'existing-private-export'


def test_existing_symlink_is_not_followed(tmp_path):
    target = tmp_path / 'target'
    target.write_text('untouched')
    destination = tmp_path / 'cookies.txt'
    destination.symlink_to(target)
    with pytest.raises(helper.SessionImportError, match='already exists'):
        helper.import_profile('Default', destination, chrome_root=tmp_path)
    assert target.read_text() == 'untouched'


@pytest.mark.parametrize('profile', ['', '.', '..', '../Default', '/tmp/Default', 'Profile 0', 'Profile 01',
                                     'Profile -1', 'Profile 1/../Default', 'Default\\Other', 'Default/'])
def test_profile_identifiers_reject_paths_and_unsupported_directories(tmp_path, profile):
    with pytest.raises(helper.SessionImportError, match='directory identifier'):
        helper.import_profile(profile, tmp_path / 'cookies.txt', chrome_root=tmp_path)


def test_network_cookie_database_and_numbered_profile_are_supported(tmp_path, monkeypatch):
    root = tmp_path / 'chrome'
    database(root, profile='Profile 12', network=True)
    backend(monkeypatch, lambda **kwargs: [cookie()])
    assert helper.import_profile('Profile 12', tmp_path / 'export.txt', chrome_root=root) == 1


def test_no_b17_rows_does_not_invoke_decryption_or_create_export(tmp_path, monkeypatch):
    root = tmp_path / 'chrome'
    database(root, domains=['example.org'])
    backend(monkeypatch, lambda **kwargs: pytest.fail('must not access decryption for unrelated cookies'))
    destination = tmp_path / 'export.txt'
    with pytest.raises(helper.SessionImportError, match='no B17 cookies'):
        helper.import_profile('Default', destination, chrome_root=root)
    assert not destination.exists()
    assert not list(tmp_path.glob('.b17-session-*'))


def test_expired_or_foreign_decryption_results_do_not_create_export(tmp_path, monkeypatch):
    root = tmp_path / 'chrome'
    database(root)
    backend(monkeypatch, lambda **kwargs: [cookie(expires=1), cookie('example.org')])
    destination = tmp_path / 'export.txt'
    with pytest.raises(helper.SessionImportError, match='no unexpired B17 cookies'):
        helper.import_profile('Default', destination, chrome_root=root)
    assert not destination.exists()
    assert not list(tmp_path.glob('.b17-session-*'))


def test_decryption_failure_cleans_temporary_subset(tmp_path, monkeypatch):
    root = tmp_path / 'chrome'
    database(root)
    seen = []
    def fail(**kwargs):
        seen.append(Path(kwargs['cookie_file']))
        raise RuntimeError('private-value-never-print')
    backend(monkeypatch, fail)
    destination = tmp_path / 'export.txt'
    with pytest.raises(RuntimeError):
        helper.import_profile('Default', destination, chrome_root=root)
    assert not destination.exists()
    assert seen and not seen[0].exists()


def test_missing_optional_dependency_is_actionable(tmp_path, monkeypatch):
    root = tmp_path / 'chrome'
    database(root)
    def missing(name):
        raise ImportError('private-value-do-not-print')
    monkeypatch.setattr(helper.importlib, 'import_module', missing)
    with pytest.raises(helper.SessionImportError, match='pip install browser-cookie3') as error:
        helper.import_profile('Default', tmp_path / 'export.txt', chrome_root=root)
    assert 'private-value' not in str(error.value)


def test_default_mac_path_is_derived_from_home(tmp_path, monkeypatch):
    root = tmp_path / 'Library/Application Support/Google/Chrome'
    database(root)
    monkeypatch.setattr(helper.Path, 'home', classmethod(lambda cls: tmp_path))
    monkeypatch.setattr(helper.sys, 'platform', 'darwin')
    backend(monkeypatch, lambda **kwargs: [cookie()])
    assert helper.import_profile('Default', tmp_path / 'export.txt') == 1


def test_default_path_on_other_platforms_fails_before_browser_access(tmp_path, monkeypatch):
    monkeypatch.setattr(helper.sys, 'platform', 'linux')
    with pytest.raises(helper.SessionImportError, match='macOS Chrome'):
        helper.import_profile('Default', tmp_path / 'export.txt')


def test_cli_output_contains_only_success_and_count(tmp_path, monkeypatch, capsys):
    monkeypatch.setattr(helper, 'import_profile', lambda *args, **kwargs: 3)
    assert helper.main(['--profile', 'Default', '--output', str(tmp_path / 'export.txt')]) == 0
    out = capsys.readouterr()
    assert out.out == 'OK: B17-only session exported privately; cookie count: 3\n'
    assert not out.err


def test_cli_masks_third_party_exception_details(tmp_path, monkeypatch, capsys):
    def fail(*args, **kwargs):
        raise RuntimeError('private-value-secret-key')
    monkeypatch.setattr(helper, 'import_profile', fail)
    assert helper.main(['--profile', 'Default', '--output', str(tmp_path / 'export.txt')]) == 2
    out = capsys.readouterr()
    assert not out.out
    assert out.err == 'FAIL: session import failed (RuntimeError)\n'
    assert 'private-value' not in out.err
