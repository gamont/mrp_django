from __future__ import annotations

from collections import defaultdict
from datetime import date
from decimal import Decimal

from django.db import transaction
from django.db.models import Max

from apps.planning.models import DemandPeggingAllocation
from apps.production.models import WorkOrder
from .models import CommercialPromiseAlert, RecoveryCommercialImpact, RecoveryPlan, ReschedulingTrigger

ZERO = Decimal("0")


def _affected_work_orders(trigger: ReschedulingTrigger):
    if not trigger.publication:
        return []
    slots = trigger.publication.slots.filter(planned_end__gte=trigger.affected_from, actual_end__isnull=True).select_related("operation__work_order")
    payload = trigger.payload or {}
    if trigger.trigger_type == ReschedulingTrigger.TriggerType.MACHINE_BREAKDOWN and str(trigger.source_id).isdigit():
        slots = slots.filter(machine_id=int(trigger.source_id))
    elif trigger.trigger_type == ReschedulingTrigger.TriggerType.MATERIAL_SHORTAGE and payload.get("work_order_id"):
        slots = slots.filter(operation__work_order_id=payload["work_order_id"])
    ids = sorted({s.operation.work_order_id for s in slots})
    return list(WorkOrder.objects.filter(pk__in=ids))


def _promise_dates_for_work_orders(trigger, work_orders, plan=None):
    ids = [w.pk for w in work_orders]
    current = dict(
        trigger.publication.slots.filter(operation__work_order_id__in=ids)
        .values("operation__work_order_id")
        .annotate(end=Max("planned_end"))
        .values_list("operation__work_order_id", "end")
    ) if trigger.publication else {}
    recovered = {}
    if plan and plan.solver_run_id:
        recovered = dict(
            plan.solver_run.assignments.filter(operation__work_order_id__in=ids)
            .values("operation__work_order_id")
            .annotate(end=Max("end"))
            .values_list("operation__work_order_id", "end")
        )
    return current, recovered


def exact_sales_order_allocations(trigger: ReschedulingTrigger):
    """Return exact persisted SalesOrderLine allocations for affected work orders.

    Legacy MRP runs created before 0.7.3 simply return no exact rows; callers must
    label any fallback separately rather than presenting inference as exact pegging.
    """
    work_orders = _affected_work_orders(trigger)
    planned_ids = [w.planned_order_id for w in work_orders if w.planned_order_id]
    if not planned_ids:
        return work_orders, []
    rows = list(
        DemandPeggingAllocation.objects.filter(
            planned_order_id__in=planned_ids,
            source_type=DemandPeggingAllocation.SourceType.SALES_ORDER_LINE,
            sales_order_line__isnull=False,
        ).select_related("sales_order_line__sales_order", "sales_order_line__item", "planned_order")
    )
    return work_orders, rows


