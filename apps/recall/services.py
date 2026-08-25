from __future__ import annotations

from collections import deque

from django.core.exceptions import ValidationError
from django.db import transaction
from django.utils import timezone

from apps.common.models import DomainEvent
from apps.traceability.models import InventoryLot, SerialComponent, SerialNumber

from .models import RecallAffectedUnit, RecallCase, RecallCriterion


def _event(case, event_type, actor, payload, suffix):
    DomainEvent.objects.get_or_create(
        idempotency_key=f"recall:{case.pk}:{suffix}",
        defaults={
            "event_type": event_type,
            "aggregate_type": "RecallCase",
            "aggregate_id": str(case.pk),
            "payload": payload,
            "actor": actor,
        },
    )


def _serials_for_criterion(criterion):
    qs = SerialNumber.objects.select_related("item", "lot")
    if criterion.criterion_type == RecallCriterion.CriterionType.SERIAL and criterion.serial_id:
        return qs.filter(pk=criterion.serial_id)
    if criterion.criterion_type == RecallCriterion.CriterionType.LOT and criterion.lot_id:
        return qs.filter(lot_id=criterion.lot_id)
    if criterion.criterion_type == RecallCriterion.CriterionType.ITEM and criterion.item_id:
        return qs.filter(item_id=criterion.item_id)
    if criterion.criterion_type == RecallCriterion.CriterionType.SUPPLIER and criterion.supplier_id:
        return qs.filter(lot__supplier_id=criterion.supplier_id)
    if criterion.criterion_type == RecallCriterion.CriterionType.PRODUCTION_PERIOD:
        if criterion.date_from:
            qs = qs.filter(manufactured_at__gte=criterion.date_from)
        if criterion.date_to:
            qs = qs.filter(manufactured_at__lte=criterion.date_to)
        if criterion.item_id:
            qs = qs.filter(item_id=criterion.item_id)
        return qs
    if criterion.criterion_type == RecallCriterion.CriterionType.SOURCE_REFERENCE:
        return qs.filter(source_type=criterion.reference_type, source_id=criterion.reference_id)
    return qs.none()


def _lots_for_criterion(criterion):
    qs = InventoryLot.objects.select_related("item")
    if criterion.criterion_type == RecallCriterion.CriterionType.LOT and criterion.lot_id:
        return qs.filter(pk=criterion.lot_id)
    if criterion.criterion_type == RecallCriterion.CriterionType.ITEM and criterion.item_id:
        return qs.filter(item_id=criterion.item_id)
    if criterion.criterion_type == RecallCriterion.CriterionType.SUPPLIER and criterion.supplier_id:
        return qs.filter(supplier_id=criterion.supplier_id)
    if criterion.criterion_type == RecallCriterion.CriterionType.SOURCE_REFERENCE:
        return qs.filter(source_type=criterion.reference_type, source_id=criterion.reference_id)
    return qs.none()


@transaction.atomic
def analyze_recall(*, case: RecallCase, actor=None, include_components=True, include_where_used=True):
    case = RecallCase.objects.select_for_update().get(pk=case.pk)
    if case.status not in {RecallCase.Status.DRAFT, RecallCase.Status.INVESTIGATING}:
        raise ValidationError("A análise só pode ser executada em recall em rascunho ou investigação.")

    case.status = RecallCase.Status.INVESTIGATING
    case.save(update_fields=["status", "updated_at"])
    case.affected_units.all().delete()

    direct_serial_ids = set()
    for criterion in case.criteria.select_related("serial", "lot", "item", "supplier"):
        for lot in _lots_for_criterion(criterion).iterator():
            RecallAffectedUnit.objects.get_or_create(
                recall_case=case, lot=lot, serial=None,
                defaults={"item": lot.item, "source": RecallAffectedUnit.Source.DIRECT, "depth": 0},
            )
        for serial in _serials_for_criterion(criterion).iterator():
            direct_serial_ids.add(serial.pk)
            RecallAffectedUnit.objects.get_or_create(
                recall_case=case, serial=serial,
                defaults={
                    "item": serial.item, "lot": serial.lot,
                    "source": RecallAffectedUnit.Source.DIRECT, "depth": 0,
                },
            )

    queue = deque((serial_id, 0) for serial_id in direct_serial_ids)
    visited = set(direct_serial_ids)
    while queue:
        serial_id, depth = queue.popleft()
        neighbors = []
        if include_where_used:
            neighbors.extend(
                (row.parent_serial_id, RecallAffectedUnit.Source.GENEALOGY_UP)
                for row in SerialComponent.objects.filter(
                    component_serial_id=serial_id, removed_at__isnull=True
                )
            )
        if include_components:
            neighbors.extend(
                (row.component_serial_id, RecallAffectedUnit.Source.GENEALOGY_DOWN)
                for row in SerialComponent.objects.filter(
                    parent_serial_id=serial_id, removed_at__isnull=True
                )
            )
        for neighbor_id, source in neighbors:
            if neighbor_id in visited:
                continue
            visited.add(neighbor_id)
            neighbor = SerialNumber.objects.select_related("item", "lot").get(pk=neighbor_id)
            RecallAffectedUnit.objects.get_or_create(
                recall_case=case, serial=neighbor,
                defaults={
                    "item": neighbor.item, "lot": neighbor.lot,
                    "source": source, "depth": depth + 1,
                },
            )
            queue.append((neighbor_id, depth + 1))

    summary = {
        "affected_units": case.affected_units.count(),
        "serials": case.affected_units.exclude(serial__isnull=True).count(),
        "lots": case.affected_units.filter(serial__isnull=True).exclude(lot__isnull=True).count(),
    }
    _event(case, "recall.analyzed", actor, summary, f"analyzed:{case.updated_at.isoformat()}")
    return summary


