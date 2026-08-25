from decimal import Decimal
from django.db import transaction
from django.utils import timezone
from apps.costing.models import CostVersion, ItemCost, WorkCenterRate, WorkOrderCost, WorkOrderCostLine
from apps.inventory.models import InventoryTransaction
from apps.production.models import ProductionReport, WorkOrder

D = Decimal


def active_version_for(work_order: WorkOrder) -> CostVersion:
    version = CostVersion.objects.filter(plant=work_order.plant, status=CostVersion.Status.ACTIVE).order_by("-effective_from").first()
    if not version:
        raise ValueError("Não existe versão de custo ativa para a planta.")
    return version


def _rate_map(version):
    return {x.work_center_id: x for x in WorkCenterRate.objects.filter(cost_version=version)}


@transaction.atomic
def calculate_planned_cost(work_order: WorkOrder, version: CostVersion | None = None) -> WorkOrderCost:
    version = version or active_version_for(work_order)
    quantity = work_order.quantity
    summary = {k: D("0") for k in ("material", "setup", "labor", "machine", "overhead", "subcontract", "scrap", "rework")}
    lines = []
    for material in work_order.materials.select_related("item"):
        unit = ItemCost.objects.filter(cost_version=version, item=material.item).values_list("total_cost", flat=True).first()
        unit = unit if unit is not None else material.item.standard_cost
        amount = material.required_quantity * unit
        summary["material"] += amount
        lines.append((WorkOrderCostLine.Category.MATERIAL, material.item, None, material.required_quantity, D("0"), unit, amount, {"source": "work_order_material"}))
    rates = _rate_map(version)
    for op in work_order.operations.select_related("work_center"):
        rate = rates.get(op.work_center_id)
        if not rate:
            continue
        setup = op.setup_hours * rate.setup_rate
        labor = op.run_hours * rate.labor_rate
        machine = op.run_hours * rate.machine_rate
        overhead = (op.setup_hours + op.run_hours) * rate.overhead_rate
        summary["setup"] += setup; summary["labor"] += labor; summary["machine"] += machine; summary["overhead"] += overhead
        ref = f"OP{op.sequence}"
        lines += [
            (WorkOrderCostLine.Category.SETUP, None, op.work_center, D("0"), op.setup_hours, rate.setup_rate, setup, {"operation": ref}),
            (WorkOrderCostLine.Category.LABOR, None, op.work_center, D("0"), op.run_hours, rate.labor_rate, labor, {"operation": ref}),
            (WorkOrderCostLine.Category.MACHINE, None, op.work_center, D("0"), op.run_hours, rate.machine_rate, machine, {"operation": ref}),
            (WorkOrderCostLine.Category.OVERHEAD, None, op.work_center, D("0"), op.setup_hours + op.run_hours, rate.overhead_rate, overhead, {"operation": ref}),
        ]
    total = sum(summary.values(), D("0"))
    obj, _ = WorkOrderCost.objects.update_or_create(work_order=work_order, cost_type=WorkOrderCost.CostType.PLANNED, defaults={
        "cost_version": version, "quantity_basis": quantity, "material_cost": summary["material"], "setup_cost": summary["setup"],
        "labor_cost": summary["labor"], "machine_cost": summary["machine"], "overhead_cost": summary["overhead"],
        "subcontract_cost": summary["subcontract"], "scrap_cost": summary["scrap"], "rework_cost": summary["rework"],
        "total_cost": total, "unit_cost": total / quantity if quantity else D("0"), "calculated_at": timezone.now(),
        "calculation_details": {"basis": "released_work_order_snapshot"},
    })
    obj.lines.all().delete()
    WorkOrderCostLine.objects.bulk_create([WorkOrderCostLine(work_order_cost=obj, category=c, item=i, work_center=w, reference=d.get("operation", ""), quantity=q, hours=h, rate=r, amount=a, details=d) for c,i,w,q,h,r,a,d in lines])
    return obj


@transaction.atomic
def calculate_actual_cost(work_order: WorkOrder, version: CostVersion | None = None) -> WorkOrderCost:
    version = version or active_version_for(work_order)
    quantity = work_order.completed_quantity or work_order.quantity
    summary = {k: D("0") for k in ("material", "setup", "labor", "machine", "overhead", "subcontract", "scrap", "rework")}
    lines = []
    txs = InventoryTransaction.objects.filter(reference_type="WORK_ORDER", reference_id=work_order.number, transaction_type=InventoryTransaction.TransactionType.PRODUCTION_ISSUE).select_related("item")
    for tx in txs:
        unit = ItemCost.objects.filter(cost_version=version, item=tx.item).values_list("total_cost", flat=True).first()
        unit = unit if unit is not None else tx.item.standard_cost
        amount = abs(tx.quantity) * unit
        summary["material"] += amount
        lines.append((WorkOrderCostLine.Category.MATERIAL, tx.item, None, abs(tx.quantity), D("0"), unit, amount, {"transaction": tx.id}))
    rates = _rate_map(version)
    reports = ProductionReport.objects.filter(work_order=work_order).select_related("operation__work_center")
    for rep in reports:
        wc = rep.operation.work_center if rep.operation_id else None
        rate = rates.get(wc.id) if wc else None
        if not rate:
            continue
        labor = rep.labor_hours * rate.labor_rate
        machine = rep.machine_hours * rate.machine_rate
        overhead = (rep.labor_hours + rep.machine_hours) * rate.overhead_rate
        scrap_unit = ItemCost.objects.filter(cost_version=version, item=work_order.item).values_list("total_cost", flat=True).first() or work_order.item.standard_cost
        scrap = rep.scrap_quantity * scrap_unit
        summary["labor"] += labor; summary["machine"] += machine; summary["overhead"] += overhead; summary["scrap"] += scrap
        lines += [
            (WorkOrderCostLine.Category.LABOR, None, wc, D("0"), rep.labor_hours, rate.labor_rate, labor, {"report": rep.id}),
            (WorkOrderCostLine.Category.MACHINE, None, wc, D("0"), rep.machine_hours, rate.machine_rate, machine, {"report": rep.id}),
            (WorkOrderCostLine.Category.OVERHEAD, None, wc, D("0"), rep.labor_hours + rep.machine_hours, rate.overhead_rate, overhead, {"report": rep.id}),
        ]
        if scrap:
            lines.append((WorkOrderCostLine.Category.SCRAP, work_order.item, wc, rep.scrap_quantity, D("0"), scrap_unit, scrap, {"report": rep.id}))
    total = sum(summary.values(), D("0"))
    obj, _ = WorkOrderCost.objects.update_or_create(work_order=work_order, cost_type=WorkOrderCost.CostType.ACTUAL, defaults={
        "cost_version": version, "quantity_basis": quantity, "material_cost": summary["material"], "setup_cost": summary["setup"],
        "labor_cost": summary["labor"], "machine_cost": summary["machine"], "overhead_cost": summary["overhead"],
        "subcontract_cost": summary["subcontract"], "scrap_cost": summary["scrap"], "rework_cost": summary["rework"],
        "total_cost": total, "unit_cost": total / quantity if quantity else D("0"), "calculated_at": timezone.now(),
        "calculation_details": {"basis": "actual_inventory_and_production_transactions"},
    })
    obj.lines.all().delete()
    WorkOrderCostLine.objects.bulk_create([WorkOrderCostLine(work_order_cost=obj, category=c, item=i, work_center=w, reference=str(d.get("report") or d.get("transaction") or ""), quantity=q, hours=h, rate=r, amount=a, details=d) for c,i,w,q,h,r,a,d in lines])
    return obj
