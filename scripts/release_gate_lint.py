#!/usr/bin/env python3
"""Static contract for the stable release gate.

One-off ``web`` commands must bypass entrypoint bootstrap side effects. The web
service itself is still started normally later, which validates the production
entrypoint exactly once.
"""
from __future__ import annotations

import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "release_validate.sh"
text = SCRIPT.read_text(encoding="utf-8")
errors: list[str] = []

if "run_web()" not in text:
    errors.append("release_validate.sh must define run_web helper")
if "SKIP_DJANGO_BOOTSTRAP=1" not in text:
    errors.append("run_web must set SKIP_DJANGO_BOOTSTRAP=1")
if "run_web_secure()" not in text:
    errors.append("release_validate.sh must define run_web_secure production-profile helper")
for token in (
    "DJANGO_DEBUG=0",
    "DJANGO_SECURE_SSL_REDIRECT=1",
    "DJANGO_SESSION_COOKIE_SECURE=1",
    "DJANGO_CSRF_COOKIE_SECURE=1",
    "DJANGO_SECURE_HSTS_SECONDS=31536000",
):
    if token not in text:
        errors.append(f"secure deploy gate missing production setting: {token}")

# Raw one-off invocations reintroduce repeated migrate/bootstrap/collectstatic.
raw = []
for lineno, line in enumerate(text.splitlines(), 1):
    if re.search(r"docker\s+compose\s+run\s+--rm\s+web\b", line):
        raw.append(lineno)
if raw:
    errors.append("raw 'docker compose run --rm web' found at line(s): " + ", ".join(map(str, raw)))

required = [
    "run_web python manage.py migrate --noinput",
    "run_web python manage.py makemigrations --check --dry-run",
    "run_web python manage.py bootstrap_roles",
    "run_web python manage.py check",
    "run_web_secure python manage.py check --deploy --fail-level WARNING",
    "run_web python manage.py system_check",
    "run_web pytest -q",
    "run_web python manage.py seed_demo",
]
for token in required:
    if token not in text:
        errors.append(f"release gate missing one-off command through run_web: {token}")

# The long-running web container must *not* skip bootstrap; this is where the
# production entrypoint is validated once.
if "docker compose up -d web worker beat" not in text:
    errors.append("release gate must start normal web/worker/beat services")

if errors:
    for error in errors:
        print(f"[FAIL] {error}", file=sys.stderr)
    print(f"RELEASE_GATE_LINT_FAILED errors={len(errors)}", file=sys.stderr)
    raise SystemExit(2)

print("RELEASE_GATE_LINT_OK one_off_bootstrap=disabled secure_deploy_check=enabled production_entrypoint=enabled")
