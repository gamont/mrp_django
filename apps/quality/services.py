from __future__ import annotations

from decimal import Decimal

from django.core.exceptions import ValidationError
from django.db import transaction
from django.utils import timezone

from apps.common.models import DomainEvent
from apps.traceability.models import InventoryLot

from .models import Disposition, InspectionOrder, InspectionResult, NonConformance


def _event(*, event_type, aggregate, actor=None, payload=None):
    return DomainEvent.objects.create(
        event_type=event_type,
        aggregate_type=aggregate.__class__.__name__,
        aggregate_id=str(aggregate.pk),
        actor=actor,
        payload=payload or {},
        idempotency_key=f"{event_type}:{aggregate.pk}:{timezone.now().isoformat()}",
    )


@transaction.atomic
def start_inspection(*, order: InspectionOrder, user=None):
    order = InspectionOrder.objects.select_for_update(of=("self",)).select_related("lot").get(pk=order.pk)
    if order.status != InspectionOrder.Status.OPEN:
        raise ValidationError("Somente inspeções abertas podem ser iniciadas.")
    order.status = InspectionOrder.Status.IN_PROGRESS
    order.inspector = user
    order.save(update_fields=["status", "inspector", "updated_at"])
    if order.lot_id:
        InventoryLot.objects.filter(pk=order.lot_id).update(status=InventoryLot.Status.INSPECTION)
    _event(event_type="quality.inspection.started", aggregate=order, actor=user)
    return order


@transaction.atomic
def record_result(*, order: InspectionOrder, characteristic, sample_number=1, numeric_value=None, boolean_value=None, text_value="", user=None, notes=""):
    order = InspectionOrder.objects.select_for_update().get(pk=order.pk)
    if order.status not in {InspectionOrder.Status.OPEN, InspectionOrder.Status.IN_PROGRESS}:
        raise ValidationError("A inspeção não aceita novos resultados.")
    if characteristic.plan_id != order.plan_id:
        raise ValidationError("A característica não pertence ao plano da inspeção.")
    conforming = True
    if characteristic.data_type == characteristic.DataType.NUMERIC:
        if numeric_value is None:
            raise ValidationError("Informe o valor numérico.")
        value = Decimal(str(numeric_value))
        if characteristic.lower_limit is not None and value < characteristic.lower_limit:
            conforming = False
        if characteristic.upper_limit is not None and value > characteristic.upper_limit:
            conforming = False
    elif characteristic.data_type == characteristic.DataType.BOOLEAN:
        if boolean_value is None:
            raise ValidationError("Informe o resultado conforme/não conforme.")
        conforming = bool(boolean_value)
    result, _ = InspectionResult.objects.update_or_create(
        order=order, characteristic=characteristic, sample_number=sample_number,
        defaults={"numeric_value": numeric_value, "boolean_value": boolean_value, "text_value": text_value, "is_conforming": conforming, "measured_by": user, "notes": notes},
    )
    if order.status == InspectionOrder.Status.OPEN:
        order.status = InspectionOrder.Status.IN_PROGRESS
        order.inspector = user
        order.save(update_fields=["status", "inspector", "updated_at"])
    return result


@transaction.atomic
def complete_inspection(*, order: InspectionOrder, quantity_approved, quantity_rejected, user=None, notes=""):
    order = InspectionOrder.objects.select_for_update(of=("self",)).select_related("lot").get(pk=order.pk)
    approved = Decimal(str(quantity_approved)); rejected = Decimal(str(quantity_rejected))
    if approved < 0 or rejected < 0 or approved + rejected > order.quantity_received:
        raise ValidationError("Quantidades de aprovação/rejeição são inválidas.")
    missing = order.plan.characteristics.filter(is_mandatory=True).exclude(results__order=order).exists()
    if missing:
        raise ValidationError("Existem características obrigatórias sem resultado.")
    order.quantity_inspected = approved + rejected
    order.quantity_approved = approved
    order.quantity_rejected = rejected
    order.completed_at = timezone.now()
    order.inspector = user
    order.notes = notes or order.notes
    if rejected == 0:
        order.status = InspectionOrder.Status.APPROVED
    elif approved == 0:
        order.status = InspectionOrder.Status.REJECTED
    else:
        order.status = InspectionOrder.Status.PARTIAL
    order.save()
    if order.lot_id:
        lot = InventoryLot.objects.select_for_update().get(pk=order.lot_id)
        lot.status = InventoryLot.Status.AVAILABLE if rejected == 0 else (InventoryLot.Status.REJECTED if approved == 0 else InventoryLot.Status.QUARANTINE)
        lot.save(update_fields=["status", "updated_at"])
    if rejected > 0:
        number = f"NC-{timezone.now():%Y%m%d}-{order.pk:06d}"
        NonConformance.objects.get_or_create(number=number, defaults={
            "inspection_order": order, "plant": order.plant, "item": order.item, "lot": order.lot,
            "serial": order.serial, "supplier": order.supplier, "description": "Reprovação gerada pela inspeção",
            "quantity_affected": rejected, "opened_by": user,
        })
    _event(event_type="quality.inspection.completed", aggregate=order, actor=user, payload={"approved": str(approved), "rejected": str(rejected), "status": order.status})
    return order


@transaction.atomic
def apply_disposition(*, nonconformance: NonConformance, decision, quantity, instructions="", user=None):
    ncr = NonConformance.objects.select_for_update(of=("self",)).select_related("lot").get(pk=nonconformance.pk)
    qty = Decimal(str(quantity))
    disposed = sum((d.quantity for d in ncr.dispositions.all()), Decimal("0"))
    if qty <= 0 or disposed + qty > ncr.quantity_affected:
        raise ValidationError("Quantidade de disposição excede a quantidade afetada.")
    row = Disposition.objects.create(nonconformance=ncr, decision=decision, quantity=qty, instructions=instructions, approved_by=user)
    if disposed + qty == ncr.quantity_affected:
        ncr.status = NonConformance.Status.DISPOSITIONED
        ncr.save(update_fields=["status", "updated_at"])
    if ncr.lot_id:
        lot = InventoryLot.objects.select_for_update().get(pk=ncr.lot_id)
        if decision == Disposition.Decision.USE_AS_IS and disposed + qty == ncr.quantity_affected:
            lot.status = InventoryLot.Status.AVAILABLE
        elif decision == Disposition.Decision.SCRAP and disposed + qty == ncr.quantity_affected:
            lot.status = InventoryLot.Status.REJECTED
        else:
            lot.status = InventoryLot.Status.QUARANTINE
        lot.save(update_fields=["status", "updated_at"])
    _event(event_type="quality.nonconformance.dispositioned", aggregate=ncr, actor=user, payload={"decision": decision, "quantity": str(qty)})
    return row
