from datetime import datetime, time, timedelta

import pytest
from django.urls import reverse
from django.utils import timezone

from apps.common.models import Plant
from apps.maintenance.models import MaintenanceAsset, MaintenanceWorkOrder


@pytest.mark.django_db
def test_advanced_planner_groups_orders_by_scheduled_day(
    client,
    django_user_model,
):
    user = django_user_model.objects.create_user(
        username="maintenance-planner-test",
        password="test-password",
    )
    client.force_login(user)

    plant = Plant.objects.create(
        code="MNT-ADV",
        name="Manutenção Advanced Planner",
    )
    asset = MaintenanceAsset.objects.create(
        plant=plant,
        code="MNT-01",
        name="Máquina de teste",
    )

    monday = timezone.localdate()
    monday = monday - timedelta(days=monday.weekday())
    tuesday = monday + timedelta(days=1)

    tz = timezone.get_current_timezone()

    monday_start = timezone.make_aware(
        datetime.combine(monday, time(9, 0)),
        tz,
    )
    monday_end = timezone.make_aware(
        datetime.combine(monday, time(11, 0)),
        tz,
    )
    tuesday_start = timezone.make_aware(
        datetime.combine(tuesday, time(14, 0)),
        tz,
    )
    tuesday_end = timezone.make_aware(
        datetime.combine(tuesday, time(16, 0)),
        tz,
    )

    monday_order = MaintenanceWorkOrder.objects.create(
        plant=plant,
        number="OM-ADV-001",
        asset=asset,
        title="Ordem de segunda-feira",
        scheduled_start=monday_start,
        scheduled_end=monday_end,
    )
    tuesday_order = MaintenanceWorkOrder.objects.create(
        plant=plant,
        number="OM-ADV-002",
        asset=asset,
        title="Ordem de terça-feira",
        scheduled_start=tuesday_start,
        scheduled_end=tuesday_end,
    )

    response = client.get(
        reverse("maintenance:advanced-planner"),
        {
            "plant": plant.pk,
            "week": monday.isoformat(),
        },
    )

    assert response.status_code == 200

    calendar_days = response.context["calendar_days"]

    assert len(calendar_days) == 7
    assert calendar_days[0]["date"] == monday
    assert calendar_days[1]["date"] == tuesday

    assert [wo.pk for wo in calendar_days[0]["orders"]] == [
        monday_order.pk
    ]
    assert [wo.pk for wo in calendar_days[1]["orders"]] == [
        tuesday_order.pk
    ]

    assert monday_order.number in response.content.decode()
    assert tuesday_order.number in response.content.decode()
