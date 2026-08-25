from __future__ import annotations

from django.conf import settings
from django.core.checks import Error, Warning, register


@register("mrp")
def security_configuration_check(app_configs, **kwargs):
    messages = []
    if settings.SECRET_KEY == "dev-only-secret-key":
        messages.append(
            Warning(
                "DJANGO_SECRET_KEY ainda usa o valor padrão de desenvolvimento.",
                hint="Defina uma chave longa e aleatória no ambiente.",
                id="mrp.W001",
            )
        )
    if not settings.DEBUG and "*" in settings.ALLOWED_HOSTS:
        messages.append(
            Error(
                "ALLOWED_HOSTS não deve conter '*' em produção.",
                id="mrp.E001",
            )
        )
    if settings.SECURE_HSTS_SECONDS and not settings.SECURE_SSL_REDIRECT:
        messages.append(
            Warning(
                "HSTS está ativo, mas SECURE_SSL_REDIRECT está desabilitado.",
                id="mrp.W002",
            )
        )
    return messages
