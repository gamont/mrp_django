from __future__ import annotations

import importlib
import json
import socket
from dataclasses import asdict, dataclass
from pathlib import Path
from urllib.parse import urlparse

from django.conf import settings
from django.core.checks import run_checks
from django.core.management.base import BaseCommand
from django.db import connection


@dataclass
class CheckResult:
    name: str
    ok: bool
    detail: str
    required: bool = True


def _release_version() -> str:
    version_file = Path(settings.BASE_DIR) / "VERSION"
    try:
        return version_file.read_text(encoding="utf-8").strip()
    except OSError:
        return str(settings.MRP_VERSION)


def _hostname_from_url(value: str) -> str:
    parsed = urlparse(value)
    if parsed.hostname:
        return parsed.hostname
    raise ValueError(f"URL sem hostname: {value!r}")


class Command(BaseCommand):
    help = "Executa o readiness check consolidado da instalação MRP."

    def add_arguments(self, parser):
        parser.add_argument("--json", action="store_true", dest="as_json")
        parser.add_argument("--skip-redis", action="store_true")
        parser.add_argument("--skip-database", action="store_true")
        parser.add_argument("--skip-ortools", action="store_true")

    def handle(self, *args, **options):
        results: list[CheckResult] = []
        expected_version = _release_version()

        messages = run_checks(tags=None)
        errors = [m for m in messages if getattr(m, "level", 0) >= 40]
        warnings = [m for m in messages if 30 <= getattr(m, "level", 0) < 40]
        results.append(CheckResult("django_checks", not errors, f"errors={len(errors)} warnings={len(warnings)}"))

        if not options["skip_database"]:
            try:
                with connection.cursor() as cursor:
                    cursor.execute("SELECT 1")
                    value = cursor.fetchone()[0]
                results.append(CheckResult("database", value == 1, f"vendor={connection.vendor}"))
            except Exception as exc:  # pragma: no cover
                results.append(CheckResult("database", False, f"{type(exc).__name__}: {exc}"))

        redis_url = getattr(settings, "REDIS_URL", settings.CELERY_BROKER_URL)
        if not options["skip_redis"]:
            try:
                redis = importlib.import_module("redis")
                client = redis.Redis.from_url(redis_url, socket_timeout=2)
                pong = client.ping()
                results.append(CheckResult("redis", bool(pong), redis_url))
            except Exception as exc:  # pragma: no cover
                results.append(CheckResult("redis", False, f"{type(exc).__name__}: {exc}"))

        if not options["skip_ortools"]:
            try:
                cp_model = importlib.import_module("ortools.sat.python.cp_model")
                model = cp_model.CpModel()
                x = model.new_int_var(0, 10, "x")
                model.add(x == 7)
                solver = cp_model.CpSolver()
                status = solver.solve(model)
                ok = status in (cp_model.OPTIMAL, cp_model.FEASIBLE) and solver.value(x) == 7
                results.append(CheckResult("ortools_cp_sat", ok, f"status={status}"))
            except Exception as exc:  # pragma: no cover
                results.append(CheckResult("ortools_cp_sat", False, f"{type(exc).__name__}: {exc}"))

        try:
            celery_module = importlib.import_module("celery")
            results.append(CheckResult("celery_import", True, f"version={getattr(celery_module, '__version__', 'unknown')}"))
        except Exception as exc:
            results.append(CheckResult("celery_import", False, f"{type(exc).__name__}: {exc}"))

        results.append(CheckResult("mrp_version", settings.MRP_VERSION == expected_version, f"settings={settings.MRP_VERSION} file={expected_version}"))

        for name, value in (("broker_dns", settings.CELERY_BROKER_URL), ("redis_dns", redis_url)):
            try:
                host = _hostname_from_url(value)
                socket.getaddrinfo(host, None)
                results.append(CheckResult(name, True, host, required=False))
            except Exception as exc:  # pragma: no cover
                results.append(CheckResult(name, False, str(exc), required=False))

        failed = [r for r in results if r.required and not r.ok]
        payload = {"version": settings.MRP_VERSION, "expected_version": expected_version, "ok": not failed, "results": [asdict(r) for r in results]}
        if options["as_json"]:
            self.stdout.write(json.dumps(payload, ensure_ascii=False, indent=2))
        else:
            for result in results:
                mark = "OK" if result.ok else ("WARN" if not result.required else "FAIL")
                self.stdout.write(f"[{mark:4}] {result.name}: {result.detail}")
            self.stdout.write("")
            if failed:
                self.stdout.write(self.style.ERROR(f"SYSTEM_CHECK_FAILED: {len(failed)} requisito(s)."))
            else:
                self.stdout.write(self.style.SUCCESS(f"SYSTEM_CHECK_OK: release {expected_version} pronta para smoke/E2E."))
        if failed:
            raise SystemExit(2)
