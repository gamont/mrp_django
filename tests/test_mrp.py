from datetime import timedelta
from decimal import Decimal
import pytest
from django.utils import timezone

from apps.common.models import Plant
from apps.demand.models import MasterProductionSchedule
from apps.masterdata.models import BOMLine, Item, ItemPlantPolicy
from apps.planning.models import PlannedOrder, PlanningRun
from apps.planning.services import execute_planning_run


@pytest.mark.django_db
def test_mrp_explodes_bom_and_creates_pegging():
    today = timezone.localdate()
    plant = Plant.objects.create(code="T01", name="Teste")
    parent = Item.objects.create(code="PA", description="Produto A", item_type=Item.ItemType.FINISHED)
    component = Item.objects.create(code="CB", description="Componente B", item_type=Item.ItemType.PURCHASED)
    ItemPlantPolicy.objects.create(
        plant=plant,
        item=parent,
        source_type=ItemPlantPolicy.SourceType.MAKE,
        lead_time_days=2,
    )
    ItemPlantPolicy.objects.create(
        plant=plant,
        item=component,
        source_type=ItemPlantPolicy.SourceType.BUY,
        lead_time_days=3,
    )
    BOMLine.objects.create(parent=parent, component=component, sequence=10, quantity_per=2)
    MasterProductionSchedule.objects.create(
        plant=plant,
        item=parent,
        due_date=today + timedelta(days=15),
        quantity=10,
        source="TEST",
        status=MasterProductionSchedule.Status.FIRM,
    )
    run = PlanningRun.objects.create(
        name="Teste",
        plant=plant,
        horizon_start=today,
        horizon_end=today + timedelta(days=30),
    )

    execute_planning_run(run)

    parent_order = PlannedOrder.objects.get(planning_run=run, item=parent)
    component_order = PlannedOrder.objects.get(planning_run=run, item=component)
    assert parent_order.quantity == Decimal("10.0000")
    assert component_order.quantity == Decimal("20.0000")
    assert run.pegging_records.filter(component_item=component, parent_item=parent).exists()
