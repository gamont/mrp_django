from __future__ import annotations

from decimal import Decimal

from django.core.exceptions import ValidationError
from django.db import IntegrityError, transaction
from django.utils import timezone

from apps.common.services import append_domain_event
from .models import (
    InventoryLot,
    LotBalance,
    LotReservation,
    LotTransaction,
    SerialComponent,
    SerialNumber,
    SerialTransaction,
)


def _positive(quantity: Decimal) -> Decimal:
    quantity = Decimal(quantity)
    if quantity <= 0:
        raise ValidationError({"quantity": "A quantidade deve ser positiva."})
    return quantity


@transaction.atomic
def post_lot_transaction(*, transaction_type, lot, quantity, idempotency_key, from_location=None,
                         to_location=None, reference_type="", reference_id="", user=None, notes=""):
    quantity = _positive(quantity)
    existing = LotTransaction.objects.filter(idempotency_key=idempotency_key).first()
    if existing:
        expected = (existing.lot_id, existing.transaction_type, existing.quantity,
                    existing.from_location_id, existing.to_location_id)
        supplied = (lot.id, transaction_type, quantity,
                    getattr(from_location, "id", None), getattr(to_location, "id", None))
        if expected != supplied:
            raise ValidationError({"idempotency_key": "Chave já usada com dados diferentes."})
        return existing

    if lot.status not in {InventoryLot.Status.AVAILABLE, InventoryLot.Status.QUARANTINE,
                          InventoryLot.Status.INSPECTION} and transaction_type in {
        LotTransaction.TransactionType.ISSUE, LotTransaction.TransactionType.TRANSFER
    }:
        raise ValidationError({"lot": f"Lote com status {lot.status} não pode ser movimentado."})

    location_ids = sorted({x.id for x in (from_location, to_location) if x})
    balances = {
        row.location_id: row
        for row in LotBalance.objects.select_for_update().filter(lot=lot, location_id__in=location_ids)
    }
    for location in (from_location, to_location):
        if location and location.id not in balances:
            balances[location.id], _ = LotBalance.objects.select_for_update().get_or_create(
                lot=lot, location=location, defaults={"on_hand": 0, "allocated": 0}
            )

    if transaction_type in {LotTransaction.TransactionType.ISSUE, LotTransaction.TransactionType.TRANSFER}:
        if not from_location:
            raise ValidationError({"from_location": "Origem obrigatória."})
        source = balances[from_location.id]
        if source.available < quantity:
            raise ValidationError({"quantity": "Saldo disponível do lote insuficiente."})
        source.on_hand -= quantity
        source.save(update_fields=["on_hand", "updated_at"])

    if transaction_type in {LotTransaction.TransactionType.RECEIPT, LotTransaction.TransactionType.TRANSFER}:
        if not to_location:
            raise ValidationError({"to_location": "Destino obrigatório."})
        target = balances[to_location.id]
        target.on_hand += quantity
        target.save(update_fields=["on_hand", "updated_at"])

    try:
        row = LotTransaction.objects.create(
            transaction_type=transaction_type, lot=lot, from_location=from_location,
            to_location=to_location, quantity=quantity, reference_type=reference_type,
            reference_id=reference_id, posted_by=user, idempotency_key=idempotency_key, notes=notes,
        )
    except IntegrityError:
        return LotTransaction.objects.get(idempotency_key=idempotency_key)

    append_domain_event(
        event_type="traceability.lot_transaction_posted", aggregate_type="InventoryLot",
        aggregate_id=str(lot.id), actor=user,
        payload={"lot_number": lot.lot_number, "item": lot.item.code, "type": transaction_type,
                 "quantity": str(quantity), "reference_type": reference_type, "reference_id": reference_id},
        idempotency_key=f"lot-event:{idempotency_key}",
    )
    return row


@transaction.atomic
def reserve_lot(*, lot, location, quantity, demand_type, demand_id, required_date):
    quantity = _positive(quantity)
    if lot.status != InventoryLot.Status.AVAILABLE:
        raise ValidationError({"lot": "Somente lotes disponíveis podem ser reservados."})
    balance = LotBalance.objects.select_for_update().get(lot=lot, location=location)
    if balance.available < quantity:
        raise ValidationError({"quantity": "Saldo disponível do lote insuficiente."})
    balance.allocated += quantity
    balance.save(update_fields=["allocated", "updated_at"])
    return LotReservation.objects.create(
        lot=lot, location=location, quantity=quantity, demand_type=demand_type,
        demand_id=demand_id, required_date=required_date,
    )


