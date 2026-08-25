from __future__ import annotations

from decimal import Decimal

from django.core.exceptions import ValidationError
from django.db import transaction
from django.db.models import Q
from django.utils import timezone

from apps.common.services import append_domain_event
from apps.inventory.models import InventoryTransaction, Reservation, StockBalance
from apps.inventory.services import post_inventory_transaction
from apps.masterdata.models import BOMLine, ItemSubstitute

from .models import (
    ProductionReport,
    WorkOrder,
    WorkOrderCompletion,
    WorkOrderMaterial,
    WorkOrderOperation,
)

ZERO = Decimal("0")


@transaction.atomic
def materialize_work_order(work_order: WorkOrder) -> WorkOrder:
    if work_order.materials.exists() or work_order.operations.exists():
        return work_order

    bom_lines = BOMLine.objects.filter(parent=work_order.item, is_active=True).select_related("component")
    for line in bom_lines:
        WorkOrderMaterial.objects.create(
            work_order=work_order,
            item=line.component,
            bom_line=line,
            required_quantity=work_order.quantity * line.quantity_with_scrap(),
            required_date=work_order.release_date,
        )

    routing = work_order.routing or work_order.item.routings.filter(
        plant=work_order.plant, is_primary=True, is_active=True
    ).first()
    if routing:
        work_order.routing = routing
        work_order.save(update_fields=["routing", "updated_at"])
        for op in routing.operations.select_related("work_center").all():
            WorkOrderOperation.objects.create(
                work_order=work_order,
                sequence=op.sequence,
                description=op.description,
                work_center=op.work_center,
                setup_hours=op.setup_hours,
                run_hours=op.run_hours_per_unit * work_order.quantity,
            )
    return work_order


def _reserve_available(*, item, requested_item, requested_qty, actual_qty, work_order, conversion):
    """Reserva até ``actual_qty`` e devolve o equivalente principal reservado."""

    if requested_qty <= ZERO or actual_qty <= ZERO:
        return ZERO

    remaining_actual = actual_qty
    reserved_equivalent = ZERO
    balances = list(
        StockBalance.objects.select_for_update()
        .filter(item=item, location__warehouse__plant=work_order.plant)
        .select_related("location")
        .order_by("location_id")
    )
    for balance in balances:
        available = balance.on_hand - balance.allocated
        if available <= ZERO:
            continue
        reserve_actual = min(available, remaining_actual)
        equivalent = reserve_actual / conversion
        equivalent = min(equivalent, requested_qty - reserved_equivalent)
        reserve_actual = equivalent * conversion
        if reserve_actual <= ZERO:
            continue

        balance.allocated += reserve_actual
        balance.save(update_fields=["allocated", "updated_at"])
        Reservation.objects.create(
            item=item,
            requested_item=requested_item,
            location=balance.location,
            quantity=reserve_actual,
            requested_quantity=equivalent,
            demand_type="WORK_ORDER",
            demand_id=str(work_order.id),
            required_date=work_order.release_date,
        )
        remaining_actual -= reserve_actual
        reserved_equivalent += equivalent
        if remaining_actual <= ZERO or reserved_equivalent >= requested_qty:
            break
    return reserved_equivalent


