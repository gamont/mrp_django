from __future__ import annotations

from collections.abc import Iterable

from django.contrib.auth.models import Group, Permission
from django.contrib.contenttypes.models import ContentType
from django.db import transaction

ROLE_ADMIN = "MRP Administradores"
ROLE_PLANNER = "MRP Planejadores"
ROLE_BUYER = "MRP Compradores"
ROLE_PRODUCTION = "MRP Produção"
ROLE_WAREHOUSE = "MRP Almoxarifado"
ROLE_SALES = "MRP Vendas"
ROLE_AUDITOR = "MRP Auditores"
ROLE_MAINTENANCE = "MRP Manutenção"

MRP_APP_LABELS = {
    "common",
    "masterdata",
    "inventory",
    "demand",
    "planning",
    "production",
    "purchasing",
    "engineering",
    "traceability",
    "quality",
    "recall",
    "costing",
    "shopfloor",
    "maintenance",
    "integrated_scheduling",
}

# Todos os papéis recebem as permissões view dos módulos MRP. As regras abaixo
# adicionam somente os comandos próprios de cada função; delete fica reservado
# ao administrador para reduzir exclusões acidentais em dados transacionais.
WRITE_RULES: dict[str, dict[str, set[str] | str]] = {
    ROLE_PLANNER: {
        "common": {"shopcalendarday"},
        "masterdata": "*",
        "demand": "*",
        "planning": "*",
        "engineering": "*",
        "integrated_scheduling": "*",
    },
    ROLE_BUYER: {
        "masterdata": {"supplier", "itemsupplier"},
        "purchasing": {"purchaseorder", "purchaseorderline", "goodsreceipt"},
    },
    ROLE_PRODUCTION: {
        "production": "*",
        "traceability": {"serialnumber", "serialtransaction", "serialcomponent"},
        "shopfloor": "*",
    },
    ROLE_WAREHOUSE: {
        "inventory": {"inventorytransaction"},
        "traceability": "*",
        # A action receive em PurchaseOrderLine exige add_goodsreceipt.
        "purchasing": {"goodsreceipt"},
    },
    ROLE_SALES: {
        "demand": {"forecast", "salesorder", "salesorderline", "masterproductionschedule"},
    },
    ROLE_MAINTENANCE: {
        "maintenance": "*",
        "inventory": {"inventorytransaction"},
        "shopfloor": {"machine", "downtimeevent", "downtimereason"},
        "integrated_scheduling": "*",
    },
    ROLE_AUDITOR: {},
}


def _model_allowed(model_name: str, configured: set[str] | str | None) -> bool:
    return configured == "*" or (isinstance(configured, set) and model_name in configured)


@transaction.atomic
def sync_default_roles() -> dict[str, int]:
    """Cria/atualiza grupos padrão e devolve a quantidade de permissões por grupo."""

    content_types = list(ContentType.objects.filter(app_label__in=MRP_APP_LABELS))
    permissions = list(
        Permission.objects.filter(content_type__in=content_types).select_related("content_type")
    )
    result: dict[str, int] = {}

    all_roles = [
        ROLE_ADMIN,
        ROLE_PLANNER,
        ROLE_BUYER,
        ROLE_PRODUCTION,
        ROLE_WAREHOUSE,
        ROLE_SALES,
        ROLE_MAINTENANCE,
        ROLE_AUDITOR,
    ]
    for role_name in all_roles:
        group, _ = Group.objects.get_or_create(name=role_name)
        selected: list[Permission] = []
        for permission in permissions:
            action, _, model_name = permission.codename.partition("_")
            app_label = permission.content_type.app_label
            if role_name == ROLE_ADMIN:
                selected.append(permission)
                continue
            if action == "view":
                selected.append(permission)
                continue
            if (
                role_name == ROLE_PRODUCTION
                and app_label == "shopfloor"
                and permission.codename == "use_shopfloor_terminal"
            ):
                selected.append(permission)
                continue
            configured = WRITE_RULES.get(role_name, {}).get(app_label)
            if action in {"add", "change"} and _model_allowed(model_name, configured):
                selected.append(permission)
        group.permissions.set(selected)
        result[role_name] = len(selected)
    return result


def role_names() -> Iterable[str]:
    return (
        ROLE_ADMIN,
        ROLE_PLANNER,
        ROLE_BUYER,
        ROLE_PRODUCTION,
        ROLE_WAREHOUSE,
        ROLE_SALES,
        ROLE_MAINTENANCE,
        ROLE_AUDITOR,
    )
