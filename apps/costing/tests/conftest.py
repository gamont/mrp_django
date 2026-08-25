import pytest

from apps.common.models import Plant
from apps.inventory.models import Location, Warehouse
from apps.masterdata.models import Item


@pytest.fixture
def plant(db):
    return Plant.objects.create(
        code="COST",
        name="Planta de Testes de Custos",
    )


@pytest.fixture
def item(db):
    return Item.objects.create(
        code="ITEM-COST",
        description="Item de testes de custos",
        item_type=Item.ItemType.PURCHASED,
        uom="UN",
    )


@pytest.fixture
def warehouse(db, plant):
    return Warehouse.objects.create(
        plant=plant,
        code="WH-COST",
        name="Armazém de Testes de Custos",
    )


@pytest.fixture
def location(db, warehouse):
    return Location.objects.create(
        warehouse=warehouse,
        code="LOC-COST",
        description="Local de testes de custos",
    )