@transaction.atomic
def release_work_order(work_order: WorkOrder) -> WorkOrder:
    work_order = WorkOrder.objects.select_for_update().get(pk=work_order.pk)
    if work_order.status != WorkOrder.Status.PLANNED:
        raise ValidationError("Somente ordens planejadas podem ser liberadas.")

    materialize_work_order(work_order)
    shortages = []
    on_date = work_order.release_date

    for material in work_order.materials.select_related("item").all():
        remaining = material.required_quantity

        reserved = _reserve_available(
            item=material.item,
            requested_item=material.item,
            requested_qty=remaining,
            actual_qty=remaining,
            work_order=work_order,
            conversion=Decimal("1"),
        )
        remaining -= reserved

        if remaining > ZERO:
            substitutes = ItemSubstitute.objects.filter(
                plant=work_order.plant,
                item=material.item,
                is_active=True,
            ).select_related("substitute_item").order_by("priority", "substitute_item__code")
            for substitute in substitutes:
                if not substitute.is_effective_on(on_date):
                    continue
                conversion = substitute.substitute_quantity_per_primary
                reserved_equivalent = _reserve_available(
                    item=substitute.substitute_item,
                    requested_item=material.item,
                    requested_qty=remaining,
                    actual_qty=remaining * conversion,
                    work_order=work_order,
                    conversion=conversion,
                )
                remaining -= reserved_equivalent
                if remaining <= ZERO:
                    break

        if remaining > ZERO:
            shortages.append(f"{material.item.code}: falta {remaining}")

    if shortages:
        raise ValidationError({"materials": shortages})

    work_order.status = WorkOrder.Status.RELEASED
    work_order.save(update_fields=["status", "updated_at"])
    append_domain_event(
        idempotency_key=f"event:work-order-release:{work_order.pk}",
        event_type="WORK_ORDER_RELEASED",
        aggregate_type="WORK_ORDER",
        aggregate_id=work_order.pk,
        payload={"number": work_order.number, "item": work_order.item.code},
    )
    return work_order


def _consume_reservation(*, reservation: Reservation, requested_equivalent: Decimal, completion_key: str, actor=None):
    basis_requested = reservation.requested_quantity or reservation.quantity
    if basis_requested <= ZERO:
        raise ValidationError("Reserva com equivalência inválida.")

    remaining_requested = basis_requested - reservation.consumed_requested_quantity
    take_requested = min(requested_equivalent, remaining_requested)
    if take_requested <= ZERO:
        return ZERO

    actual_per_requested = reservation.quantity / basis_requested
    take_actual = take_requested * actual_per_requested

    tx = InventoryTransaction(
        transaction_type=InventoryTransaction.TransactionType.PRODUCTION_ISSUE,
        item=reservation.item,
        from_location=reservation.location,
        quantity=take_actual,
        reference_type="WORK_ORDER",
        reference_id=reservation.demand_id,
        posted_by=actor if getattr(actor, "is_authenticated", False) else None,
        notes=f"Backflush da reserva {reservation.pk}",
        idempotency_key=f"work-order-backflush:{completion_key}:{reservation.pk}",
    )
    post_inventory_transaction(tx)

    balance = StockBalance.objects.select_for_update().get(
        item=reservation.item, location=reservation.location
    )
    balance.allocated = max(balance.allocated - take_actual, ZERO)
    balance.save(update_fields=["allocated", "updated_at"])

    reservation.consumed_quantity += take_actual
    reservation.consumed_requested_quantity += take_requested
    if reservation.consumed_requested_quantity >= basis_requested:
        reservation.status = Reservation.Status.CONSUMED
    reservation.save(
        update_fields=[
            "consumed_quantity",
            "consumed_requested_quantity",
            "status",
            "updated_at",
        ]
    )
    return take_requested


def _validate_completion_replay(
    *,
    existing: WorkOrderCompletion,
    work_order: WorkOrder,
    good_quantity: Decimal,
    scrap_quantity: Decimal,
    destination_location,
    backflush: bool,
) -> None:
    mismatches = []
    if existing.work_order_id != work_order.pk:
        mismatches.append("work_order")
    if existing.good_quantity != good_quantity:
        mismatches.append("good_quantity")
    if existing.scrap_quantity != scrap_quantity:
        mismatches.append("scrap_quantity")
    if existing.destination_location_id != destination_location.pk:
        mismatches.append("destination_location")
    if existing.backflush != backflush:
        mismatches.append("backflush")
    if mismatches:
        raise ValidationError(
            {
                "idempotency_key": (
                    "A chave já foi utilizada por outro apontamento. "
                    f"Campos divergentes: {', '.join(mismatches)}."
                )
            }
        )


