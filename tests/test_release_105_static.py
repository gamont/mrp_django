from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def test_release_gate_uses_isolated_compose_project_and_ephemeral_ports():
    script = (ROOT / "scripts/release_validate.sh").read_text(encoding="utf-8")
    assert "COMPOSE_PROJECT_NAME" in script
    assert "RELEASE_COMPOSE_PROJECT" in script
    assert 'POSTGRES_HOST_PORT="${RELEASE_POSTGRES_HOST_PORT:-0}"' in script
    assert 'WEB_HOST_PORT="${RELEASE_WEB_HOST_PORT:-0}"' in script


def test_release_gate_cleans_isolated_volumes_by_default():
    script = (ROOT / "scripts/release_validate.sh").read_text(encoding="utf-8")
    assert "RELEASE_KEEP_VOLUMES" in script
    assert "down --remove-orphans --volumes" in script


def test_compose_ports_are_parameterized():
    compose = (ROOT / "docker-compose.yml").read_text(encoding="utf-8")
    assert "${POSTGRES_HOST_PORT:-5432}:5432" in compose
    assert "${WEB_HOST_PORT:-8000}:8000" in compose


def test_release_105_docs_exist():
    assert (ROOT / "docs/HARDENING_1_0_5.md").is_file()
    assert (ROOT / "RELEASE_NOTES_1_0_5.md").is_file()
