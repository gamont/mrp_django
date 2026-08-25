from decimal import Decimal
import pytest
from apps.costing.models import MovingAverageCostBalance
from apps.costing.services.revaluation import revalue_item

pytestmark = pytest.mark.django_db


def test_revaluation_changes_value_not_quantity(plant, item):
    MovingAverageCostBalance.objects.create(plant=plant, item=item, quantity=Decimal("10"), inventory_value=Decimal("50"), average_unit_cost=Decimal("5"))
    obj, created = revalue_item(plant=plant, item=item, new_unit_cost="6", reason="Novo padrão", idempotency_key="reval-test-1")
    bal = MovingAverageCostBalance.objects.get(plant=plant, item=item)
    assert created is True
    assert bal.quantity == Decimal("10")
    assert bal.inventory_value == Decimal("60.0000")
    assert obj.variance_value == Decimal("10.0000")