@transaction.atomic
def complete_work_order(
    *,
    work_order: WorkOrder,
    good_quantity: Decimal,
    destination_location,
    idempotency_key: str,
    scrap_quantity: Decimal = ZERO,
    backflush: bool = True,
    reported_at=None,
    notes: str = "",
    actor=None,
) -> tuple[WorkOrderCompletion, bool]:
    """Aponta produção, executa backflush, recebe o PA e encerra a OP.

    A chave de idempotência garante que um retry da API não duplique consumo
    nem entrada de estoque.
    """

    if not idempotency_key:
        raise ValidationError({"idempotency_key": "Informe uma chave de idempotência."})
    existing = WorkOrderCompletion.objects.select_related("work_order").filter(
        idempotency_key=idempotency_key
    ).first()
    if existing:
        _validate_completion_replay(
            existing=existing,
            work_order=work_order,
            good_quantity=good_quantity,
            scrap_quantity=scrap_quantity,
            destination_location=destination_location,
            backflush=backflush,
        )
        return existing, False

    work_order = WorkOrder.objects.select_for_update().select_related("item", "plant").get(
        pk=work_order.pk
    )
    existing = WorkOrderCompletion.objects.select_related("work_order").filter(
        idempotency_key=idempotency_key
    ).first()
    if existing:
        _validate_completion_replay(
            existing=existing,
            work_order=work_order,
            good_quantity=good_quantity,
            scrap_quantity=scrap_quantity,
            destination_location=destination_location,
            backflush=backflush,
        )
        return existing, False

    if work_order.status not in {
        WorkOrder.Status.RELEASED,
        WorkOrder.Status.IN_PROGRESS,
        WorkOrder.Status.COMPLETED,
    }:
        raise ValidationError("A OP deve estar liberada, em andamento ou concluída.")
    if destination_location.warehouse.plant_id != work_order.plant_id:
        raise ValidationError("O local de recebimento deve pertencer à planta da OP.")
    if good_quantity <= ZERO:
        raise ValidationError({"good_quantity": "A quantidade boa deve ser positiva."})
    if scrap_quantity < ZERO:
        raise ValidationError({"scrap_quantity": "A sucata não pode ser negativa."})
    if work_order.completed_quantity + good_quantity > work_order.quantity:
        raise ValidationError(
            {"good_quantity": "A quantidade boa excede a quantidade aberta da OP."}
        )

    materialize_work_order(work_order)
    previous_total_reported = sum(
        (row.good_quantity + row.scrap_quantity for row in work_order.completions.all()),
        ZERO,
    )
    new_total_reported = previous_total_reported + good_quantity + scrap_quantity
    completion_ratio = min(new_total_reported / work_order.quantity, Decimal("1"))

    if backflush:
        for material in work_order.materials.select_for_update().all():
            desired_cumulative_issue = material.required_quantity * completion_ratio
            to_issue = desired_cumulative_issue - material.issued_quantity
            if to_issue <= ZERO:
                continue

            reservations = Reservation.objects.select_for_update().filter(
                Q(requested_item=material.item)
                | Q(requested_item__isnull=True, item=material.item),
                demand_type="WORK_ORDER",
                demand_id=str(work_order.pk),
                status=Reservation.Status.OPEN,
            ).select_related("item", "location").order_by("created_at", "pk")
            remaining = to_issue
            for reservation in reservations:
                consumed = _consume_reservation(
                    reservation=reservation,
                    requested_equivalent=remaining,
                    completion_key=idempotency_key,
                    actor=actor,
                )
                remaining -= consumed
                if remaining <= ZERO:
                    break
            if remaining > ZERO:
                raise ValidationError(
                    {"materials": f"Reserva insuficiente para backflush de {material.item.code}: {remaining}."}
                )
            material.issued_quantity += to_issue
            material.save(update_fields=["issued_quantity", "updated_at"])

    receipt_tx = InventoryTransaction(
        transaction_type=InventoryTransaction.TransactionType.PRODUCTION_RECEIPT,
        item=work_order.item,
        to_location=destination_location,
        quantity=good_quantity,
        reference_type="WORK_ORDER",
        reference_id=str(work_order.pk),
        posted_by=actor if getattr(actor, "is_authenticated", False) else None,
        notes=notes,
        idempotency_key=f"work-order-receipt:{idempotency_key}",
    )
    receipt_tx = post_inventory_transaction(receipt_tx)

    work_order.completed_quantity += good_quantity
    closed = work_order.completed_quantity >= work_order.quantity
    work_order.status = WorkOrder.Status.CLOSED if closed else WorkOrder.Status.IN_PROGRESS
    work_order.save(update_fields=["completed_quantity", "status", "updated_at"])

    completion = WorkOrderCompletion.objects.create(
        work_order=work_order,
        idempotency_key=idempotency_key,
        good_quantity=good_quantity,
        scrap_quantity=scrap_quantity,
        destination_location=destination_location,
        receipt_transaction=receipt_tx,
        reported_at=reported_at or timezone.now(),
        backflush=backflush,
        closed_order=closed,
        notes=notes,
    )
    ProductionReport.objects.create(
        work_order=work_order,
        reported_at=completion.reported_at,
        good_quantity=good_quantity,
        scrap_quantity=scrap_quantity,
        notes=notes,
    )

    append_domain_event(
        idempotency_key=f"event:work-order-completion:{idempotency_key}",
        event_type="WORK_ORDER_COMPLETED" if closed else "WORK_ORDER_PARTIAL_COMPLETION",
        aggregate_type="WORK_ORDER",
        aggregate_id=work_order.pk,
        payload={
            "number": work_order.number,
            "item": work_order.item.code,
            "good_quantity": str(good_quantity),
            "scrap_quantity": str(scrap_quantity),
            "completed_quantity": str(work_order.completed_quantity),
            "status": work_order.status,
            "destination_location": destination_location.code,
            "backflush": backflush,
        },
        actor=actor,
    )
    return completion, True

