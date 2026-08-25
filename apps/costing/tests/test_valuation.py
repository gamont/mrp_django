from decimal import Decimal
from django.contrib.auth import get_user_model
from django.test import TestCase
from django.utils import timezone

from apps.common.models import Plant
from apps.masterdata.models import Item
from apps.inventory.models import Warehouse, Location, StockBalance
from apps.production.models import WorkOrder
from apps.costing.models import CostVersion, ItemCost, AccountingPeriod, WorkOrderCost
from apps.costing.services.valuation import create_inventory_valuation, create_wip_snapshot, close_accounting_period


class CostValuationTests(TestCase):
    def setUp(self):
        self.plant = Plant.objects.create(code="SP01", name="São Paulo")
        self.item = Item.objects.create(code="COMP-1", description="Componente", item_type=Item.ItemType.PURCHASED)
        wh = Warehouse.objects.create(plant=self.plant, code="MP", name="Matéria-prima")
        self.location = Location.objects.create(warehouse=wh, code="A01")
        StockBalance.objects.create(item=self.item, location=self.location, on_hand=Decimal("10"))
        self.version = CostVersion.objects.create(plant=self.plant, code="2026-08", effective_from=timezone.localdate(), status=CostVersion.Status.ACTIVE)
        ItemCost.objects.create(cost_version=self.version, item=self.item, material_cost=Decimal("12.50"), total_cost=Decimal("12.50"))
        self.period = AccountingPeriod.objects.create(plant=self.plant, code="2026-08", start_date=timezone.localdate().replace(day=1), end_date=timezone.localdate(), cost_version=self.version)

    def test_inventory_valuation_standard(self):
        snapshot = create_inventory_valuation(self.period)
        self.assertEqual(snapshot.total_quantity, Decimal("10"))
        self.assertEqual(snapshot.total_value, Decimal("125.00"))
        self.assertEqual(snapshot.lines.count(), 1)

    def test_wip_snapshot_and_period_close(self):
        wo = WorkOrder.objects.create(number="OP-1", plant=self.plant, item=self.item, quantity=Decimal("10"), release_date=timezone.localdate(), due_date=timezone.localdate(), status=WorkOrder.Status.IN_PROGRESS)
        WorkOrderCost.objects.create(work_order=wo, cost_version=self.version, cost_type=WorkOrderCost.CostType.ACTUAL, quantity_basis=Decimal("10"), material_cost=Decimal("50"), total_cost=Decimal("50"), unit_cost=Decimal("5"), calculated_at=timezone.now())
        wip = create_wip_snapshot(self.period)
        self.assertEqual(wip.total_value, Decimal("50"))
        user = get_user_model().objects.create_user(username="controller", password="x")
        period = close_accounting_period(self.period, user)
        self.assertEqual(period.status, AccountingPeriod.Status.CLOSED)
        self.assertEqual(period.closed_by, user)