@transaction.atomic
def change_lot_status(*, lot, status, user=None, reason=""):
    lot = InventoryLot.objects.select_for_update().get(pk=lot.pk)
    previous = lot.status
    lot.status = status
    lot.save(update_fields=["status", "updated_at"])
    append_domain_event(
        event_type="traceability.lot_status_changed", aggregate_type="InventoryLot",
        aggregate_id=str(lot.id), actor=user,
        payload={"from": previous, "to": status, "reason": reason},
        idempotency_key=f"lot-status:{lot.id}:{previous}:{status}:{timezone.now().isoformat()}",
    )
    return lot


@transaction.atomic
def post_serial_transaction(*, serial, transaction_type, idempotency_key, from_location=None,
                            to_location=None, reference_type="", reference_id="", user=None, notes=""):
    existing = SerialTransaction.objects.filter(idempotency_key=idempotency_key).first()
    if existing:
        return existing
    serial = SerialNumber.objects.select_for_update().get(pk=serial.pk)
    if transaction_type == SerialTransaction.TransactionType.MOVE and not to_location:
        raise ValidationError({"to_location": "Destino obrigatório."})
    status_map = {
        SerialTransaction.TransactionType.CREATE: SerialNumber.Status.AVAILABLE,
        SerialTransaction.TransactionType.RESERVE: SerialNumber.Status.RESERVED,
        SerialTransaction.TransactionType.ISSUE: SerialNumber.Status.IN_PRODUCTION,
        SerialTransaction.TransactionType.INSTALL: SerialNumber.Status.INSTALLED,
        SerialTransaction.TransactionType.SHIP: SerialNumber.Status.SHIPPED,
        SerialTransaction.TransactionType.BLOCK: SerialNumber.Status.BLOCKED,
        SerialTransaction.TransactionType.SCRAP: SerialNumber.Status.SCRAPPED,
    }
    if to_location:
        serial.current_location = to_location
    if transaction_type in status_map:
        serial.status = status_map[transaction_type]
    serial.save(update_fields=["current_location", "status", "updated_at"])
    row = SerialTransaction.objects.create(
        serial=serial, transaction_type=transaction_type, from_location=from_location,
        to_location=to_location, reference_type=reference_type, reference_id=reference_id,
        posted_by=user, idempotency_key=idempotency_key, notes=notes,
    )
    append_domain_event(
        event_type="traceability.serial_transaction_posted", aggregate_type="SerialNumber",
        aggregate_id=str(serial.id), actor=user,
        payload={"serial_number": serial.serial_number, "type": transaction_type,
                 "reference_type": reference_type, "reference_id": reference_id},
        idempotency_key=f"serial-event:{idempotency_key}",
    )
    return row


@transaction.atomic
def install_component(*, parent_serial, component_serial, installed_at=None, work_order_id="",
                      operation_sequence=None, user=None, notes=""):
    parent_serial = SerialNumber.objects.select_for_update().get(pk=parent_serial.pk)
    component_serial = SerialNumber.objects.select_for_update().get(pk=component_serial.pk)
    if parent_serial.pk == component_serial.pk:
        raise ValidationError("Uma série não pode conter a si própria.")
    if SerialComponent.objects.filter(component_serial=component_serial, removed_at__isnull=True).exists():
        raise ValidationError({"component_serial": "Componente já está instalado em outro produto."})
    link = SerialComponent.objects.create(
        parent_serial=parent_serial, component_serial=component_serial,
        installed_at=installed_at or timezone.now(), work_order_id=work_order_id,
        operation_sequence=operation_sequence, notes=notes,
    )
    component_serial.status = SerialNumber.Status.INSTALLED
    component_serial.save(update_fields=["status", "updated_at"])
    append_domain_event(
        event_type="traceability.serial_component_installed", aggregate_type="SerialNumber",
        aggregate_id=str(parent_serial.id), actor=user,
        payload={"parent": parent_serial.serial_number, "component": component_serial.serial_number,
                 "work_order_id": work_order_id},
        idempotency_key=f"serial-install:{link.id}",
    )
    return link


def serial_genealogy(serial: SerialNumber) -> dict:
    def children(node, visited):
        if node.id in visited:
            return {"id": node.id, "serial_number": node.serial_number, "cycle": True, "components": []}
        next_visited = visited | {node.id}
        rows = node.installed_components.filter(removed_at__isnull=True).select_related(
            "component_serial", "component_serial__item", "component_serial__lot"
        )
        return {
            "id": node.id,
            "item": node.item.code,
            "serial_number": node.serial_number,
            "lot_number": node.lot.lot_number if node.lot_id else None,
            "status": node.status,
            "components": [children(row.component_serial, next_visited) for row in rows],
        }
    return children(serial, set())
