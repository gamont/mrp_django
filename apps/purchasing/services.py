from __future__ import annotations

from datetime import datetime
from decimal import Decimal

from django.core.exceptions import ValidationError
from django.db import models, transaction
from django.utils import timezone

from apps.common.services import append_domain_event
from apps.inventory.models import InventoryTransaction, Location
from apps.inventory.services import post_inventory_transaction

from .models import GoodsReceipt, PurchaseOrder, PurchaseOrderLine


def _validate_receipt_replay(
    *,
    existing: GoodsReceipt,
    line: PurchaseOrderLine,
    quantity: Decimal,
    destination_location: Location,
    receipt_number: str,
) -> None:
    mismatches = []
    if existing.purchase_order_line_id != line.pk:
        mismatches.append("purchase_order_line")
    if existing.quantity != quantity:
        mismatches.append("quantity")
    if existing.destination_location_id != destination_location.pk:
        mismatches.append("destination_location")
    if existing.receipt_number != receipt_number:
        mismatches.append("receipt_number")
    if mismatches:
        raise ValidationError(
            {
                "idempotency_key": (
                    "A chave já foi utilizada por outro recebimento. "
                    f"Campos divergentes: {', '.join(mismatches)}."
                )
            }
        )


@transaction.atomic
def receive_purchase_order_line(
    *,
    line: PurchaseOrderLine,
    quantity: Decimal,
    destination_location: Location,
    receipt_number: str,
    idempotency_key: str,
    received_at: datetime | None = None,
    lot_number: str = "",
    notes: str = "",
    actor=None,
) -> tuple[GoodsReceipt, bool]:
    """Recebe uma linha de OC, movimenta estoque e fecha a OC quando aplicável.

    A operação inteira é atômica e idempotente. Repetir a mesma chave devolve
    o mesmo recebimento sem duplicar saldo, quantidade recebida ou evento.
    """

    if not idempotency_key:
        raise ValidationError({"idempotency_key": "Informe uma chave de idempotência."})

    existing = GoodsReceipt.objects.select_related(
        "purchase_order_line", "inventory_transaction"
    ).filter(idempotency_key=idempotency_key).first()
    if existing:
        _validate_receipt_replay(
            existing=existing,
            line=line,
            quantity=quantity,
            destination_location=destination_location,
            receipt_number=receipt_number,
        )
        return existing, False

    locked_line = (
        PurchaseOrderLine.objects.select_for_update()
        .select_related("purchase_order", "item", "purchase_order__plant")
        .get(pk=line.pk)
    )
    order = PurchaseOrder.objects.select_for_update().get(pk=locked_line.purchase_order_id)

    # Revalida depois do lock: uma chamada concorrente pode ter concluído o
    # recebimento enquanto esta transação aguardava a linha/OC.
    existing = GoodsReceipt.objects.select_related(
        "purchase_order_line", "inventory_transaction"
    ).filter(idempotency_key=idempotency_key).first()
    if existing:
        _validate_receipt_replay(
            existing=existing,
            line=locked_line,
            quantity=quantity,
            destination_location=destination_location,
            receipt_number=receipt_number,
        )
        return existing, False

    if order.status not in {PurchaseOrder.Status.RELEASED, PurchaseOrder.Status.PARTIAL}:
        raise ValidationError("Somente OCs liberadas ou parciais podem ser recebidas.")
    if destination_location.warehouse.plant_id != order.plant_id:
        raise ValidationError("O local de destino deve pertencer à mesma planta da OC.")
    if quantity <= 0:
        raise ValidationError({"quantity": "A quantidade recebida deve ser positiva."})

    open_quantity = locked_line.quantity - locked_line.received_quantity
    if quantity > open_quantity:
        raise ValidationError(
            {"quantity": f"Quantidade excede o saldo aberto da linha ({open_quantity})."}
        )

    tx = InventoryTransaction(
        transaction_type=InventoryTransaction.TransactionType.PURCHASE_RECEIPT,
        item=locked_line.item,
        to_location=destination_location,
        quantity=quantity,
        reference_type="PURCHASE_ORDER_LINE",
        reference_id=str(locked_line.pk),
        posted_by=actor if getattr(actor, "is_authenticated", False) else None,
        notes=f"Recebimento {receipt_number}. {notes}".strip(),
        idempotency_key=f"purchase-receipt:{idempotency_key}",
    )
    tx = post_inventory_transaction(tx)

    receipt = GoodsReceipt.objects.create(
        purchase_order_line=locked_line,
        receipt_number=receipt_number,
        idempotency_key=idempotency_key,
        received_at=received_at or timezone.now(),
        quantity=quantity,
        destination_location=destination_location,
        inventory_transaction=tx,
        lot_number=lot_number,
        notes=notes,
    )

    locked_line.received_quantity += quantity
    locked_line.save(update_fields=["received_quantity", "updated_at"])

    open_lines = order.lines.filter(received_quantity__lt=models.F("quantity"))
    if open_lines.exists():
        order.status = PurchaseOrder.Status.PARTIAL
    else:
        order.status = PurchaseOrder.Status.COMPLETED
    order.save(update_fields=["status", "updated_at"])

    append_domain_event(
        idempotency_key=f"event:purchase-receipt:{idempotency_key}",
        event_type="PURCHASE_RECEIPT_POSTED",
        aggregate_type="PURCHASE_ORDER",
        aggregate_id=order.pk,
        payload={
            "purchase_order": order.number,
            "line_id": locked_line.pk,
            "item": locked_line.item.code,
            "quantity": str(quantity),
            "destination_location": destination_location.code,
            "receipt_number": receipt_number,
            "purchase_order_status": order.status,
        },
        actor=actor,
    )
    return receipt, True
