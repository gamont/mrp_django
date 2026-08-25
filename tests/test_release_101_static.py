from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def test_version_files_stay_in_sync_after_101():
    version = (ROOT / "VERSION").read_text().strip()
    settings_text = (ROOT / "config/settings.py").read_text()
    assert version.startswith("1.0.")
    assert f'MRP_VERSION = "{version}"' in settings_text


def test_release_hardening_assets_exist():
    for rel in (
        "scripts/preflight.sh",
        "scripts/migration_lint.py",
        "docs/HARDENING_1_0_1.md",
        "RELEASE_NOTES_1_0_1.md",
    ):
        assert (ROOT / rel).exists(), rel


def test_system_check_is_not_pinned_to_100():
    text = (ROOT / "apps/common/management/commands/system_check.py").read_text()
    assert '== "1.0.0"' not in text
    assert "expected_version" in text
