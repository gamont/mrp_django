from pathlib import Path

from django.conf import settings


def test_release_is_stable_1_0_line():
    version = Path("VERSION").read_text().strip()
    assert settings.MRP_VERSION == version
    assert version.startswith("1.0.")


def test_release_operational_scripts_exist():
    for name in (
        "scripts/backup.sh",
        "scripts/restore.sh",
        "scripts/release_validate.sh",
        "scripts/smoke_mrp.sh",
    ):
        assert Path(name).is_file()


def test_release_runbooks_exist():
    for name in (
        "docs/INSTALLATION_1_0.md",
        "docs/BACKUP_RESTORE_1_0.md",
        "docs/PRODUCTION_RUNBOOK_1_0.md",
        "docs/ACCEPTANCE_1_0.md",
    ):
        assert Path(name).is_file()
