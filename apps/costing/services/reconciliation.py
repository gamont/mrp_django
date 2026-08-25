from decimal import Decimal
from django.db import transaction
from django.db.models import Sum
from django.utils import timezone

from apps.costing.models import InventoryReconciliationRun, InventoryReconciliationLine, MovingAverageCostBalance
from apps.inventory.models import StockBalance
from apps.masterdata.models import Item

ZERO = Decimal("0")


@transaction.atomic
def reconcile_inventory(*, plant, period=None, user=None):
    run = InventoryReconciliationRun.objects.create(plant=plant, period=period, as_of=timezone.now(), created_by=user)
    physical = {row["item_id"]: row["q"] or ZERO for row in StockBalance.objects.filter(location__warehouse__plant=plant).values("item_id").annotate(q=Sum("on_hand"))}
    financial = {b.item_id: b for b in MovingAverageCostBalance.objects.filter(plant=plant)}
    item_ids = set(physical) | set(financial)
    totals = {"pq": ZERO, "fq": ZERO, "pv": ZERO, "fv": ZERO}
    for item in Item.objects.filter(pk__in=item_ids).order_by("code"):
        pq = physical.get(item.pk, ZERO)
        bal = financial.get(item.pk)
        fq = bal.quantity if bal else ZERO
        unit = bal.average_unit_cost if bal else ZERO
        pv = pq * unit; fv = bal.inventory_value if bal else ZERO
        qv = pq - fq; vv = pv - fv
        InventoryReconciliationLine.objects.create(
            run=run, item=item, physical_quantity=pq, financial_quantity=fq, unit_cost=unit,
            physical_value=pv, financial_value=fv, quantity_variance=qv, value_variance=vv,
            reconciled=(qv == 0 and vv == 0),
        )
        totals["pq"] += pq; totals["fq"] += fq; totals["pv"] += pv; totals["fv"] += fv
    run.physical_quantity = totals["pq"]; run.financial_quantity = totals["fq"]
    run.physical_value = totals["pv"]; run.financial_value = totals["fv"]
    run.quantity_variance = totals["pq"] - totals["fq"]; run.value_variance = totals["pv"] - totals["fv"]
    run.status = InventoryReconciliationRun.Status.RECONCILED if run.quantity_variance == 0 and run.value_variance == 0 else InventoryReconciliationRun.Status.COMPLETED
    run.save()
    return run
