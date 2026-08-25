from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal

from django.db.models import DecimalField, ExpressionWrapper, F, Sum
from django.utils import timezone

from apps.common.models import Plant
from apps.costing.models import AccountingPeriod, CostVariance, ItemCost, WIPSnapshot
from apps.inventory.models import Location, StockBalance
from apps.planning.models import CapacityAllocation, PlannedOrder, PlanningMessage, PlanningRun
from apps.production.models import WorkOrder, WorkOrderOperation
from apps.purchasing.models import PurchaseOrder, PurchaseOrderLine
from apps.quality.models import InspectionOrder, NonConformance


@dataclass(frozen=True)
class DashboardContext:
    plant: Plant | None
    data: dict


def selected_plant(request) -> Plant | None:
    plant_id = request.session.get("ui_plant_id")
    qs = Plant.objects.filter(is_active=True).order_by("code")
    plant = qs.filter(pk=plant_id).first() if plant_id else qs.first()
    if plant and plant_id != plant.pk:
        request.session["ui_plant_id"] = plant.pk
    return plant


def planner_dashboard(plant: Plant | None) -> DashboardContext:
    if not plant:
        return DashboardContext(None, {})
    latest_run = PlanningRun.objects.filter(plant=plant).first()
    messages = PlanningMessage.objects.none()
    orders = PlannedOrder.objects.none()
    if latest_run:
        messages = latest_run.messages.select_related("item", "planned_order")
        orders = latest_run.planned_orders.select_related("item")
    overloads = CapacityAllocation.objects.filter(scenario__plant=plant, overload_hours__gt=0).select_related("work_center").order_by("-overload_hours")[:10]
    return DashboardContext(plant, {
        "latest_run": latest_run,
        "message_count": messages.count(),
        "error_count": messages.filter(severity="ERROR").count(),
        "warning_count": messages.filter(severity="WARNING").count(),
        "release_count": messages.filter(message_type="RELEASE").count(),
        "planned_make": orders.filter(order_type="MAKE", status__in=["PLANNED", "FIRM"]).count(),
        "planned_purchase": orders.filter(order_type="PURCHASE", status__in=["PLANNED", "FIRM"]).count(),
        "messages": messages[:12],
        "orders": orders[:12],
        "overloads": overloads,
    })


def production_dashboard(plant: Plant | None) -> DashboardContext:
    if not plant:
        return DashboardContext(None, {})
    today = timezone.localdate()
    qs = WorkOrder.objects.filter(plant=plant).select_related("item")
    operations = WorkOrderOperation.objects.filter(work_order__plant=plant).select_related("work_order", "work_center")
    active = qs.filter(status__in=["RELEASED", "IN_PROGRESS"])
    planned = qs.filter(status="PLANNED")
    locations = Location.objects.filter(warehouse__plant=plant, is_active=True).select_related("warehouse").order_by("warehouse__code", "code")
    return DashboardContext(plant, {
        "planned": planned.count(),
        "released": qs.filter(status="RELEASED").count(),
        "in_progress": qs.filter(status="IN_PROGRESS").count(),
        "late": active.filter(due_date__lt=today).count(),
        "ready_ops": operations.filter(status__in=["READY", "SETUP", "RUNNING"]).count(),
        "planned_orders": planned.order_by("release_date", "number")[:12],
        "orders": active.order_by("due_date", "number")[:15],
        "operations": operations.filter(status__in=["READY", "SETUP", "RUNNING", "INTERRUPTED"]).order_by("planned_start", "work_order__number")[:15],
        "locations": locations,
    })