@transaction.atomic
def rebuild_recovery_commercial_impact(trigger: ReschedulingTrigger, plan: RecoveryPlan | None = None, create_alerts: bool = True):
    work_orders, allocations = exact_sales_order_allocations(trigger)
    qs = RecoveryCommercialImpact.objects.filter(trigger=trigger, recovery_plan=plan)
    qs.delete()
    if not allocations:
        return {"exact": False, "method": "NO_SOURCE_AWARE_PEGGING", "rows": [], "impacted_sales_orders": 0, "late_sales_orders": 0}

    wo_by_po = {w.planned_order_id: w for w in work_orders if w.planned_order_id}
    current_dates, recovered_dates = _promise_dates_for_work_orders(trigger, work_orders, plan=plan)
    grouped = defaultdict(lambda: {"qty": ZERO, "wo_ids": set(), "alloc_ids": []})
    line_by_id = {}
    for alloc in allocations:
        line = alloc.sales_order_line
        line_by_id[line.pk] = line
        wo = wo_by_po.get(alloc.planned_order_id)
        if not wo:
            continue
        g = grouped[line.pk]
        g["qty"] += alloc.quantity
        g["wo_ids"].add(wo.pk)
        g["alloc_ids"].append(alloc.pk)

    output = []
    late_orders = set()
    impacted_orders = set()
    for line_id, info in grouped.items():
        line = line_by_id[line_id]
        current_dt = max([current_dates.get(w) for w in info["wo_ids"] if current_dates.get(w)], default=None)
        recovered_dt = max([recovered_dates.get(w) for w in info["wo_ids"] if recovered_dates.get(w)], default=None) if plan else None
        current_date = current_dt.date() if current_dt else None
        recovered_date = recovered_dt.date() if recovered_dt else None
        comparison_date = recovered_date or current_date
        delta_days = (comparison_date - line.requested_date).days if comparison_date else 0
        if comparison_date is None:
            status = RecoveryCommercialImpact.PromiseStatus.UNKNOWN
        elif comparison_date <= line.requested_date:
            status = RecoveryCommercialImpact.PromiseStatus.RECOVERED if plan and current_date and current_date > line.requested_date else RecoveryCommercialImpact.PromiseStatus.ON_TIME
        elif plan:
            status = RecoveryCommercialImpact.PromiseStatus.LATE
        else:
            status = RecoveryCommercialImpact.PromiseStatus.AT_RISK
        impact = RecoveryCommercialImpact.objects.create(
            trigger=trigger, recovery_plan=plan, sales_order_line=line,
            pegged_quantity=min(info["qty"], line.open_quantity), requested_date=line.requested_date,
            current_promise_date=current_date, recovered_promise_date=recovered_date,
            promise_delta_days=delta_days, promise_status=status, pegging_method="EXACT_MRP_SOURCE",
            details={"work_order_ids": sorted(info["wo_ids"]), "allocation_ids": info["alloc_ids"]},
        )
        impacted_orders.add(line.sales_order_id)
        if status in {RecoveryCommercialImpact.PromiseStatus.LATE, RecoveryCommercialImpact.PromiseStatus.AT_RISK}:
            late_orders.add(line.sales_order_id)
            if create_alerts:
                sev = "CRITICAL" if delta_days >= 2 else "HIGH" if delta_days >= 1 else "MEDIUM"
                CommercialPromiseAlert.objects.update_or_create(
                    trigger=trigger, recovery_plan=plan, sales_order_line=line,
                    defaults={"severity": sev, "status": CommercialPromiseAlert.Status.OPEN,
                              "message": f"Pedido {line.sales_order.number} linha {line.line_number}: promessa {comparison_date} vs solicitada {line.requested_date}.",
                              "details": {"pegged_quantity": str(impact.pegged_quantity), "promise_delta_days": delta_days, "method": "EXACT_MRP_SOURCE"}},
                )
        output.append(impact)
    return {"exact": True, "method": "EXACT_MRP_SOURCE", "rows": output,
            "impacted_sales_orders": len(impacted_orders), "late_sales_orders": len(late_orders)}


def commercial_impact_summary(trigger: ReschedulingTrigger, plan: RecoveryPlan | None = None):
    result = rebuild_recovery_commercial_impact(trigger, plan=plan)
    rows = result["rows"]
    return {
        "exact": result["exact"], "method": result["method"],
        "impacted_sales_orders": result["impacted_sales_orders"],
        "late_sales_orders": result["late_sales_orders"],
        "lines": [
            {"sales_order": r.sales_order_line.sales_order.number, "customer_code": r.sales_order_line.sales_order.customer_code,
             "customer_name": r.sales_order_line.sales_order.customer_name, "line_number": r.sales_order_line.line_number,
             "item": r.sales_order_line.item.code, "pegged_quantity": str(r.pegged_quantity),
             "requested_date": r.requested_date.isoformat(), "current_promise_date": r.current_promise_date.isoformat() if r.current_promise_date else None,
             "recovered_promise_date": r.recovered_promise_date.isoformat() if r.recovered_promise_date else None,
             "promise_delta_days": r.promise_delta_days, "status": r.promise_status}
            for r in rows
        ],
    }
