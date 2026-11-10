"""Public archives must exclude private state and fail on unsafe source content."""
import importlib.util
import json
from pathlib import Path
import zipfile

import pytest


ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location('publication_builder', ROOT / 'scripts/prepare_publication.py')
publication = importlib.util.module_from_spec(spec)
spec.loader.exec_module(publication)


def minimal_project(tmp_path):
    root = tmp_path / 'project'
    for relative in publication._FIXED:
        path = root / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text('Публичный вымышленный пример\n')
    return root


def test_public_bundle_excludes_private_state_and_real_example_files(tmp_path):
    root = minimal_project(tmp_path)
    for relative in ['work/cookies.txt', 'data/private/export.jsonl', '.venv/config',
                     'examples/cli-auth-5.jsonl', 'b17_parser/__pycache__/a.pyc', '.git/config']:
        path = root / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text('PRIVATE_UNPUBLISHED_MARKER')
    path = root / 'b17_parser/core.py'
    path.parent.mkdir(exist_ok=True)
    path.write_text('"""Public source."""\n')
    archive = tmp_path / 'public.zip'
    manifest = publication.build_publication(root, archive)
    with zipfile.ZipFile(archive) as source:
        names = source.namelist()
        assert 'b17-parser/b17_parser/core.py' in names
        assert not any('work/' in n or 'data/' in n or '.venv/' in n or '.git/' in n or 'cli-auth-5' in n for n in names)
        assert all(b'PRIVATE_UNPUBLISHED_MARKER' not in source.read(n) for n in names)
    assert all(not Path(item['path']).is_absolute() for item in manifest['files'])
    assert manifest['checks']['network_used'] is False and manifest['checks']['git_used'] is False


def test_selected_symlink_is_rejected(tmp_path):
    root = minimal_project(tmp_path)
    target = root / 'README.md'
    target.unlink()
    private = tmp_path / 'private.txt'
    private.write_text('private')
    target.symlink_to(private)
    with pytest.raises(ValueError, match='ссылка'):
        publication.build_publication(root, tmp_path / 'public.zip')


def test_private_marker_is_not_echoed_and_no_archive_is_created(tmp_path):
    root = minimal_project(tmp_path)
    marker = 'private_data_value'
    (root / 'README.md').write_text(marker)
    archive = tmp_path / 'public.zip'
    with pytest.raises(ValueError, match='частный маркер') as caught:
        publication.build_publication(root, archive, [marker])
    assert marker not in str(caught.value)
    assert not archive.exists()


def test_absolute_home_path_is_rejected(tmp_path):
    root = minimal_project(tmp_path)
    path = '/' + 'Users' + '/example-owner/project/'
    (root / 'README.md').write_text(path)
    with pytest.raises(ValueError, match='absolute_home_path'):
        publication.build_publication(root, tmp_path / 'public.zip')


def test_public_sample_is_explicitly_synthetic_and_not_a_local_session():
    record = json.loads((ROOT / 'examples/profiles.sample.jsonl').read_text())
    assert record['example_is_synthetic'] is True
    assert record['name'].startswith('Тестовый специалист')
    assert record['url'].endswith('/fixture_profile_01/')
    assert 'cookies' not in record and 'capture_provenance' not in record
    assert record['raw_profile_text_chars'] == len(record['raw_profile_text'])
