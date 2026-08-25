from decimal import Decimal

import pytest
from django.contrib.auth import get_user_model
from django.urls import reverse
from django.utils import timezone

from apps.common.models import Plant
from apps.inventory.models import Location, Warehouse
from apps.masterdata.models import Item, WorkCenter
from apps.production.models import WorkOrder, WorkOrderMaterial, WorkOrderOperation
from apps.quality.models import InspectionCharacteristic, InspectionOrder, InspectionPlan


def _superuser(username):
    return get_user_model().objects.create_superuser(
        username=username,
        email=f"{username}@example.com",
        password="test12345",
    )


def _item(code):
    return Item.objects.create(
        code=code,
        description=code,
        item_type=Item.ItemType.MANUFACTURED,
        uom="UN",
    )


@pytest.mark.django_db
def test_operation_action_via_htmx_updates_detail(client):
    user = _superuser("operator-053")
    plant = Plant.objects.create(code="P053", name="Planta 053")
    item = _item("PA-053")
    wc = WorkCenter.objects.create(plant=plant, code="MONT", name="Montagem")
    order = WorkOrder.objects.create(
        number="OP-053-001",
        plant=plant,
        item=item,
        quantity=Decimal("10"),
        release_date=timezone.localdate(),
        due_date=timezone.localdate(),
        status=WorkOrder.Status.RELEASED,
    )
    operation = WorkOrderOperation.objects.create(
        work_order=order,
        sequence=10,
        description="Montar",
        work_center=wc,
        status=WorkOrderOperation.Status.READY,
    )
    client.force_login(user)
    session = client.session
    session["ui_plant_id"] = plant.pk
    session.save()

    response = client.post(
        reverse("ui:work-order-operation-action", args=[order.pk, operation.pk]),
        {"action": "RUN"},
        HTTP_HX_REQUEST="true",
    )
    operation.refresh_from_db()
    order.refresh_from_db()
    assert response.status_code == 200
    assert b'id="detail-content"' in response.content
    assert operation.status == WorkOrderOperation.Status.RUNNING
    assert order.status == WorkOrder.Status.IN_PROGRESS


@pytest.mark.django_db
def test_operation_report_completes_operation_and_releases_next(client):
    user = _superuser("reporter-053")
    plant = Plant.objects.create(code="P054", name="Planta 054")
    item = _item("PA-054")
    wc = WorkCenter.objects.create(plant=plant, code="TEST", name="Teste")
    order = WorkOrder.objects.create(
        number="OP-053-002",
        plant=plant,
        item=item,
        quantity=Decimal("20"),
        release_date=timezone.localdate(),
        due_date=timezone.localdate(),
        status=WorkOrder.Status.IN_PROGRESS,
    )
    op1 = WorkOrderOperation.objects.create(work_order=order, sequence=10, description="A", work_center=wc, status=WorkOrderOperation.Status.RUNNING)
    op2 = WorkOrderOperation.objects.create(work_order=order, sequence=20, description="B", work_center=wc, status=WorkOrderOperation.Status.PENDING)
    client.force_login(user)
    session = client.session
    session["ui_plant_id"] = plant.pk
    session.save()

    response = client.post(
        reverse("ui:report-work-order-operation", args=[order.pk, op1.pk]),
        {"good_quantity": "5", "scrap_quantity": "1", "labor_hours": "2.5", "machine_hours": "2.0"},
        HTTP_HX_REQUEST="true",
    )
    op1.refresh_from_db(); op2.refresh_from_db()
    assert response.status_code == 200
    assert op1.status == WorkOrderOperation.Status.COMPLETED
    assert op2.status == WorkOrderOperation.Status.READY
    assert order.reports.filter(operation=op1, good_quantity=Decimal("5")).exists()


@pytest.mark.django_db
def test_quality_result_entry_via_htmx(client):
    user = _superuser("quality-053")
    plant = Plant.objects.create(code="Q053", name="Qualidade 053")
    item = _item("LED-Q053")
    plan = InspectionPlan.objects.create(
        code="PLAN-Q053",
        description="Plano",
        item=item,
        source_type=InspectionPlan.SourceType.STOCK,
        effective_from=timezone.localdate(),
    )
    characteristic = InspectionCharacteristic.objects.create(
        plan=plan,
        sequence=10,
        name="Tensão",
        data_type=InspectionCharacteristic.DataType.NUMERIC,
        lower_limit=Decimal("11.5"),
        target_value=Decimal("12.0"),
        upper_limit=Decimal("12.5"),
    )
    inspection = InspectionOrder.objects.create(
        plant=plant,
        plan=plan,
        item=item,
        source_type="STOCK",
        source_id="COUNT-1",
        quantity_received=Decimal("10"),
    )
    client.force_login(user)
    session = client.session
    session["ui_plant_id"] = plant.pk
    session.save()

    response = client.post(
        reverse("ui:record-inspection-result", args=[inspection.pk, characteristic.pk]),
        {"sample_number": "1", "numeric_value": "12.1"},
        HTTP_HX_REQUEST="true",
    )
    inspection.refresh_from_db()
    result = inspection.results.get(characteristic=characteristic, sample_number=1)
    assert response.status_code == 200
    assert result.is_conforming is True
    assert inspection.status == InspectionOrder.Status.IN_PROGRESS


@pytest.mark.django_db
def test_manual_issue_ui_calls_domain_service(client, monkeypatch):
    user = _superuser("store-053")
    plant = Plant.objects.create(code="S053", name="Estoque 053")
    parent = _item("PA-S053")
    component = _item("CP-S053")
    warehouse = Warehouse.objects.create(plant=plant, code="MP", name="Matéria-prima")
    location = Location.objects.create(warehouse=warehouse, code="A01")
    order = WorkOrder.objects.create(
        number="OP-053-003",
        plant=plant,
        item=parent,
        quantity=Decimal("10"),
        release_date=timezone.localdate(),
        due_date=timezone.localdate(),
        status=WorkOrder.Status.RELEASED,
    )
    material = WorkOrderMaterial.objects.create(
        work_order=order,
        item=component,
        required_quantity=Decimal("10"),
        required_date=timezone.localdate(),
    )
    called = {}
    def fake_issue(**kwargs):
        called.update(kwargs)
        return object()
    monkeypatch.setattr("apps.ui.views.issue_work_order_material", fake_issue)
    client.force_login(user)
    session = client.session
    session["ui_plant_id"] = plant.pk
    session.save()

    response = client.post(
        reverse("ui:issue-work-order-material", args=[order.pk, material.pk]),
        {"actual_item": component.pk, "source_location": location.pk, "actual_quantity": "2.5", "idempotency_key": "test-ui-issue-053"},
        HTTP_HX_REQUEST="true",
    )
    assert response.status_code == 200
    assert called["material"].pk == material.pk
    assert called["actual_item"].pk == component.pk
    assert called["actual_quantity"] == Decimal("2.5")
