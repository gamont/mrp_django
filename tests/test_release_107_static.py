from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def test_release_gate_has_strict_production_security_profile():
    text = (ROOT / "scripts" / "release_validate.sh").read_text(encoding="utf-8")
    assert "run_web_secure()" in text
    assert "DJANGO_DEBUG=0" in text
    assert "DJANGO_SECURE_SSL_REDIRECT=1" in text
    assert "DJANGO_SESSION_COOKIE_SECURE=1" in text
    assert "DJANGO_CSRF_COOKIE_SECURE=1" in text
    assert "DJANGO_SECURE_HSTS_SECONDS=31536000" in text
    assert "check --deploy --fail-level WARNING" in text


def test_security_profile_lint_is_wired_into_preflight():
    assert (ROOT / "scripts" / "security_profile_lint.py").is_file()
    preflight = (ROOT / "scripts" / "preflight.sh").read_text(encoding="utf-8")
    assert "security_profile_lint.py" in preflight


def test_release_107_docs_exist():
    assert (ROOT / "docs" / "HARDENING_1_0_7.md").is_file()
    assert (ROOT / "RELEASE_NOTES_1_0_7.md").is_file()
