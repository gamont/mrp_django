from decimal import Decimal
import pytest
from django.utils import timezone

from apps.common.models import Plant
from apps.inventory.models import Location, Warehouse
from apps.masterdata.models import Item
from apps.traceability.models import InventoryLot, LotBalance, LotTransaction, SerialNumber
from apps.traceability.services import install_component, post_lot_transaction, serial_genealogy

pytestmark = pytest.mark.django_db


def test_lot_receipt_and_idempotency():
    plant = Plant.objects.create(code="SP", name="São Paulo")
    item = Item.objects.create(code="CMP", description="Componente", item_type="PURCHASED")
    wh = Warehouse.objects.create(plant=plant, code="MP", name="Matéria-prima")
    loc = Location.objects.create(warehouse=wh, code="A01")
    lot = InventoryLot.objects.create(plant=plant, item=item, lot_number="L001")
    first = post_lot_transaction(transaction_type=LotTransaction.TransactionType.RECEIPT, lot=lot, quantity=Decimal("10"), to_location=loc, idempotency_key="receipt-1")
    second = post_lot_transaction(transaction_type=LotTransaction.TransactionType.RECEIPT, lot=lot, quantity=Decimal("10"), to_location=loc, idempotency_key="receipt-1")
    assert first.pk == second.pk
    assert LotBalance.objects.get(lot=lot, location=loc).on_hand == Decimal("10")


def test_serial_genealogy():
    plant = Plant.objects.create(code="SP", name="São Paulo")
    parent_item = Item.objects.create(code="FG", description="Produto", item_type="MANUFACTURED")
    component_item = Item.objects.create(code="CMP", description="Componente", item_type="PURCHASED")
    parent = SerialNumber.objects.create(plant=plant, item=parent_item, serial_number="FG-001")
    component = SerialNumber.objects.create(plant=plant, item=component_item, serial_number="CMP-001")
    install_component(parent_serial=parent, component_serial=component, installed_at=timezone.now())
    tree = serial_genealogy(parent)
    assert tree["serial_number"] == "FG-001"
    assert tree["components"][0]["serial_number"] == "CMP-001"
