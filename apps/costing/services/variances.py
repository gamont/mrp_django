from decimal import Decimal
from django.db import transaction
from apps.costing.models import CostVariance, WorkOrderCost
from apps.production.models import WorkOrder

D = Decimal

MAPPING = {
    CostVariance.VarianceType.MATERIAL_USAGE: "material_cost",
    CostVariance.VarianceType.SETUP: "setup_cost",
    CostVariance.VarianceType.LABOR_EFFICIENCY: "labor_cost",
    CostVariance.VarianceType.MACHINE_EFFICIENCY: "machine_cost",
    CostVariance.VarianceType.OVERHEAD: "overhead_cost",
    CostVariance.VarianceType.SCRAP: "scrap_cost",
    CostVariance.VarianceType.TOTAL: "total_cost",
}

@transaction.atomic
def calculate_variances(work_order: WorkOrder):
    planned = WorkOrderCost.objects.get(work_order=work_order, cost_type=WorkOrderCost.CostType.PLANNED)
    actual = WorkOrderCost.objects.get(work_order=work_order, cost_type=WorkOrderCost.CostType.ACTUAL)
    results = []
    for variance_type, field in MAPPING.items():
        p = getattr(planned, field); a = getattr(actual, field); v = a - p
        obj, _ = CostVariance.objects.update_or_create(work_order=work_order, variance_type=variance_type, defaults={"planned_amount": p, "actual_amount": a, "variance_amount": v, "favorable": v <= 0, "details": {"field": field}})
        results.append(obj)
    return results