def purchasing_dashboard(plant: Plant | None) -> DashboardContext:
    if not plant:
        return DashboardContext(None, {})
    today = timezone.localdate()
    qs = PurchaseOrder.objects.filter(plant=plant).select_related("supplier")
    open_status = ["RELEASED", "PARTIAL"]
    lines = PurchaseOrderLine.objects.filter(purchase_order__plant=plant, purchase_order__status__in=open_status).select_related("purchase_order", "item", "purchase_order__supplier")
    locations = Location.objects.filter(warehouse__plant=plant, is_active=True).select_related("warehouse").order_by("warehouse__code", "code")
    return DashboardContext(plant, {
        "released": qs.filter(status="RELEASED").count(),
        "partial": qs.filter(status="PARTIAL").count(),
        "late": qs.filter(status__in=open_status, expected_date__lt=today).count(),
        "open_lines": lines.filter(received_quantity__lt=models_f("quantity")).count(),
        "orders": qs.filter(status__in=open_status).order_by("expected_date", "number")[:15],
        "lines": lines.order_by("expected_date", "purchase_order__number")[:15],
        "locations": locations,
    })


def models_f(field: str):
    return F(field)


def inventory_dashboard(plant: Plant | None) -> DashboardContext:
    if not plant:
        return DashboardContext(None, {})
    balances = StockBalance.objects.filter(location__warehouse__plant=plant).select_related("item", "location", "location__warehouse")
    low = balances.annotate(available_calc=models_f("on_hand") - models_f("allocated")).filter(available_calc__lte=0)
    totals = balances.aggregate(on_hand=Sum("on_hand"), allocated=Sum("allocated"))
    on_hand = totals["on_hand"] or Decimal("0")
    allocated = totals["allocated"] or Decimal("0")
    return DashboardContext(plant, {
        "sku_count": balances.values("item_id").distinct().count(),
        "on_hand": on_hand,
        "allocated": allocated,
        "available": on_hand - allocated,
        "shortage_count": low.count(),
        "shortages": low.order_by("available_calc", "item__code")[:15],
        "balances": balances.order_by("item__code", "location__code")[:15],
    })


def quality_dashboard(plant: Plant | None) -> DashboardContext:
    if not plant:
        return DashboardContext(None, {})
    inspections = InspectionOrder.objects.filter(plant=plant).select_related("item", "supplier", "plan")
    ncr = NonConformance.objects.filter(plant=plant).select_related("item", "supplier")
    return DashboardContext(plant, {
        "open_inspections": inspections.filter(status__in=["OPEN", "IN_PROGRESS"]).count(),
        "rejected_inspections": inspections.filter(status="REJECTED").count(),
        "open_ncr": ncr.exclude(status="CLOSED").count(),
        "critical_ncr": ncr.exclude(status="CLOSED").filter(severity="CRITICAL").count(),
        "inspections": inspections.filter(status__in=["OPEN", "IN_PROGRESS", "PARTIAL", "REJECTED"]).order_by("-opened_at")[:15],
        "nonconformances": ncr.exclude(status="CLOSED").order_by("-created_at")[:15],
    })


def costing_dashboard(plant: Plant | None) -> DashboardContext:
    if not plant:
        return DashboardContext(None, {})
    periods = AccountingPeriod.objects.filter(plant=plant).select_related("cost_version")
    active_period = periods.filter(status__in=["OPEN", "CLOSING"]).first() or periods.first()
    variances = CostVariance.objects.filter(work_order__plant=plant).select_related("work_order")
    variance_total = variances.aggregate(total=Sum("variance_amount"))["total"] or Decimal("0")
    unfavorable = variances.filter(favorable=False).aggregate(total=Sum("variance_amount"))["total"] or Decimal("0")
    latest_wip = WIPSnapshot.objects.filter(period__plant=plant).order_by("-as_of").first()
    conversion_expr = ExpressionWrapper(
        F("setup_cost") + F("labor_cost") + F("machine_cost") + F("overhead_cost") + F("subcontract_cost"),
        output_field=DecimalField(max_digits=22, decimal_places=4),
    )
    latest_costs = ItemCost.objects.filter(cost_version__plant=plant).select_related("item", "cost_version").annotate(conversion_cost=conversion_expr).order_by("-created_at")[:12]
    return DashboardContext(plant, {
        "active_period": active_period,
        "open_periods": periods.filter(status="OPEN").count(),
        "variance_total": variance_total,
        "unfavorable_variance": unfavorable,
        "wip_value": latest_wip.total_value if latest_wip else Decimal("0"),
        "latest_costs": latest_costs,
        "variances": variances.order_by("-created_at")[:15],
    })
