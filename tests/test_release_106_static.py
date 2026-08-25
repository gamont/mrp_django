from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def test_release_gate_bypasses_bootstrap_for_one_off_commands():
    text = (ROOT / "scripts" / "release_validate.sh").read_text(encoding="utf-8")
    assert "run_web()" in text
    assert "SKIP_DJANGO_BOOTSTRAP=1" in text
    assert "run_web python manage.py migrate --noinput" in text
    assert "run_web pytest -q" in text


def test_release_gate_lint_is_present():
    assert (ROOT / "scripts" / "release_gate_lint.py").is_file()
