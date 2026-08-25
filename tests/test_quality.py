from datetime import date
from decimal import Decimal
import pytest
from django.contrib.auth import get_user_model
from apps.common.models import Plant
from apps.masterdata.models import Item
from apps.traceability.models import InventoryLot
from apps.quality.models import InspectionCharacteristic, InspectionOrder, InspectionPlan, NonConformance
from apps.quality.services import complete_inspection, record_result, start_inspection

@pytest.mark.django_db
def test_quality_flow_creates_ncr_and_quarantine():
    plant = Plant.objects.create(code="SPQ", name="Qualidade")
    item = Item.objects.create(code="LED-Q", description="LED", item_type="PURCHASED", uom="UN")
    lot = InventoryLot.objects.create(plant=plant, item=item, lot_number="LQ-1", status="QUARANTINE")
    plan = InspectionPlan.objects.create(code="PI-LED", description="Inspeção LED", item=item, source_type="RECEIPT", effective_from=date.today())
    char = InspectionCharacteristic.objects.create(plan=plan, sequence=10, name="Fluxo", data_type="NUMERIC", unit="lm", lower_limit=Decimal("900"), upper_limit=Decimal("1100"))
    order = InspectionOrder.objects.create(plant=plant, plan=plan, item=item, lot=lot, source_type="PURCHASE_ORDER", source_id="OC-1", quantity_received=Decimal("10"))
    start_inspection(order=order)
    result = record_result(order=order, characteristic=char, numeric_value=Decimal("850"))
    assert result.is_conforming is False
    done = complete_inspection(order=order, quantity_approved=Decimal("8"), quantity_rejected=Decimal("2"))
    assert done.status == InspectionOrder.Status.PARTIAL
    lot.refresh_from_db(); assert lot.status == InventoryLot.Status.QUARANTINE
    assert NonConformance.objects.filter(inspection_order=order, quantity_affected=2).exists()
