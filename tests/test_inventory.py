from decimal import Decimal
import pytest
from apps.common.models import Plant
from apps.inventory.models import InventoryTransaction, Location, StockBalance, Warehouse
from apps.inventory.services import post_inventory_transaction
from apps.masterdata.models import Item


@pytest.mark.django_db
def test_inventory_receipt_updates_balance():
    plant = Plant.objects.create(code="T02", name="Teste estoque")
    warehouse = Warehouse.objects.create(plant=plant, code="MP", name="MP")
    location = Location.objects.create(warehouse=warehouse, code="A1")
    item = Item.objects.create(code="X", description="Item X", item_type=Item.ItemType.PURCHASED)
    tx = InventoryTransaction(
        transaction_type=InventoryTransaction.TransactionType.RECEIPT,
        item=item,
        to_location=location,
        quantity=Decimal("12.5"),
    )
    post_inventory_transaction(tx)
    balance = StockBalance.objects.get(item=item, location=location)
    assert balance.on_hand == Decimal("12.5000")
