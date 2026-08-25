from pathlib import Path


def test_release_104_metadata_and_compose_guard():
    root = Path(__file__).resolve().parents[1]
    version = (root / 'VERSION').read_text(encoding='utf-8').strip()
    settings_text = (root / 'config/settings.py').read_text(encoding='utf-8')
    release_script = (root / 'scripts/release_validate.sh').read_text(encoding='utf-8')

    assert version.startswith('1.0.')
    assert f'MRP_VERSION = "{version}"' in settings_text
    assert (root / 'scripts/compose_lint.py').exists()
    assert 'release_diagnostics' in release_script
    assert 'docker compose down --remove-orphans' in release_script
    assert 'RELEASE_KEEP_STACK' in release_script
