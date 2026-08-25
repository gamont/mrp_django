#!/usr/bin/env python3
"""Static contract for the 1.0.x production-profile Django security gate."""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "release_validate.sh"
text = SCRIPT.read_text(encoding="utf-8")

required = {
    "helper": "run_web_secure()",
    "DEBUG off": "DJANGO_DEBUG=0",
    "SSL redirect": "DJANGO_SECURE_SSL_REDIRECT=1",
    "session secure": "DJANGO_SESSION_COOKIE_SECURE=1",
    "csrf secure": "DJANGO_CSRF_COOKIE_SECURE=1",
    "HSTS": "DJANGO_SECURE_HSTS_SECONDS=31536000",
    "HSTS preload": "DJANGO_SECURE_HSTS_PRELOAD=1",
    "proxy trust": "DJANGO_TRUST_PROXY=1",
    "strict deploy check": "check --deploy --fail-level WARNING",
    "release secret": "RELEASE_DJANGO_SECRET_KEY",
}
errors = [label for label, token in required.items() if token not in text]

# The normal smoke service must stay separate from this strict profile; otherwise
# SECURE_SSL_REDIRECT would turn the internal HTTP health check into an HTTPS redirect.
if "docker compose up -d web worker beat" not in text:
    errors.append("normal smoke service startup missing")

if errors:
    for error in errors:
        print(f"[FAIL] security profile contract missing: {error}", file=sys.stderr)
    print(f"SECURITY_PROFILE_LINT_FAILED errors={len(errors)}", file=sys.stderr)
    raise SystemExit(2)

print("SECURITY_PROFILE_LINT_OK strict_deploy_warning_gate=enabled smoke_http_profile=separate")
