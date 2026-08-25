import pytest
from decimal import Decimal
from apps.common.models import Plant
from apps.masterdata.models import Item, BOMLine
from apps.costing.models import CostVersion, ItemCost
from apps.costing.services.rollup import run_rollup
@pytest.mark.django_db
def test_multilevel_cost_rollup():
    p=Plant.objects.create(code="SP01",name="Planta")
    raw=Item.objects.create(code="RAW",description="Matéria",item_type="RAW",standard_cost=Decimal("10"))
    fg=Item.objects.create(code="FG",description="Produto",item_type="FINISHED")
    BOMLine.objects.create(parent=fg,component=raw,quantity_per=Decimal("2"))
    v=CostVersion.objects.create(plant=p,code="2026-08",effective_from="2026-08-01")
    run_rollup(v)
    assert ItemCost.objects.get(cost_version=v,item=fg).material_cost == Decimal("20")


@pytest.mark.django_db
def test_planned_actual_and_variances():
    from django.utils import timezone
    from apps.inventory.models import Warehouse, Location, InventoryTransaction
    from apps.masterdata.models import WorkCenter
    from apps.production.models import WorkOrder, WorkOrderMaterial, WorkOrderOperation, ProductionReport
    from apps.costing.models import WorkCenterRate, WorkOrderCost, CostVariance
    from apps.costing.services.work_order_cost import calculate_planned_cost, calculate_actual_cost
    from apps.costing.services.variances import calculate_variances
    p=Plant.objects.create(code="C01",name="Custos")
    raw=Item.objects.create(code="C-RAW",description="Matéria",item_type="RAW",standard_cost=Decimal("5"))
    fg=Item.objects.create(code="C-FG",description="Produto",item_type="FINISHED")
    wc=WorkCenter.objects.create(plant=p,code="WC",name="Centro")
    v=CostVersion.objects.create(plant=p,code="V1",effective_from="2026-01-01",status=CostVersion.Status.ACTIVE)
    ItemCost.objects.create(cost_version=v,item=raw,material_cost=Decimal("5"),total_cost=Decimal("5"))
    WorkCenterRate.objects.create(cost_version=v,work_center=wc,labor_rate=Decimal("20"),machine_rate=Decimal("10"),overhead_rate=Decimal("5"))
    wo=WorkOrder.objects.create(number="OP-C1",plant=p,item=fg,quantity=Decimal("10"),release_date="2026-01-01",due_date="2026-01-02")
    WorkOrderMaterial.objects.create(work_order=wo,item=raw,required_quantity=Decimal("20"),required_date="2026-01-01")
    op=WorkOrderOperation.objects.create(work_order=wo,sequence=10,description="Montar",work_center=wc,run_hours=Decimal("2"))
    wh=Warehouse.objects.create(plant=p,code="W",name="W"); loc=Location.objects.create(warehouse=wh,code="L")
    InventoryTransaction.objects.create(transaction_type=InventoryTransaction.TransactionType.PRODUCTION_ISSUE,item=raw,from_location=loc,quantity=Decimal("22"),reference_type="WORK_ORDER",reference_id=wo.number)
    ProductionReport.objects.create(work_order=wo,operation=op,reported_at=timezone.now(),good_quantity=Decimal("10"),labor_hours=Decimal("3"),machine_hours=Decimal("2"))
    planned=calculate_planned_cost(wo); actual=calculate_actual_cost(wo); variances=calculate_variances(wo)
    assert planned.total_cost > 0 and actual.total_cost > 0
    assert any(v.variance_type == CostVariance.VarianceType.TOTAL for v in variances)
