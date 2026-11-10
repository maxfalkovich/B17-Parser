"""Export explicitly selected macOS Chrome B17 cookies for the collector CLI.

This optional setup helper reads one profile without changing Chrome or opening
browser windows. It decrypts only a temporary B17-only database subset. Browser
cookie decryption uses the optional browser-cookie3 package and may require the
operating system's normal Keychain access approval. No cookie values or keys are
printed. Supply the resulting private file to the collector's --cookies-file.
"""
from __future__ import annotations

import argparse
from contextlib import closing
import http.cookiejar
import importlib
import os
from pathlib import Path
import re
import sqlite3
import sys
import tempfile


_DOMAINS = {'b17.ru', '.b17.ru', 'www.b17.ru'}
_PROFILE = re.compile(r'(?:Default|Profile [1-9][0-9]*)\Z')


class SessionImportError(RuntimeError):
    """An actionable setup error whose message contains no cookie values."""


def _copy_b17_subset(source: Path, subset: Path) -> int:
    """Copy only exact B17 cookie rows and the format version, read-only.

    Chrome's source database, WAL, and profile are never modified or copied in
    full. The destination is private and must not already exist. Both selects
    share a read transaction so the cookie rows and format version are coherent.
    Returns the number of encrypted cookie rows copied, including expired rows.
    """
    descriptor = os.open(subset, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    os.close(descriptor)
    with closing(sqlite3.connect(source.resolve().as_uri() + '?mode=ro', uri=True, timeout=3)) as original:
        original.execute('BEGIN')
        with closing(sqlite3.connect(subset)) as target:
            count = 0
            for table in ('cookies', 'meta'):
                schema = original.execute(
                    'SELECT sql FROM sqlite_master WHERE type=? AND name=?', ('table', table),
                ).fetchone()
                if not schema:
                    if table == 'cookies':
                        raise SessionImportError('Selected profile has no supported cookie table')
                    continue
                target.execute(schema[0])
                if table == 'cookies':
                    cursor = original.execute(
                        "SELECT * FROM cookies WHERE host_key IN ('b17.ru','.b17.ru','www.b17.ru')",
                    )
                else:
                    cursor = original.execute("SELECT * FROM meta WHERE key='version'")
                rows = cursor.fetchall()
                if rows:
                    placeholders = ','.join('?' for _ in cursor.description)
                    target.executemany(f'INSERT INTO {table} VALUES ({placeholders})', rows)
                if table == 'cookies':
                    count = len(rows)
            target.commit()
    return count


def import_profile(profile: str, output: str | Path, *, chrome_root: str | Path | None = None) -> int:
    """Export one authorized profile's unexpired B17 cookies; return their count.

    Profile is a directory identifier such as Default or Profile 1, never a path.
    Without an injected chrome_root this helper supports macOS Chrome only. The
    caller must have permission to use that profile's B17 session. Existing
    output files and symlinks are never replaced, and the exported file is 0600.
    New output parents and temporary directories are private; permissions of an
    existing output parent are preserved. Temporary subsets and temporary cookie
    exports are removed on success or failure. No browser or network action runs.
    """
    if not isinstance(profile, str) or not _PROFILE.fullmatch(profile):
        raise SessionImportError('Use a profile directory identifier: Default or Profile N')
    destination = Path(output).expanduser()
    if destination.exists() or destination.is_symlink():
        raise SessionImportError('Output already exists; choose a new private filename')
    if chrome_root is None:
        if sys.platform != 'darwin':
            raise SessionImportError('This helper supports macOS Chrome; supply a private cookie export on other systems')
        chrome_root = Path.home() / 'Library/Application Support/Google/Chrome'
    root = Path(chrome_root).expanduser()
    source = root / profile / 'Cookies'
    if not source.is_file():
        source = root / profile / 'Network/Cookies'
    if not source.is_file():
        raise SessionImportError('Selected Chrome profile has no cookie database')
    try:
        backend = importlib.import_module('browser_cookie3')
    except ImportError:
        raise SessionImportError('Install the optional helper dependency: python -m pip install browser-cookie3') from None
    destination.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix='.b17-session-', dir=destination.parent) as private:
        temporary = Path(private)
        temporary.chmod(0o700)
        subset = temporary / 'b17-encrypted-subset.sqlite'
        if not _copy_b17_subset(source, subset):
            raise SessionImportError('Selected profile contains no B17 cookies')
        cookies = backend.chrome(cookie_file=str(subset), domain_name='b17.ru')
        temporary_export = temporary / 'b17-cookies.txt'
        jar = http.cookiejar.MozillaCookieJar(str(temporary_export))
        for cookie in cookies:
            if cookie.domain in _DOMAINS and not cookie.is_expired():
                jar.set_cookie(cookie)
        if not len(jar):
            raise SessionImportError('Selected profile contains no unexpired B17 cookies')
        # Serialize with the standard Netscape generator before reserving output.
        descriptor = os.open(temporary_export, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
        os.close(descriptor)
        jar.save(ignore_discard=True, ignore_expires=False)
        temporary_export.chmod(0o600)
        contents = temporary_export.read_bytes()
        try:
            descriptor = os.open(destination, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
        except FileExistsError:
            raise SessionImportError('Output already exists; choose a new private filename') from None
        try:
            with os.fdopen(descriptor, 'wb') as exported:
                exported.write(contents)
                exported.flush()
                os.fsync(exported.fileno())
        except BaseException:
            destination.unlink(missing_ok=True)
            raise
    return len(jar)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--profile', required=True, help='Chrome profile directory: Default or Profile N')
    parser.add_argument('--output', required=True, type=Path, help='new private Netscape cookie file (never overwritten)')
    args = parser.parse_args(argv)
    try:
        count = import_profile(args.profile, args.output)
    except SessionImportError as exc:
        print(f'FAIL: {exc}', file=sys.stderr)
        return 2
    except Exception as exc:
        # Third-party exceptions can include decrypted data or filesystem paths.
        print(f'FAIL: session import failed ({type(exc).__name__})', file=sys.stderr)
        return 2
    print(f'OK: B17-only session exported privately; cookie count: {count}')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
