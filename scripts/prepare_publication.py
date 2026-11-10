"""Build a reviewable source archive from a narrow allowlist without using Git."""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import re
import sys
import zipfile


_FIXED = ('README.md', 'FILTERS.md', 'LICENSE', 'pyproject.toml', '.gitignore', 'MANIFEST.in',
          'examples/README.md', 'examples/profiles.sample.jsonl',
          'examples/profiles.sample.json', 'examples/profiles.sample.csv')
_PATTERNS = ('b17_parser/*.py', 'scripts/*.py', 'tests/*.py', 'tests/fixtures/*.html',
             'references/*.json', '.github/workflows/*.yml')
_RULES = (
    ('absolute_home_path', re.compile(r'/(?:Users|home)/[A-Za-z0-9_.-]+/')),
    ('private_key', re.compile(r'-----BEGIN (?:RSA |OPENSSH |EC )?PRIVATE KEY-----')),
    ('account_token', re.compile(r'(?:skey|access_token|auth_token|csrf_token|sessionid)=[a-f0-9]{24,}', re.I)),
)


def candidate_files(root: Path) -> list[Path]:
    """Select only public source, synthetic examples, fixtures, and documentation.

    Private work/data, virtualenvs, caches, actual datasets, and Git metadata are
    never enumerated. Selected symlinks and paths escaping root are rejected.
    Missing required public files fail instead of producing an incomplete bundle.
    """
    root = root.resolve()
    relative = set(_FIXED)
    for pattern in _PATTERNS:
        relative.update(str(path.relative_to(root)) for path in root.glob(pattern))
    result = []
    for name in sorted(relative):
        path = root / name
        if path.is_symlink() or root not in path.resolve().parents:
            raise ValueError(f'Неподдерживаемая ссылка в публичном наборе: {name}')
        if not path.is_file():
            raise ValueError(f'Отсутствует обязательный файл: {name}')
        result.append(path)
    return result


def build_publication(root: Path, output: Path, private_patterns: list[str] | None = None) -> dict:
    """Validate and archive allowlisted files, returning a relative-path manifest.

    Private patterns are supplied explicitly and never written into the manifest
    or diagnostic text. This check is a review aid, not proof that arbitrary new
    content contains no personal information. The function never creates a Git
    repository, runs Git commands, contacts a remote service, or uploads files.
    """
    root, output = root.resolve(), output.resolve()
    files = candidate_files(root)
    if output in files:
        raise ValueError('Архив не должен заменять исходный файл')
    manifest = {'format_version': 1, 'files': [], 'checks': {
        'allowlist_only': True, 'selected_symlinks_rejected': True,
        'generic_secret_checks': True, 'private_pattern_check': bool(private_patterns),
        'network_used': False, 'git_used': False}}
    payloads = []
    for path in files:
        relative = str(path.relative_to(root))
        content = path.read_bytes()
        decoded = content.decode('utf-8')
        for name, pattern in _RULES:
            if pattern.search(decoded):
                raise ValueError(f'Проверка {name} не пройдена: {relative}')
        if any(value and value in decoded for value in (private_patterns or [])):
            raise ValueError(f'Обнаружен частный маркер: {relative}')
        manifest['files'].append({'path': relative, 'bytes': len(content),
                                  'sha256': hashlib.sha256(content).hexdigest()})
        payloads.append((relative, content))
    output.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(output, 'w', zipfile.ZIP_DEFLATED) as archive:
        for relative, content in payloads:
            info = zipfile.ZipInfo('b17-parser/' + relative, date_time=(1980, 1, 1, 0, 0, 0))
            info.compress_type = zipfile.ZIP_DEFLATED
            info.external_attr = 0o100644 << 16
            archive.writestr(info, content)
    manifest['archive_sha256'] = hashlib.sha256(output.read_bytes()).hexdigest()
    return manifest


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description='Локальная подготовка публичного архива без Git и сетевых запросов')
    parser.add_argument('--output', type=Path, default=Path('dist/b17-parser-public.zip'))
    parser.add_argument('--private-pattern-file', type=Path, help='частный JSON-массив строк для дополнительной проверки')
    args = parser.parse_args(argv)
    try:
        values = []
        if args.private_pattern_file:
            values = json.loads(args.private_pattern_file.read_text(encoding='utf-8'))
            if not isinstance(values, list) or any(not isinstance(v, str) for v in values):
                raise ValueError('Ожидается JSON-массив строк частных маркеров')
        root = Path(__file__).resolve().parents[1]
        manifest = build_publication(root, args.output, values)
        report = args.output.with_suffix('.manifest.json')
        report.write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
        print(f'OK: публичный набор подготовлен, файлов: {len(manifest["files"])}')
        return 0
    except (ValueError, OSError, UnicodeError, json.JSONDecodeError) as exc:
        print(f'FAIL: {exc}', file=sys.stderr)
        return 2


if __name__ == '__main__':
    raise SystemExit(main())
