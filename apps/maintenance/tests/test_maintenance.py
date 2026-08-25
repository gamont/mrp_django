from datetime import timedelta
from decimal import Decimal

import pytest
from django.contrib.auth import get_user_model
from django.utils import timezone

from apps.common.models import Plant
from apps.inventory.models import Location, StockBalance, Warehouse
from apps.maintenance.models import MaintenanceAsset, MaintenancePart, MaintenancePlan, MaintenanceWorkOrder
from apps.maintenance.services import complete_work_order, generate_preventive_orders, issue_maintenance_part, start_work_order
from apps.masterdata.models import Item, WorkCenter
from apps.shopfloor.models import Machine

pytestmark = pytest.mark.django_db


def base_data():
    plant = Plant.objects.create(code="SP01", name="São Paulo")
    wc = WorkCenter.objects.create(plant=plant, code="MONT", name="Montagem", capacity_hours_per_day=8)
    machine = Machine.objects.create(plant=plant, work_center=wc, code="M01", name="Máquina 01")
    asset = MaintenanceAsset.objects.create(plant=plant, code="M01", name="Máquina 01", machine=machine, work_center=wc)
    return plant, wc, machine, asset


def test_generate_start_and_complete_preventive_order():
    plant, _, machine, asset = base_data()
    plan = MaintenancePlan.objects.create(
        asset=asset, code="P30", title="Preventiva mensal", strategy=MaintenancePlan.Strategy.CALENDAR,
        interval_days=30, next_due_date=timezone.localdate(), planned_duration_hours=Decimal("2"),
    )
    created = generate_preventive_orders(plant=plant)
    assert len(created) == 1
    wo = created[0]
    wo = start_work_order(work_order=wo)
    machine.refresh_from_db()
    assert wo.status == MaintenanceWorkOrder.Status.IN_PROGRESS
    assert machine.status == Machine.Status.PREVENTIVE
    assert wo.downtime_event.reason.category == "PLANNED"

    wo = complete_work_order(work_order=wo, meter_value=Decimal("1250"), completion_notes="Executada")
    machine.refresh_from_db(); plan.refresh_from_db(); wo.downtime_event.refresh_from_db()
    assert wo.status == MaintenanceWorkOrder.Status.COMPLETED
    assert machine.status == Machine.Status.IDLE
    assert wo.downtime_event.ended_at is not None
    assert plan.next_due_date == timezone.localdate() + timedelta(days=30)
    assert wo.meter_at_completion == Decimal("1250")


def test_issue_spare_part_posts_inventory():
    plant, _, _, asset = base_data()
    item = Item.objects.create(code="ROL-01", description="Rolamento", item_type=Item.ItemType.PURCHASED)
    wh = Warehouse.objects.create(plant=plant, code="MP", name="Matéria prima")
    loc = Location.objects.create(warehouse=wh, code="A01")
    StockBalance.objects.create(item=item, location=loc, on_hand=Decimal("10"), allocated=0)
    wo = MaintenanceWorkOrder.objects.create(plant=plant, number="OM-2026-00001", asset=asset, order_type=MaintenanceWorkOrder.OrderType.CORRECTIVE, title="Troca rolamento")
    part = MaintenancePart.objects.create(work_order=wo, item=item, planned_quantity=Decimal("2"))

    issue_maintenance_part(part=part, location=loc, quantity=Decimal("2"), idempotency_key="maint-test-1")
    part.refresh_from_db(); balance = StockBalance.objects.get(item=item, location=loc)
    assert part.issued_quantity == Decimal("2")
    assert balance.on_hand == Decimal("8")

    issue_maintenance_part(part=part, location=loc, quantity=Decimal("2"), idempotency_key="maint-test-1")
    part.refresh_from_db(); balance.refresh_from_db()
    assert part.issued_quantity == Decimal("2")
    assert balance.on_hand == Decimal("8")
