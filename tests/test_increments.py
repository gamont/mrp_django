from datetime import date, timedelta
from decimal import Decimal

import pytest
from django.utils import timezone

from apps.common.models import Plant
from apps.demand.models import MasterProductionSchedule
from apps.inventory.models import Location, StockBalance, Warehouse
from apps.masterdata.models import (
    BOMLine,
    Item,
    ItemPlantPolicy,
    ItemSubstitute,
    Routing,
    RoutingOperation,
    Supplier,
    WorkCenter,
)
from apps.planning.capacity import execute_capacity_scenario
from apps.planning.models import CapacityScenario, PlanningChange
from apps.planning.net_change import enqueue_planning_change, execute_net_change_run
from apps.production.models import WorkOrder
from apps.production.services import complete_work_order, release_work_order
from apps.purchasing.models import PurchaseOrder, PurchaseOrderLine
from apps.purchasing.services import receive_purchase_order_line


@pytest.mark.django_db(transaction=True)
def test_purchase_receipt_is_idempotent_and_closes_order():
    plant = Plant.objects.create(code="P01", name="Planta")
    warehouse = Warehouse.objects.create(plant=plant, code="MP", name="Matéria-prima")
    location = Location.objects.create(warehouse=warehouse, code="A1")
    item = Item.objects.create(code="COMP", description="Componente", item_type=Item.ItemType.PURCHASED)
    supplier = Supplier.objects.create(code="F01", name="Fornecedor")
    order = PurchaseOrder.objects.create(
        number="OC-1",
        plant=plant,
        supplier=supplier,
        order_date=timezone.localdate(),
        expected_date=timezone.localdate(),
        status=PurchaseOrder.Status.RELEASED,
    )
    line = PurchaseOrderLine.objects.create(
        purchase_order=order,
        line_number=10,
        item=item,
        quantity=Decimal("10"),
        expected_date=timezone.localdate(),
    )

    first, created = receive_purchase_order_line(
        line=line,
        quantity=Decimal("5"),
        destination_location=location,
        receipt_number="REC-1",
        idempotency_key="receipt-1",
    )
    repeated, repeated_created = receive_purchase_order_line(
        line=line,
        quantity=Decimal("5"),
        destination_location=location,
        receipt_number="REC-1",
        idempotency_key="receipt-1",
    )

    assert created is True
    assert repeated_created is False
    assert repeated.pk == first.pk
    line.refresh_from_db()
    order.refresh_from_db()
    assert line.received_quantity == Decimal("5.0000")
    assert order.status == PurchaseOrder.Status.PARTIAL
    assert StockBalance.objects.get(item=item, location=location).on_hand == Decimal("5.0000")

    receive_purchase_order_line(
        line=line,
        quantity=Decimal("5"),
        destination_location=location,
        receipt_number="REC-2",
        idempotency_key="receipt-2",
    )
    order.refresh_from_db()
    assert order.status == PurchaseOrder.Status.COMPLETED
    assert StockBalance.objects.get(item=item, location=location).on_hand == Decimal("10.0000")


@pytest.mark.django_db(transaction=True)
def test_work_order_close_backflushes_substitute_and_receives_finished_item():
    plant = Plant.objects.create(code="P02", name="Planta")
    warehouse = Warehouse.objects.create(plant=plant, code="GERAL", name="Geral")
    location = Location.objects.create(warehouse=warehouse, code="A1")
    parent = Item.objects.create(code="PA", description="Produto", item_type=Item.ItemType.FINISHED)
    component = Item.objects.create(code="C1", description="Componente", item_type=Item.ItemType.PURCHASED)
    substitute = Item.objects.create(code="C1-ALT", description="Alternativo", item_type=Item.ItemType.PURCHASED)
    BOMLine.objects.create(parent=parent, component=component, sequence=10, quantity_per=Decimal("2"))
    ItemSubstitute.objects.create(
        plant=plant,
        item=component,
        substitute_item=substitute,
        substitute_quantity_per_primary=Decimal("1"),
    )
    StockBalance.objects.create(item=component, location=location, on_hand=Decimal("0"))
    StockBalance.objects.create(item=substitute, location=location, on_hand=Decimal("10"))

    order = WorkOrder.objects.create(
        number="OP-1",
        plant=plant,
        item=parent,
        quantity=Decimal("5"),
        release_date=timezone.localdate(),
        due_date=timezone.localdate() + timedelta(days=2),
    )
    release_work_order(order)
    completion, created = complete_work_order(
        work_order=order,
        good_quantity=Decimal("5"),
        destination_location=location,
        idempotency_key="completion-1",
    )
    repeated, repeated_created = complete_work_order(
        work_order=order,
        good_quantity=Decimal("5"),
        destination_location=location,
        idempotency_key="completion-1",
    )

    assert created is True
    assert repeated_created is False
    assert repeated.pk == completion.pk
    order.refresh_from_db()
    assert order.status == WorkOrder.Status.CLOSED
    assert order.completed_quantity == Decimal("5.0000")
    assert StockBalance.objects.get(item=substitute, location=location).on_hand == Decimal("0.0000")
    assert StockBalance.objects.get(item=parent, location=location).on_hand == Decimal("5.0000")


