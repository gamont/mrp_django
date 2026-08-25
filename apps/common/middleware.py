from __future__ import annotations

import logging
import time
import uuid

from django.conf import settings

from .context import reset_request_id, set_request_id
from .metrics import observe_request

logger = logging.getLogger("mrp.http")


class RequestContextMiddleware:
    """Propaga um identificador de correlação e registra duração/status."""

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        incoming = request.headers.get("X-Request-ID", "").strip()
        request_id = incoming[:128] if incoming else uuid.uuid4().hex
        request.request_id = request_id
        token = set_request_id(request_id)
        started = time.monotonic()
        response = None
        try:
            response = self.get_response(request)
            return response
        finally:
            duration = max(time.monotonic() - started, 0)
            status_code = getattr(response, "status_code", 500)
            route = getattr(getattr(request, "resolver_match", None), "route", None) or request.path
            observe_request(
                method=request.method,
                route=route,
                status_code=status_code,
                duration_seconds=duration,
            )
            user = getattr(request, "user", None)
            logger.info(
                "request_completed",
                extra={
                    "method": request.method,
                    "path": request.path,
                    "route": route,
                    "status_code": status_code,
                    "duration_ms": round(duration * 1000, 3),
                    "user_id": getattr(user, "pk", None) if getattr(user, "is_authenticated", False) else None,
                    "remote_addr": request.META.get("REMOTE_ADDR"),
                },
            )
            if response is not None:
                response["X-Request-ID"] = request_id
            reset_request_id(token)


class SecurityHeadersMiddleware:
    """Cabeçalhos adicionais adequados para a API sem depender de proxy específico."""

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        response = self.get_response(request)
        response.setdefault("X-Content-Type-Options", "nosniff")
        response.setdefault("Referrer-Policy", "same-origin")
        response.setdefault("Permissions-Policy", "camera=(), microphone=(), geolocation=()")
        if not settings.DEBUG:
            response.setdefault("Cache-Control", "no-store")
        return response
