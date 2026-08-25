from __future__ import annotations

from collections import Counter
from threading import Lock
from time import monotonic

_lock = Lock()
_request_count: Counter[tuple[str, str, int]] = Counter()
_request_duration_seconds: Counter[tuple[str, str]] = Counter()
_started_at = monotonic()


def observe_request(*, method: str, route: str, status_code: int, duration_seconds: float) -> None:
    route = route or "unresolved"
    with _lock:
        _request_count[(method, route, status_code)] += 1
        # Counter é suficiente para exportar soma; a contagem já está no outro contador.
        _request_duration_seconds[(method, route)] += duration_seconds


def render_prometheus() -> str:
    lines = [
        "# HELP mrp_process_uptime_seconds Tempo de atividade do processo web.",
        "# TYPE mrp_process_uptime_seconds gauge",
        f"mrp_process_uptime_seconds {max(monotonic() - _started_at, 0):.6f}",
        "# HELP mrp_http_requests_total Requisições HTTP processadas.",
        "# TYPE mrp_http_requests_total counter",
    ]
    with _lock:
        for (method, route, status_code), value in sorted(_request_count.items()):
            lines.append(
                "mrp_http_requests_total"
                f'{{method="{_escape(method)}",route="{_escape(route)}",status="{status_code}"}} {value}'
            )
        lines.extend(
            [
                "# HELP mrp_http_request_duration_seconds_sum Soma da duração das requisições HTTP.",
                "# TYPE mrp_http_request_duration_seconds_sum counter",
            ]
        )
        for (method, route), value in sorted(_request_duration_seconds.items()):
            lines.append(
                "mrp_http_request_duration_seconds_sum"
                f'{{method="{_escape(method)}",route="{_escape(route)}"}} {value:.6f}'
            )
    return "\n".join(lines) + "\n"


def _escape(value: str) -> str:
    return str(value).replace("\\", "\\\\").replace('"', '\\"').replace("\n", "\\n")
