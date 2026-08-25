from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def test_release_102_metadata_is_consistent():
    version = (ROOT / "VERSION").read_text().strip()
    settings_text = (ROOT / "config/settings.py").read_text()
    assert version.startswith("1.0.")
    assert f'MRP_VERSION = "{version}"' in settings_text


def test_release_consistency_gate_is_wired_everywhere():
    consistency = ROOT / "scripts/release_consistency.py"
    preflight = ROOT / "scripts/preflight.sh"
    release_validate = ROOT / "scripts/release_validate.sh"

    assert consistency.exists()

    preflight_text = preflight.read_text()
    release_validate_text = release_validate.read_text()

    # O gate de consistência é executado pelo preflight.
    assert "release_consistency.py" in preflight_text

    # A validação de release executa o preflight e, portanto,
    # herda transitivamente o gate de consistência.
    assert "preflight.sh" in release_validate_text
    assert "release_consistency.py" in (ROOT / ".github/workflows/ci.yml").read_text()


def test_legacy_stable_release_test_no_longer_pins_100():
    text = (ROOT / "tests/test_release_100.py").read_text()
    assert 'settings.MRP_VERSION == "1.0.0"' not in text
    assert 'read_text().strip() == "1.0.0"' not in text
