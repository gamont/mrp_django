import pytest
from django.contrib.auth import get_user_model

from apps.common.models import Plant
from apps.masterdata.models import Item
from apps.recall.models import RecallCase, RecallCriterion
from apps.recall.services import analyze_recall, approve_recall, execute_recall
from apps.traceability.models import InventoryLot, SerialComponent, SerialNumber


@pytest.mark.django_db
def test_recall_traces_where_used_and_blocks_units():
    user = get_user_model().objects.create_user(username="quality", password="x")
    plant = Plant.objects.create(code="SP01", name="São Paulo")
    component = Item.objects.create(code="LED", description="Módulo LED", item_type="PURCHASED", uom="EA")
    finished = Item.objects.create(code="HEADLAMP", description="Farol", item_type="MANUFACTURED", uom="EA")
    lot = InventoryLot.objects.create(plant=plant, item=component, lot_number="L-001")
    component_serial = SerialNumber.objects.create(plant=plant, item=component, lot=lot, serial_number="LED-001")
    finished_serial = SerialNumber.objects.create(plant=plant, item=finished, serial_number="FAROL-001")
    SerialComponent.objects.create(parent_serial=finished_serial, component_serial=component_serial, installed_at="2026-08-01T10:00:00Z")
    case = RecallCase.objects.create(number="REC-0001", plant=plant, classification="MARKET", title="Falha LED", description="Falha", reason="Fornecedor", opened_by=user)
    RecallCriterion.objects.create(recall_case=case, criterion_type="LOT", lot=lot)

    result = analyze_recall(case=case, actor=user)
    assert result["serials"] == 2
    approve_recall(case=case, actor=user)
    result = execute_recall(case=case, actor=user)
    assert result["serials_blocked"] == 2
    component_serial.refresh_from_db(); finished_serial.refresh_from_db(); lot.refresh_from_db()
    assert component_serial.status == "BLOCKED"
    assert finished_serial.status == "BLOCKED"
    assert lot.status == "BLOCKED"