@transaction.atomic
def approve_recall(*, case: RecallCase, actor):
    case = RecallCase.objects.select_for_update().get(pk=case.pk)
    if case.status != RecallCase.Status.INVESTIGATING:
        raise ValidationError("Somente recalls em investigação podem ser aprovados.")
    if not case.affected_units.exists():
        raise ValidationError("Execute a análise antes da aprovação.")
    case.status = RecallCase.Status.APPROVED
    case.approved_by = actor
    case.approved_at = timezone.now()
    case.save(update_fields=["status", "approved_by", "approved_at", "updated_at"])
    _event(case, "recall.approved", actor, {"number": case.number}, "approved")
    return case


@transaction.atomic
def execute_recall(*, case: RecallCase, actor=None):
    case = RecallCase.objects.select_for_update().get(pk=case.pk)
    if case.status not in {RecallCase.Status.APPROVED, RecallCase.Status.EXECUTING}:
        raise ValidationError("O recall deve estar aprovado antes da execução.")
    case.status = RecallCase.Status.EXECUTING
    case.save(update_fields=["status", "updated_at"])

    serial_ids = list(case.affected_units.exclude(serial__isnull=True).values_list("serial_id", flat=True))
    lot_ids = list(case.affected_units.exclude(lot__isnull=True).values_list("lot_id", flat=True).distinct())
    SerialNumber.objects.filter(pk__in=serial_ids).exclude(status=SerialNumber.Status.SCRAPPED).update(
        status=SerialNumber.Status.BLOCKED
    )
    InventoryLot.objects.filter(pk__in=lot_ids).exclude(
        status__in=[InventoryLot.Status.CONSUMED, InventoryLot.Status.REJECTED]
    ).update(status=InventoryLot.Status.BLOCKED)
    now = timezone.now()
    case.affected_units.filter(blocked_at__isnull=True).update(
        blocked_at=now, disposition=RecallAffectedUnit.Disposition.BLOCKED
    )
    _event(
        case, "recall.executed", actor,
        {"serials_blocked": len(serial_ids), "lots_blocked": len(lot_ids)}, "executed",
    )
    return {"serials_blocked": len(serial_ids), "lots_blocked": len(lot_ids)}


@transaction.atomic
def complete_recall(*, case: RecallCase, actor=None):
    case = RecallCase.objects.select_for_update().get(pk=case.pk)
    if case.status != RecallCase.Status.EXECUTING:
        raise ValidationError("Somente recall em execução pode ser concluído.")
    pending = case.affected_units.filter(
        disposition__in=[RecallAffectedUnit.Disposition.PENDING, RecallAffectedUnit.Disposition.BLOCKED]
    ).count()
    if pending:
        raise ValidationError(f"Existem {pending} unidades sem disposição final.")
    case.status = RecallCase.Status.COMPLETED
    case.completed_at = timezone.now()
    case.save(update_fields=["status", "completed_at", "updated_at"])
    _event(case, "recall.completed", actor, {"number": case.number}, "completed")
    return case
