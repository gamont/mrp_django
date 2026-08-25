from __future__ import annotations

from datetime import datetime, time
from decimal import Decimal

from django.db.models import DecimalField, ExpressionWrapper, F, Sum
from django.utils import timezone

from apps.common.models import DomainEvent
from apps.costing.models import CostVariance, ItemCost, PurchasePriceVariance, WorkOrderCost
from apps.inventory.models import InventoryTransaction, Reservation, StockBalance
from apps.planning.models import PeggingRecord, PlanningBucket, PlanningMessage, PlannedOrder
from apps.production.models import ProductionReport, WorkOrder, WorkOrderCompletion
from apps.purchasing.models import GoodsReceipt, PurchaseOrder
from apps.quality.models import InspectionOrder


def _moment(value):
    if value is None:
        return timezone.now()
    if isinstance(value, datetime):
        return value
    dt = datetime.combine(value, time.min)
    return timezone.make_aware(dt, timezone.get_current_timezone())


def _timeline(rows):
    normalized = []
    for row in rows:
        row = dict(row)
        row["has_time"] = isinstance(row.get("at"), datetime)
        normalized.append(row)
    return sorted(normalized, key=lambda row: _moment(row.get("at")), reverse=True)


def work_order_detail_context(order: WorkOrder) -> dict:
    materials = order.materials.select_related("item", "bom_line").annotate(open_quantity=ExpressionWrapper(F("required_quantity")-F("issued_quantity"), output_field=DecimalField(max_digits=18, decimal_places=4)))
    operations = order.operations.select_related("work_center").all()
    reports = order.reports.select_related("operation", "operation__work_center").all()
    completions = order.completions.select_related("destination_location", "receipt_transaction").all()
    reservations = Reservation.objects.filter(demand_type="WORK_ORDER", demand_id=str(order.pk)).select_related("item", "requested_item", "location")
    material_list = list(materials)
    reservation_list = list(reservations)
    for material in material_list:
        material.open_reservations = [
            row for row in reservation_list
            if row.status == Reservation.Status.OPEN
            and (row.requested_item_id == material.item_id or (row.requested_item_id is None and row.item_id == material.item_id))
            and row.remaining_quantity > 0
        ]
        for row in material.open_reservations:
            row.ui_issue_key = f"ui-manual-issue:{material.pk}:{row.pk}:{row.consumed_quantity}"
    transactions = InventoryTransaction.objects.filter(reference_type="WORK_ORDER", reference_id=str(order.pk)).select_related("item", "from_location", "to_location")
    costs = order.cost_summaries.select_related("cost_version").prefetch_related("lines__item", "lines__work_center")
    variances = order.cost_variances.all()
    pegging = PeggingRecord.objects.none()
    if order.planning_run_id:
        pegging = PeggingRecord.objects.filter(planning_run_id=order.planning_run_id)
        if order.planned_order_id:
            pegging = pegging.filter(parent_planned_order_id=order.planned_order_id)
        pegging = pegging.select_related("component_item", "parent_item", "top_level_item")

    material_required = materials.aggregate(v=Sum("required_quantity"))["v"] or Decimal("0")
    material_issued = materials.aggregate(v=Sum("issued_quantity"))["v"] or Decimal("0")
    timeline = [
        {"at": order.created_at, "kind": "OP", "title": "Ordem criada", "detail": f"{order.number} · {order.quantity} {order.item.code}"},
        {"at": order.release_date, "kind": "PLANO", "title": "Data planejada de liberação", "detail": order.status},
        {"at": order.due_date, "kind": "PLANO", "title": "Data de entrega", "detail": f"Quantidade planejada {order.quantity}"},
    ]
    for row in reports:
        timeline.append({"at": row.reported_at, "kind": "APONTAMENTO", "title": f"Produção: {row.good_quantity} boas / {row.scrap_quantity} refugo", "detail": row.notes or (f"Operação {row.operation.sequence}" if row.operation_id else "Apontamento geral")})
    for row in completions:
        timeline.append({"at": row.reported_at, "kind": "ENTRADA", "title": f"Entrada de produção: {row.good_quantity}", "detail": f"Destino {row.destination_location}"})
    for row in transactions[:100]:
        timeline.append({"at": row.posted_at, "kind": "ESTOQUE", "title": f"{row.get_transaction_type_display()}: {row.item.code} {row.quantity}", "detail": row.notes or row.idempotency_key or ""})
    operation_ids = list(order.operations.values_list("pk", flat=True))
    events = DomainEvent.objects.filter(
        aggregate_type="WORK_ORDER_OPERATION", aggregate_id__in=[str(pk) for pk in operation_ids]
    ).select_related("actor")[:100]
    for event in events:
        timeline.append({
            "at": event.occurred_at,
            "kind": "OPERAÇÃO",
            "title": event.event_type.replace("WORK_ORDER_OPERATION_", "").replace("_", " ").title(),
            "detail": f"Seq. {event.payload.get('sequence', '—')} · {event.payload.get('work_center', '—')} · {event.actor or 'sistema'}",
        })

    return {
        "order": order,
        "materials": material_list,
        "operations": operations,
        "reports": reports[:50],
        "completions": completions[:30],
        "reservations": reservation_list,
        "transactions": transactions[:50],
        "costs": costs,
        "variances": variances,
        "pegging": pegging[:100],
        "material_required": material_required,
        "material_issued": material_issued,
        "material_open": material_required - material_issued,
        "timeline": _timeline(timeline),
    }


