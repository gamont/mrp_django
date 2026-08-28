from datetime import date

import pytest
from django.contrib.auth import get_user_model
from django.db import connection
from django.test.utils import CaptureQueriesContext
from django.urls import reverse
from unittest.mock import patch

from apps.common.models import Plant
from apps.integrated_scheduling.models import (
    MPSOperationalPolicy,
    MPSWeeklyBucket,
    OperationalMPSPublication,
    SAndOPCycle,
)
from apps.masterdata.models import Item

pytestmark = pytest.mark.django_db


def _make_user():
    return get_user_model().objects.create_user(
        username="nplus1-mps-dashboard-user",
        password="test-password",
    )


def _make_publication(*, cycle, policy, item, index):
    publication = OperationalMPSPublication.objects.create(
        cycle=cycle,
        policy=policy,
        as_of_date=date(2026, 8, 1),
        horizon_start=date(2026, 8, 1),
        horizon_end=date(2026, 8, 31),
        source=f"N+1-MPS-{index:03d}",
    )

    MPSWeeklyBucket.objects.create(
        publication=publication,
        item=item,
        bucket_start=date(2026, 8, 1),
        bucket_end=date(2026, 8, 7),
        quantity=100,
        baseline_quantity=100,
    )

    return publication


def _query_count_for_dashboard(client, plant):
    url = reverse(
        "integrated-scheduling:operational-mps-dashboard"
    )

    with patch(
        "apps.integrated_scheduling.views._plant",
        return_value=plant,
    ):
        with CaptureQueriesContext(connection) as captured:
            response = client.get(url)

    assert response.status_code == 200

    return len(captured)


def test_operational_mps_dashboard_query_count_does_not_grow_per_publication(
    client,
):
    user = _make_user()
    client.force_login(user)

    plant = Plant.objects.create(
        code="P-N1-MPS",
        name="N+1 MPS Dashboard Plant",
    )

    item = Item.objects.create(
        code="FG-N1-MPS",
        description="N+1 MPS Finished Good",
        item_type=Item.ItemType.FINISHED,
    )

    policy = MPSOperationalPolicy.objects.create(
        plant=plant,
    )

    cycle = SAndOPCycle.objects.create(
        plant=plant,
        code="SOP-N1-MPS",
        version=1,
        cycle_month=date(2026, 8, 1),
        horizon_start=date(2026, 8, 1),
        horizon_end=date(2026, 8, 31),
        status=SAndOPCycle.Status.APPROVED,
    )

    _make_publication(
        cycle=cycle,
        policy=policy,
        item=item,
        index=1,
    )

    # Warm-up para retirar efeitos de primeira requisição,
    # sessão e carregamento inicial do template.
    _query_count_for_dashboard(client, plant)

    small_queries = _query_count_for_dashboard(
        client,
        plant,
    )

    for index in range(2, 21):
        _make_publication(
            cycle=cycle,
            policy=policy,
            item=item,
            index=index,
        )

    large_queries = _query_count_for_dashboard(
        client,
        plant,
    )

    print(
        f"\nN+1 operational-mps-dashboard: "
        f"small={small_queries}, large={large_queries}"
    )

    assert large_queries <= small_queries + 3, (
        "Possible N+1 detected in operational MPS dashboard: "
        f"1 publication = {small_queries} queries; "
        f"20 publications = {large_queries} queries"
    )
