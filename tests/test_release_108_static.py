from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def test_postgres_18_uses_parent_volume_mount():
    compose = (ROOT / "docker-compose.yml").read_text(encoding="utf-8")
    assert "image: postgres:18-alpine" in compose
    assert "postgres_data:/var/lib/postgresql" in compose
    assert "postgres_data:/var/lib/postgresql/data" not in compose


def test_postgres_volume_lint_is_wired_into_preflight_and_ci():
    assert (ROOT / "scripts" / "postgres_volume_lint.py").is_file()
    preflight = (ROOT / "scripts" / "preflight.sh").read_text(encoding="utf-8")
    ci = (ROOT / ".github" / "workflows" / "ci.yml").read_text(encoding="utf-8")
    assert "postgres_volume_lint.py" in preflight
    assert "postgres_volume_lint.py" in ci


def test_release_gate_recreates_database_and_checks_persistence():
    gate = (ROOT / "scripts" / "release_validate.sh").read_text(encoding="utf-8")
    assert "PostgreSQL persistence probe" in gate
    assert "docker compose rm -sf db" in gate
    assert "release_volume_probe" in gate
    assert "PostgreSQL named-volume persistence survived container recreation" in gate


def test_release_108_docs_exist():
    assert (ROOT / "docs" / "HARDENING_1_0_8.md").is_file()
    assert (ROOT / "RELEASE_NOTES_1_0_8.md").is_file()