def purchase_order_detail_context(order: PurchaseOrder) -> dict:
    lines = order.lines.select_related("item").prefetch_related("receipts__destination_location")
    receipts = GoodsReceipt.objects.filter(purchase_order_line__purchase_order=order).select_related("purchase_order_line__item", "destination_location", "inventory_transaction")
    receipt_ids = list(receipts.values_list("pk", flat=True))
    ppv = PurchasePriceVariance.objects.filter(goods_receipt_id__in=receipt_ids).select_related("goods_receipt__purchase_order_line__item", "cost_version")
    ordered = lines.aggregate(v=Sum("quantity"))["v"] or Decimal("0")
    received = lines.aggregate(v=Sum("received_quantity"))["v"] or Decimal("0")
    timeline = [
        {"at": order.created_at, "kind": "OC", "title": "Ordem de compra criada", "detail": order.number},
        {"at": order.order_date, "kind": "PLANO", "title": "Data da ordem", "detail": order.supplier.name},
        {"at": order.expected_date, "kind": "PLANO", "title": "Entrega prevista", "detail": order.get_status_display()},
    ]
    for r in receipts:
        timeline.append({"at": r.received_at, "kind": "RECEBIMENTO", "title": f"{r.purchase_order_line.item.code}: {r.quantity}", "detail": f"{r.receipt_number} · {r.destination_location}"})
    return {"order": order, "lines": lines, "receipts": receipts[:50], "ppv": ppv, "ordered_quantity": ordered, "received_quantity": received, "open_quantity": ordered-received, "timeline": _timeline(timeline)}


def inspection_detail_context(order: InspectionOrder) -> dict:
    characteristics = list(order.plan.characteristics.all())
    results = list(order.results.select_related("characteristic", "measured_by").all())
    for characteristic in characteristics:
        characteristic.result_rows = [row for row in results if row.characteristic_id == characteristic.pk]
        characteristic.next_sample_number = max([row.sample_number for row in characteristic.result_rows] or [0]) + 1
    ncrs = order.nonconformances.prefetch_related("dispositions").all()
    timeline = [
        {"at": order.opened_at, "kind": "QUALIDADE", "title": "Inspeção aberta", "detail": f"Plano {order.plan.code} rev. {order.plan.revision}"},
    ]
    if order.completed_at:
        timeline.append({"at": order.completed_at, "kind": "QUALIDADE", "title": f"Inspeção {order.get_status_display()}", "detail": f"Aprovada {order.quantity_approved} · Rejeitada {order.quantity_rejected}"})
    for r in results:
        value = r.numeric_value if r.numeric_value is not None else r.boolean_value if r.boolean_value is not None else r.text_value
        timeline.append({"at": r.measured_at, "kind": "MEDIÇÃO", "title": r.characteristic.name, "detail": f"{value} · {'Conforme' if r.is_conforming else 'Não conforme'}"})
    for n in ncrs:
        timeline.append({"at": n.created_at, "kind": "NCR", "title": n.number, "detail": n.description})
    return {"order": order, "characteristics": characteristics, "results": results, "nonconformances": ncrs, "timeline": _timeline(timeline)}


def planned_order_detail_context(order: PlannedOrder) -> dict:
    pegging_down = order.component_pegging.select_related("component_item", "parent_item", "top_level_item").all()
    messages = order.messages.all()
    buckets = PlanningBucket.objects.filter(planning_run=order.planning_run, item=order.item).order_by("bucket_date")
    return {"order": order, "pegging": pegging_down, "messages": messages, "buckets": buckets}


def item_cost_detail_context(item_cost: ItemCost) -> dict:
    item = item_cost.item
    conversion_expr = ExpressionWrapper(F("setup_cost") + F("labor_cost") + F("machine_cost") + F("overhead_cost") + F("subcontract_cost"), output_field=DecimalField(max_digits=22, decimal_places=4))
    versions = ItemCost.objects.filter(item=item, cost_version__plant=item_cost.cost_version.plant).select_related("cost_version").annotate(conversion_cost=conversion_expr).order_by("-cost_version__effective_from")[:12]
    balances = StockBalance.objects.filter(item=item, location__warehouse__plant=item_cost.cost_version.plant).select_related("location__warehouse")
    variances = CostVariance.objects.filter(work_order__item=item, work_order__plant=item_cost.cost_version.plant).select_related("work_order").order_by("-created_at")[:30]
    work_costs = WorkOrderCost.objects.filter(work_order__item=item, work_order__plant=item_cost.cost_version.plant).select_related("work_order", "cost_version").order_by("-calculated_at")[:30]
    return {"item_cost": item_cost, "item": item, "versions": versions, "balances": balances, "variances": variances, "work_costs": work_costs}
