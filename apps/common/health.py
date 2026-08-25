from __future__ import annotations

import hmac
import os
from importlib.metadata import PackageNotFoundError, version

from django.conf import settings
from django.db import connection
from django.db.migrations.executor import MigrationExecutor
from django.http import HttpRequest, HttpResponse, JsonResponse
from django.views.decorators.cache import never_cache
from django.views.decorators.http import require_GET

from .metrics import render_prometheus


def _package_version() -> str:
    try:
        return version("mrp-django")
    except PackageNotFoundError:
        return getattr(settings, "MRP_VERSION", "0.2.1")


@never_cache
@require_GET
def live(request: HttpRequest) -> JsonResponse:
    return JsonResponse({"status": "ok", "service": "mrp-django", "version": _package_version()})


@never_cache
@require_GET
def ready(request: HttpRequest) -> JsonResponse:
    checks: dict[str, object] = {}
    status_code = 200

    try:
        with connection.cursor() as cursor:
            cursor.execute("SELECT 1")
            cursor.fetchone()
        checks["database"] = "ok"
    except Exception as exc:  # pragma: no cover - depende de infraestrutura
        checks["database"] = {"status": "error", "detail": str(exc)}
        status_code = 503

    if status_code == 200:
        try:
            executor = MigrationExecutor(connection)
            plan = executor.migration_plan(executor.loader.graph.leaf_nodes())
            if plan:
                checks["migrations"] = {
                    "status": "pending",
                    "count": len(plan),
                    "items": [f"{migration.app_label}.{migration.name}" for migration, _ in plan[:20]],
                }
                status_code = 503
            else:
                checks["migrations"] = "ok"
        except Exception as exc:  # pragma: no cover - depende de infraestrutura
            checks["migrations"] = {"status": "error", "detail": str(exc)}
            status_code = 503

    return JsonResponse(
        {"status": "ok" if status_code == 200 else "not_ready", "checks": checks},
        status=status_code,
    )


@never_cache
@require_GET
def metrics(request: HttpRequest) -> HttpResponse:
    configured_token = os.getenv("MRP_METRICS_TOKEN", "")
    if configured_token:
        supplied = request.headers.get("X-Metrics-Token", "")
        if not hmac.compare_digest(configured_token, supplied):
            return HttpResponse("forbidden\n", status=403, content_type="text/plain; charset=utf-8")

    lines = [render_prometheus().rstrip("\n")]
    try:
        with connection.cursor() as cursor:
            cursor.execute("SELECT 1")
            cursor.fetchone()
        lines.extend(
            [
                "# HELP mrp_database_up Indica se o banco de dados está acessível.",
                "# TYPE mrp_database_up gauge",
                "mrp_database_up 1",
            ]
        )
    except Exception:  # pragma: no cover - depende de infraestrutura
        lines.extend(
            [
                "# HELP mrp_database_up Indica se o banco de dados está acessível.",
                "# TYPE mrp_database_up gauge",
                "mrp_database_up 0",
            ]
        )
    return HttpResponse("\n".join(lines) + "\n", content_type="text/plain; version=0.0.4")
