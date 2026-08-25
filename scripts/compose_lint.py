#!/usr/bin/env python3
"""Static docker-compose contract checks for the stable 1.0.x release line.

This intentionally avoids importing Django and supplements ``docker compose config``.
It catches accidental removal of services/healthchecks relied on by release_validate.sh.
"""
from __future__ import annotations

import sys
from pathlib import Path

try:
    import yaml
except Exception as exc:  # pragma: no cover - dependency check is itself useful
    print(f"[FAIL] PyYAML unavailable: {exc}", file=sys.stderr)
    raise SystemExit(2)

ROOT = Path(__file__).resolve().parents[1]
COMPOSE = ROOT / "docker-compose.yml"
REQUIRED_SERVICES = {"db", "redis", "web", "worker", "beat"}
HEALTH_REQUIRED = {"db", "redis", "web"}


def main() -> int:
    errors: list[str] = []
    data = yaml.safe_load(COMPOSE.read_text(encoding="utf-8")) or {}
    services = data.get("services") or {}

    missing = sorted(REQUIRED_SERVICES - set(services))
    if missing:
        errors.append(f"required services missing: {', '.join(missing)}")

    for name in sorted(HEALTH_REQUIRED & set(services)):
        if not services[name].get("healthcheck"):
            errors.append(f"service {name!r} must define healthcheck")

    worker = services.get("worker") or {}
    command = worker.get("command", "")
    if isinstance(command, list):
        command = " ".join(map(str, command))
    if "celery" not in str(command).lower():
        errors.append("worker command does not appear to start Celery")

    # Stable releases must keep host ports configurable so the release gate can run
    # beside an existing development stack using ephemeral host ports.
    raw_compose = COMPOSE.read_text(encoding="utf-8")
    for variable in ("POSTGRES_HOST_PORT", "WEB_HOST_PORT"):
        if "${" + variable not in raw_compose:
            errors.append(f"compose must parameterize host port with {variable}")

    beat = services.get("beat") or {}
    command = beat.get("command", "")
    if isinstance(command, list):
        command = " ".join(map(str, command))
    if "celery" not in str(command).lower() or "beat" not in str(command).lower():
        errors.append("beat command does not appear to start Celery Beat")

    if errors:
        for error in errors:
            print(f"[FAIL] {error}", file=sys.stderr)
        print(f"COMPOSE_LINT_FAILED errors={len(errors)}", file=sys.stderr)
        return 2

    print(
        "COMPOSE_LINT_OK "
        f"services={len(services)} required={len(REQUIRED_SERVICES)} "
        f"healthchecks={len(HEALTH_REQUIRED)}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
