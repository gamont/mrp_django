from decimal import Decimal
import pytest
from apps.costing.models import MovingAverageCostBalance
from apps.costing.services.reconciliation import reconcile_inventory
from apps.inventory.models import StockBalance

pytestmark = pytest.mark.django_db


def test_reconciliation_detects_quantity_difference(plant, item, location):
    StockBalance.objects.create(item=item, location=location, on_hand=Decimal("10"), allocated=0)
    MovingAverageCostBalance.objects.create(plant=plant, item=item, quantity=Decimal("9"), inventory_value=Decimal("45"), average_unit_cost=Decimal("5"))
    run = reconcile_inventory(plant=plant)
    line = run.lines.get(item=item)
    assert line.quantity_variance == Decimal("1")
    assert line.value_variance == Decimal("5")
