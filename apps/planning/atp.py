from __future__ import annotations

from collections import defaultdict
from datetime import date, timedelta
from decimal import Decimal

from django.db.models import F, Sum
from django.utils import timezone

from apps.demand.models import SalesOrder, SalesOrderLine
from apps.inventory.models import StockBalance
from apps.masterdata.models import Item
from apps.production.models import WorkOrder
from apps.purchasing.models import PurchaseOrder, PurchaseOrderLine

ZERO = Decimal("0")


def calculate_atp(
    *,
    plant,
    item: Item,
    quantity: Decimal,
    requested_date: date,
    horizon_days: int = 365,
) -> dict:
    """Calcula ATP discreto usando estoque, recebimentos firmes e pedidos abertos."""

    today = timezone.localdate()
    horizon_end = max(requested_date, today) + timedelta(days=horizon_days)
    opening = (
        StockBalance.objects.filter(item=item, location__warehouse__plant=plant)
        .aggregate(on_hand=Sum("on_hand"), allocated=Sum("allocated"))
    )
    available = (opening["on_hand"] or ZERO) - (opening["allocated"] or ZERO)

    receipts: dict[date, Decimal] = defaultdict(Decimal)
    po_lines = PurchaseOrderLine.objects.filter(
        item=item,
        purchase_order__plant=plant,
        purchase_order__status__in=[PurchaseOrder.Status.RELEASED, PurchaseOrder.Status.PARTIAL],
        expected_date__range=(today, horizon_end),
    ).annotate(open_qty=F("quantity") - F("received_quantity"))
    for line in po_lines:
        if line.open_qty > ZERO:
            receipts[line.expected_date] += line.open_qty

    work_orders = WorkOrder.objects.filter(
        item=item,
        plant=plant,
        status__in=[WorkOrder.Status.RELEASED, WorkOrder.Status.IN_PROGRESS],
        due_date__range=(today, horizon_end),
    ).annotate(open_qty=F("quantity") - F("completed_quantity"))
    for order in work_orders:
        if order.open_qty > ZERO:
            receipts[order.due_date] += order.open_qty

    commitments: dict[date, Decimal] = defaultdict(Decimal)
    sales_lines = SalesOrderLine.objects.filter(
        item=item,
        sales_order__plant=plant,
        sales_order__status__in=[SalesOrder.Status.CONFIRMED, SalesOrder.Status.PARTIAL],
        requested_date__lte=horizon_end,
    ).annotate(open_qty=F("quantity") - F("delivered_quantity"))
    from apps.integrated_scheduling.commercial_confirmation import effective_customer_commitment_date
    for line in sales_lines:
        commitment_date = effective_customer_commitment_date(line)
        if line.open_qty > ZERO and today <= commitment_date <= horizon_end:
            commitments[commitment_date] += line.open_qty

    event_dates = sorted(set(receipts) | set(commitments) | {requested_date})
    timeline = []
    promised_date = None
    requested_available = None
    for event_date in event_dates:
        available += receipts[event_date]
        available -= commitments[event_date]
        timeline.append(
            {
                "date": event_date.isoformat(),
                "receipts": str(receipts[event_date]),
                "commitments": str(commitments[event_date]),
                "available_to_promise": str(available),
            }
        )
        if event_date == requested_date:
            requested_available = available
        if event_date >= requested_date and available >= quantity and promised_date is None:
            promised_date = event_date

    return {
        "item_id": item.pk,
        "item_code": item.code,
        "plant_id": plant.pk,
        "requested_quantity": str(quantity),
        "requested_date": requested_date.isoformat(),
        "available_on_requested_date": str(requested_available if requested_available is not None else available),
        "can_promise": promised_date is not None,
        "promised_date": promised_date.isoformat() if promised_date else None,
        "timeline": timeline,
    }