@transaction.atomic
def advance_work_order_operation(*, operation: WorkOrderOperation, action: str, actor=None) -> WorkOrderOperation:
    """Move uma operação da OP entre estados operacionais com validação transacional."""

    operation = (
        WorkOrderOperation.objects.select_for_update()
        .select_related("work_order", "work_center")
        .get(pk=operation.pk)
    )
    work_order = WorkOrder.objects.select_for_update().get(pk=operation.work_order_id)
    if work_order.status not in {WorkOrder.Status.RELEASED, WorkOrder.Status.IN_PROGRESS}:
        raise ValidationError("A OP deve estar liberada ou em andamento.")

    action = (action or "").upper()
    now = timezone.now()
    transitions = {
        "READY": ({WorkOrderOperation.Status.PENDING, WorkOrderOperation.Status.INTERRUPTED}, WorkOrderOperation.Status.READY),
        "SETUP": ({WorkOrderOperation.Status.PENDING, WorkOrderOperation.Status.READY, WorkOrderOperation.Status.INTERRUPTED}, WorkOrderOperation.Status.SETUP),
        "RUN": ({WorkOrderOperation.Status.READY, WorkOrderOperation.Status.SETUP, WorkOrderOperation.Status.INTERRUPTED}, WorkOrderOperation.Status.RUNNING),
        "INTERRUPT": ({WorkOrderOperation.Status.SETUP, WorkOrderOperation.Status.RUNNING}, WorkOrderOperation.Status.INTERRUPTED),
    }
    if action not in transitions:
        raise ValidationError({"action": "Ação de operação inválida."})
    allowed, target = transitions[action]
    if operation.status not in allowed:
        raise ValidationError(
            f"A operação {operation.sequence} não pode executar {action} a partir de {operation.get_status_display()}."
        )

    operation.status = target
    update_fields = ["status", "updated_at"]
    if target in {WorkOrderOperation.Status.SETUP, WorkOrderOperation.Status.RUNNING} and not operation.actual_start:
        operation.actual_start = now
        update_fields.append("actual_start")
    operation.save(update_fields=update_fields)

    if work_order.status == WorkOrder.Status.RELEASED and target in {
        WorkOrderOperation.Status.SETUP,
        WorkOrderOperation.Status.RUNNING,
    }:
        work_order.status = WorkOrder.Status.IN_PROGRESS
        work_order.save(update_fields=["status", "updated_at"])

    append_domain_event(
        idempotency_key=f"event:work-order-operation:{operation.pk}:{action}:{now.isoformat()}",
        event_type=f"WORK_ORDER_OPERATION_{action}",
        aggregate_type="WORK_ORDER_OPERATION",
        aggregate_id=operation.pk,
        payload={
            "work_order": work_order.number,
            "sequence": operation.sequence,
            "work_center": operation.work_center.code,
            "status": operation.status,
        },
        actor=actor,
    )
    return operation


