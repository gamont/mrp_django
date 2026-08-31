from datetime import timedelta
from decimal import Decimal
from unittest.mock import patch

import pytest
from django.contrib.auth import get_user_model
from django.db import connection
from django.test.utils import CaptureQueriesContext
from django.urls import reverse
from django.utils import timezone

from apps.common.models import Plant
from apps.integrated_scheduling.models import (
    IntegratedScheduleScenario,
    ProductionSchedulePublication,
    PublishedExecutionSlot,
)
from apps.masterdata.models import Item, WorkCenter
from apps.production.models import WorkOrder, WorkOrderOperation


pytestmark = pytest.mark.django_db


def _make_user():
    return get_user_model().objects.create_user(
        username="nplus1-publication-user",
        password="test-password",
    )


def _make_base_case():
    plant = Plant.objects.create(
        code="N1-PUB",
        name="N+1 Publication",
    )

    item = Item.objects.create(
        code="FG-N1-PUB",
        description="Produto teste publication",
        item_type=Item.ItemType.FINISHED,
    )

    work_center = WorkCenter.objects.create(
        plant=plant,
        code="WC-N1",
        name="Work Center N+1",
        capacity_hours_per_day=Decimal("8"),
        efficiency_percent=Decimal("100"),
    )

    today = timezone.localdate()

    work_order = WorkOrder.objects.create(
        number="OP-N1-PUB",
        plant=plant,
        item=item,
        quantity=Decimal("100"),
        release_date=today,
        due_date=today + timedelta(days=2),
    )

    operation = WorkOrderOperation.objects.create(
        work_order=work_order,
        sequence=10,
        description="Operação N+1",
        work_center=work_center,
    )

    scenario = IntegratedScheduleScenario.objects.create(
        name="Scenario N+1 Publication",
        plant=plant,
        horizon_start=today,
        horizon_end=today + timedelta(days=3),
    )

    return plant, scenario, operation, work_center


def _make_publication(
    *,
    plant,
    scenario,
    operation,
    work_center,
    version,
):
    publication = ProductionSchedulePublication.objects.create(
        plant=plant,
        scenario=scenario,
        version=version,
        status=ProductionSchedulePublication.Status.PUBLISHED,
    )

    start = timezone.now() + timedelta(hours=version)

    PublishedExecutionSlot.objects.create(
        publication=publication,
        operation=operation,
        work_center=work_center,
        planned_start=start,
        planned_end=start + timedelta(hours=1),
    )

    return publication


def _query_count_for_dashboard(client, plant):
    url = reverse("integrated-scheduling:publications")

    with patch(
        "apps.integrated_scheduling.views._plant",
        return_value=plant,
    ):
        with CaptureQueriesContext(connection) as captured:
            response = client.get(url)

    assert response.status_code == 200
    return len(captured)


def test_publication_dashboard_does_not_scale_queries_with_publications(
    client,
):
    user = _make_user()
    client.force_login(user)

    plant, scenario, operation, work_center = _make_base_case()

    _make_publication(
        plant=plant,
        scenario=scenario,
        operation=operation,
        work_center=work_center,
        version=1,
    )

    # Warm-up para eliminar efeitos da primeira requisição.
    _query_count_for_dashboard(client, plant)

    small_queries = _query_count_for_dashboard(client, plant)

    for version in range(2, 21):
        _make_publication(
            plant=plant,
            scenario=scenario,
            operation=operation,
            work_center=work_center,
            version=version,
        )

    large_queries = _query_count_for_dashboard(client, plant)

    print(
        "N+1 publication-dashboard: "
        f"small={small_queries}, large={large_queries}"
    )

    assert large_queries <= small_queries + 3
