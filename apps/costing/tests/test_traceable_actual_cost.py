from decimal import Decimal
import pytest
from apps.costing.models import CostVersion, ItemCost
from apps.costing.services.actual_traceability import calculate_lot_actual_cost
from apps.traceability.models import InventoryLot, LotBalance

pytestmark = pytest.mark.django_db


def test_lot_actual_cost_falls_back_to_active_standard_cost(plant, item, location):
    version = CostVersion.objects.create(plant=plant, code="T1", effective_from="2026-08-01", status=CostVersion.Status.ACTIVE)
    ItemCost.objects.create(cost_version=version, item=item, total_cost=Decimal("12"))
    lot = InventoryLot.objects.create(plant=plant, item=item, lot_number="L-001")
    LotBalance.objects.create(lot=lot, location=location, on_hand=Decimal("5"), allocated=0)
    result = calculate_lot_actual_cost(lot)
    assert result.quantity_basis == Decimal("5")
    assert result.unit_cost == Decimal("12")
    assert result.total_cost == Decimal("60")
