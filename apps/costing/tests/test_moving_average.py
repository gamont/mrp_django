from decimal import Decimal
from django.test import TestCase

from apps.common.models import Plant
from apps.masterdata.models import Item
from apps.inventory.models import Warehouse, Location, InventoryTransaction
from apps.costing.models import MovingAverageCostBalance
from apps.costing.services.moving_average import post_moving_average_cost


class MovingAverageCostTests(TestCase):
    def setUp(self):
        self.plant = Plant.objects.create(code="SP-MA", name="Planta custo médio")
        self.item = Item.objects.create(code="MP-MA", description="Matéria-prima", item_type=Item.ItemType.PURCHASED)
        warehouse = Warehouse.objects.create(plant=self.plant, code="MP", name="Matéria-prima")
        self.location = Location.objects.create(warehouse=warehouse, code="A01")

    def test_receipts_recalculate_average_and_issue_keeps_average(self):
        receipt1 = InventoryTransaction.objects.create(
            transaction_type=InventoryTransaction.TransactionType.RECEIPT,
            item=self.item, to_location=self.location, quantity=Decimal("10"),
        )
        post_moving_average_cost(receipt1, Decimal("5"))
        receipt2 = InventoryTransaction.objects.create(
            transaction_type=InventoryTransaction.TransactionType.RECEIPT,
            item=self.item, to_location=self.location, quantity=Decimal("10"),
        )
        post_moving_average_cost(receipt2, Decimal("7"))
        balance = MovingAverageCostBalance.objects.get(plant=self.plant, item=self.item)
        self.assertEqual(balance.average_unit_cost, Decimal("6"))

        issue = InventoryTransaction.objects.create(
            transaction_type=InventoryTransaction.TransactionType.ISSUE,
            item=self.item, from_location=self.location, quantity=Decimal("5"),
        )
        movement, _ = post_moving_average_cost(issue)
        balance.refresh_from_db()
        self.assertEqual(movement.unit_cost, Decimal("6"))
        self.assertEqual(balance.quantity, Decimal("15"))
        self.assertEqual(balance.inventory_value, Decimal("90"))