@transaction.atomic
def report_work_order_operation(
    *,
    operation: WorkOrderOperation,
    good_quantity: Decimal = ZERO,
    scrap_quantity: Decimal = ZERO,
    labor_hours: Decimal = ZERO,
    machine_hours: Decimal = ZERO,
    notes: str = "",
    actor=None,
) -> ProductionReport:
    """Registra o apontamento de uma operação e a conclui.

    O apontamento de operação não recebe o produto acabado em estoque; a entrada
    final continua sendo feita por ``complete_work_order``.
    """

    operation = (
        WorkOrderOperation.objects.select_for_update()
        .select_related("work_order", "work_center")
        .get(pk=operation.pk)
    )
    work_order = WorkOrder.objects.select_for_update().get(pk=operation.work_order_id)
    if operation.status not in {
        WorkOrderOperation.Status.READY,
        WorkOrderOperation.Status.SETUP,
        WorkOrderOperation.Status.RUNNING,
        WorkOrderOperation.Status.INTERRUPTED,
    }:
        raise ValidationError("A operação não aceita apontamento neste estado.")
    for field_name, value in {
        "good_quantity": good_quantity,
        "scrap_quantity": scrap_quantity,
        "labor_hours": labor_hours,
        "machine_hours": machine_hours,
    }.items():
        if value < ZERO:
            raise ValidationError({field_name: "O valor não pode ser negativo."})
    if good_quantity == ZERO and scrap_quantity == ZERO and labor_hours == ZERO and machine_hours == ZERO:
        raise ValidationError("Informe quantidade ou horas para o apontamento.")

    now = timezone.now()
    report = ProductionReport.objects.create(
        work_order=work_order,
        operation=operation,
        reported_at=now,
        good_quantity=good_quantity,
        scrap_quantity=scrap_quantity,
        labor_hours=labor_hours,
        machine_hours=machine_hours,
        notes=notes,
    )
    operation.status = WorkOrderOperation.Status.COMPLETED
    operation.actual_end = now
    operation.save(update_fields=["status", "actual_end", "updated_at"])

    next_operation = (
        work_order.operations.select_for_update()
        .filter(sequence__gt=operation.sequence, status=WorkOrderOperation.Status.PENDING)
        .order_by("sequence")
        .first()
    )
    if next_operation:
        next_operation.status = WorkOrderOperation.Status.READY
        next_operation.save(update_fields=["status", "updated_at"])

    if work_order.status == WorkOrder.Status.RELEASED:
        work_order.status = WorkOrder.Status.IN_PROGRESS
        work_order.save(update_fields=["status", "updated_at"])

    append_domain_event(
        idempotency_key=f"event:work-order-operation-report:{report.pk}",
        event_type="WORK_ORDER_OPERATION_REPORTED",
        aggregate_type="WORK_ORDER_OPERATION",
        aggregate_id=operation.pk,
        payload={
            "work_order": work_order.number,
            "sequence": operation.sequence,
            "good_quantity": str(good_quantity),
            "scrap_quantity": str(scrap_quantity),
            "labor_hours": str(labor_hours),
            "machine_hours": str(machine_hours),
        },
        actor=actor,
    )
    return report