@pytest.mark.django_db(transaction=True)
def test_ctp_distributes_load_and_returns_promised_date():
    plant = Plant.objects.create(code="P03", name="Planta")
    item = Item.objects.create(code="PA2", description="Produto 2", item_type=Item.ItemType.FINISHED)
    center = WorkCenter.objects.create(
        plant=plant,
        code="MONT",
        name="Montagem",
        capacity_hours_per_day=Decimal("8"),
        efficiency_percent=Decimal("100"),
    )
    routing = Routing.objects.create(plant=plant, item=item, code="STD", version=1, is_primary=True)
    RoutingOperation.objects.create(
        routing=routing,
        sequence=10,
        description="Montar",
        work_center=center,
        run_hours_per_unit=Decimal("1"),
    )
    release = date(2026, 8, 3)  # segunda-feira
    scenario = CapacityScenario.objects.create(
        name="CTP teste",
        scenario_type=CapacityScenario.ScenarioType.CTP,
        plant=plant,
        item=item,
        quantity=Decimal("10"),
        requested_release_date=release,
        requested_due_date=release,
        parameters={"include_open_orders": False},
    )

    execute_capacity_scenario(scenario)
    scenario.refresh_from_db()
    assert scenario.promised_date == date(2026, 8, 4)
    assert scenario.feasible is False
    assert scenario.allocations.count() == 2


@pytest.mark.django_db(transaction=True)
def test_net_change_expands_component_to_parent_network():
    today = timezone.localdate()
    plant = Plant.objects.create(code="P04", name="Planta")
    parent = Item.objects.create(code="TOP", description="Topo", item_type=Item.ItemType.FINISHED)
    component = Item.objects.create(code="CMP", description="Componente", item_type=Item.ItemType.PURCHASED)
    ItemPlantPolicy.objects.create(
        plant=plant,
        item=parent,
        source_type=ItemPlantPolicy.SourceType.MAKE,
        lead_time_days=1,
    )
    ItemPlantPolicy.objects.create(
        plant=plant,
        item=component,
        source_type=ItemPlantPolicy.SourceType.BUY,
        lead_time_days=1,
    )
    BOMLine.objects.create(parent=parent, component=component, sequence=10, quantity_per=Decimal("1"))
    MasterProductionSchedule.objects.create(
        plant=plant,
        item=parent,
        due_date=today + timedelta(days=10),
        quantity=Decimal("3"),
        source="TEST",
        status=MasterProductionSchedule.Status.FIRM,
    )
    change, _ = enqueue_planning_change(
        plant=plant,
        item=component,
        change_type=PlanningChange.ChangeType.STOCK,
        source_type="TEST",
        source_id="1",
        idempotency_key="net-change-test-1",
    )

    run = execute_net_change_run(
        plant=plant,
        horizon_start=today,
        horizon_end=today + timedelta(days=30),
    )
    change.refresh_from_db()
    assert change.status == PlanningChange.Status.PROCESSED
    assert change.planning_run_id == run.pk
    assert run.planned_orders.filter(item=parent).exists()
    assert run.planned_orders.filter(item=component).exists()
