from __future__ import annotations

from typing import Any

from django.contrib.auth import get_user_model

from .models import DomainEvent


def append_domain_event(
    *,
    idempotency_key: str,
    event_type: str,
    aggregate_type: str,
    aggregate_id: str | int,
    payload: dict[str, Any] | None = None,
    actor=None,
) -> tuple[DomainEvent, bool]:
    """Cria um evento append-only ou devolve o já existente.

    O retorno segue o padrão ``(evento, criado)`` e permite que os serviços
    sejam repetidos com segurança.
    """

    defaults = {
        "event_type": event_type,
        "aggregate_type": aggregate_type,
        "aggregate_id": str(aggregate_id),
        "payload": payload or {},
        "actor": actor if getattr(actor, "is_authenticated", False) else None,
    }
    return DomainEvent.objects.get_or_create(idempotency_key=idempotency_key, defaults=defaults)
