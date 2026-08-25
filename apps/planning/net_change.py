from __future__ import annotations

from collections import defaultdict, deque
from datetime import date

from django.core.exceptions import ValidationError
from django.db import transaction
from django.utils import timezone

from apps.common.models import Plant
from apps.masterdata.models import BOMLine, Item

from .models import PlanningChange, PlanningRun
from .services import execute_planning_run


def enqueue_planning_change(
    *,
    plant: Plant,
    item: Item | None,
    change_type: str,
    source_type: str,
    source_id: str | int,
    idempotency_key: str,
    payload: dict | None = None,
) -> tuple[PlanningChange, bool]:
    return PlanningChange.objects.get_or_create(
        idempotency_key=idempotency_key,
        defaults={
            "plant": plant,
            "item": item,
            "change_type": change_type,
            "source_type": source_type,
            "source_id": str(source_id),
            "payload": payload or {},
        },
    )


def affected_item_scope(item_ids: set[int]) -> set[int]:
    """Expande alterações para ancestrais e toda a rede dependente afetada."""

    if not item_ids:
        return set(Item.objects.filter(is_active=True).values_list("id", flat=True))

    lines = list(BOMLine.objects.filter(is_active=True).values_list("parent_id", "component_id"))
    parents_by_component: dict[int, set[int]] = defaultdict(set)
    children_by_parent: dict[int, set[int]] = defaultdict(set)
    for parent_id, component_id in lines:
        parents_by_component[component_id].add(parent_id)
        children_by_parent[parent_id].add(component_id)

    ancestors = set(item_ids)
    queue = deque(item_ids)
    while queue:
        child = queue.popleft()
        for parent in parents_by_component.get(child, set()):
            if parent not in ancestors:
                ancestors.add(parent)
                queue.append(parent)

    scope = set(ancestors)
    queue = deque(ancestors)
    while queue:
        parent = queue.popleft()
        for child in children_by_parent.get(parent, set()):
            if child not in scope:
                scope.add(child)
                queue.append(child)
    return scope


@transaction.atomic
def execute_net_change_run(
    *,
    plant: Plant,
    horizon_start: date,
    horizon_end: date,
    name: str = "MRP net-change",
    parameters: dict | None = None,
) -> PlanningRun:
    if horizon_end < horizon_start:
        raise ValidationError("O fim do horizonte deve ser posterior ao início.")

    changes = list(
        PlanningChange.objects.select_for_update(of=("self",))
        .filter(plant=plant, status=PlanningChange.Status.PENDING)
        .select_related("item")
        .order_by("created_at", "id")
    )
    if not changes:
        raise ValidationError("Não há alterações pendentes para a planta.")

    changed_ids = {change.item_id for change in changes if change.item_id}
    full_replan = any(change.item_id is None for change in changes)
    scope_ids = affected_item_scope(set() if full_replan else changed_ids)

    run_parameters = dict(parameters or {})
    run_parameters.update(
        {
            "mode": "NET_CHANGE",
            "scope_item_ids": sorted(scope_ids),
            "change_event_ids": [change.pk for change in changes],
        }
    )
    run = PlanningRun.objects.create(
        name=name,
        plant=plant,
        horizon_start=horizon_start,
        horizon_end=horizon_end,
        parameters=run_parameters,
    )

    # O cálculo possui sua própria transação. Uma falha mantém eventos pendentes.
    execute_planning_run(run)

    now = timezone.now()
    for change in changes:
        change.status = PlanningChange.Status.PROCESSED
        change.processed_at = now
        change.planning_run = run
    PlanningChange.objects.bulk_update(changes, ["status", "processed_at", "planning_run"])
    return run