@transaction.atomic
def issue_work_order_material(
    *,
    material: WorkOrderMaterial,
    actual_item,
    source_location,
    actual_quantity: Decimal,
    idempotency_key: str,
    actor=None,
    notes: str = "",
) -> InventoryTransaction:
    """Consome manualmente material principal ou substituto previamente aprovado/reservado."""

    if actual_quantity <= ZERO:
        raise ValidationError({"actual_quantity": "A quantidade deve ser positiva."})
    if not idempotency_key:
        raise ValidationError({"idempotency_key": "Informe uma chave de idempotência."})
    existing_tx = InventoryTransaction.objects.filter(
        idempotency_key__startswith=f"work-order-backflush:{idempotency_key}:"
    ).first()
    if existing_tx:
        return existing_tx

    material = (
        WorkOrderMaterial.objects.select_for_update()
        .select_related("work_order__plant", "item")
        .get(pk=material.pk)
    )
    work_order = WorkOrder.objects.select_for_update().get(pk=material.work_order_id)
    if work_order.status not in {WorkOrder.Status.RELEASED, WorkOrder.Status.IN_PROGRESS}:
        raise ValidationError("A OP deve estar liberada ou em andamento.")
    if source_location.warehouse.plant_id != work_order.plant_id:
        raise ValidationError("O local de origem deve pertencer à planta da OP.")

    conversion = Decimal("1")
    if actual_item.pk != material.item_id:
        substitute = ItemSubstitute.objects.filter(
            plant=work_order.plant,
            item=material.item,
            substitute_item=actual_item,
            is_active=True,
        ).first()
        if not substitute or not substitute.is_effective_on(timezone.localdate()):
            raise ValidationError("O item informado não é um substituto aprovado e vigente.")
        conversion = substitute.substitute_quantity_per_primary

    requested_equivalent = actual_quantity / conversion
    remaining_material = material.required_quantity - material.issued_quantity
    if requested_equivalent > remaining_material:
        raise ValidationError(
            {"actual_quantity": f"A baixa excede o material aberto ({remaining_material} equivalente principal)."}
        )

    reservations = list(
        Reservation.objects.select_for_update()
        .filter(
            demand_type="WORK_ORDER",
            demand_id=str(work_order.pk),
            status=Reservation.Status.OPEN,
            item=actual_item,
            location=source_location,
        )
        .filter(Q(requested_item=material.item) | Q(requested_item__isnull=True, item=material.item))
        .order_by("created_at", "pk")
    )
    remaining = requested_equivalent
    first_tx = None
    for reservation in reservations:
        consumed = _consume_reservation(
            reservation=reservation,
            requested_equivalent=remaining,
            completion_key=idempotency_key,
            actor=actor,
        )
        if consumed > ZERO and first_tx is None:
            first_tx = InventoryTransaction.objects.get(
                idempotency_key=f"work-order-backflush:{idempotency_key}:{reservation.pk}"
            )
            if notes and first_tx.notes != notes:
                first_tx.notes = notes
                first_tx.save(update_fields=["notes", "updated_at"])
        remaining -= consumed
        if remaining <= ZERO:
            break
    if remaining > ZERO:
        raise ValidationError(
            {"material": f"Reserva insuficiente no local informado; faltam {remaining} equivalentes do item principal."}
        )

    material.issued_quantity += requested_equivalent
    material.save(update_fields=["issued_quantity", "updated_at"])
    append_domain_event(
        idempotency_key=f"event:work-order-material-issue:{idempotency_key}",
        event_type="WORK_ORDER_MATERIAL_ISSUED",
        aggregate_type="WORK_ORDER",
        aggregate_id=work_order.pk,
        payload={
            "work_order": work_order.number,
            "requested_item": material.item.code,
            "actual_item": actual_item.code,
            "actual_quantity": str(actual_quantity),
            "requested_equivalent": str(requested_equivalent),
            "location": source_location.code,
        },
        actor=actor,
    )
    return first_tx
