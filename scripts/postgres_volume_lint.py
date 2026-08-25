#!/usr/bin/env python3
"""Validate the Docker volume target for the configured PostgreSQL image.

PostgreSQL Docker Official Image 18+ stores PGDATA under a major-version
subdirectory and declares /var/lib/postgresql as its volume. Stable 1.0.x
releases must not regress to the pre-18 /var/lib/postgresql/data target.
"""
from __future__ import annotations

import re
import sys
from pathlib import Path

try:
    import yaml
except Exception as exc:
    print(f"[FAIL] PyYAML unavailable: {exc}", file=sys.stderr)
    raise SystemExit(2)

ROOT = Path(__file__).resolve().parents[1]
COMPOSE = ROOT / "docker-compose.yml"


def default_from_interpolation(value: str) -> str:
    m = re.fullmatch(r"\$\{[A-Z0-9_]+:-([^}]+)\}", value.strip())
    return m.group(1) if m else value.strip()


def postgres_major(image: str) -> int | None:
    image = default_from_interpolation(image)
    tag = image.rsplit(":", 1)[-1] if ":" in image else "latest"
    m = re.match(r"(\d+)", tag)
    return int(m.group(1)) if m else None


def volume_targets(db: dict) -> list[str]:
    targets: list[str] = []
    for volume in db.get("volumes") or []:
        if isinstance(volume, str):
            parts = volume.split(":")
            if len(parts) >= 2:
                targets.append(parts[1])
        elif isinstance(volume, dict):
            target = volume.get("target")
            if target:
                targets.append(str(target))
    return targets


def main() -> int:
    data = yaml.safe_load(COMPOSE.read_text(encoding="utf-8")) or {}
    db = (data.get("services") or {}).get("db") or {}
    image = str(db.get("image") or "")
    major = postgres_major(image)
    targets = volume_targets(db)
    errors: list[str] = []

    if major is None:
        errors.append(f"cannot determine PostgreSQL major version from image: {image!r}")
    elif major >= 18:
        if "/var/lib/postgresql" not in targets:
            errors.append(
                "PostgreSQL 18+ must mount persistent storage at /var/lib/postgresql"
            )
        if "/var/lib/postgresql/data" in targets:
            errors.append(
                "legacy /var/lib/postgresql/data mount is unsafe for PostgreSQL 18+"
            )
    else:
        if "/var/lib/postgresql/data" not in targets:
            errors.append(
                "PostgreSQL 17 and below should mount persistent storage at /var/lib/postgresql/data"
            )

    if errors:
        for error in errors:
            print(f"[FAIL] {error}", file=sys.stderr)
        print(f"POSTGRES_VOLUME_LINT_FAILED errors={len(errors)}", file=sys.stderr)
        return 2

    print(
        "POSTGRES_VOLUME_LINT_OK "
        f"major={major} target={'/var/lib/postgresql' if major and major >= 18 else '/var/lib/postgresql/data'}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
