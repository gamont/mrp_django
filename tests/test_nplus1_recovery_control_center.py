from datetime import timedelta
from unittest.mock import patch

import pytest
from django.contrib.auth import get_user_model
from django.db import connection
from django.test.utils import CaptureQueriesContext
from django.urls import reverse
from django.utils import timezone

from apps.common.models import Plant
from apps.integrated_scheduling.models import (
    RecoveryPlan,
    ReschedulingTrigger,
)


pytestmark = pytest.mark.django_db


def _make_user():
    return get_user_model().objects.create_user(
        username="nplus1-recovery-user",
        password="test-password",
    )


def _make_trigger(*, plant, suffix):
    trigger = ReschedulingTrigger.objects.create(
        plant=plant,
        trigger_type=ReschedulingTrigger.TriggerType.MANUAL,
        affected_from=timezone.now(),
        idempotency_key=f"nplus1-recovery-{suffix}",
        impact_summary={
            "affected_work_orders": 1,
            "impacted_sales_orders": 1,
        },
        recovery_eta_seconds=60,
    )

    RecoveryPlan.objects.create(
        trigger=trigger,
        name=f"Recovery plan {suffix}",
    )

    return trigger


def _query_count_for_dashboard(client, plant):
    url = reverse("integrated-scheduling:recovery-control-center")

    with patch(
        "apps.integrated_scheduling.views._plant",
        return_value=plant,
    ):
        with CaptureQueriesContext(connection) as captured:
            response = client.get(url)

    assert response.status_code == 200
    return len(captured)


def test_recovery_control_center_does_not_scale_queries_with_triggers(
    client,
):
    user = _make_user()
    client.force_login(user)

    plant = Plant.objects.create(
        code="N1-REC",
        name="N+1 Recovery",
    )

    _make_trigger(
        plant=plant,
        suffix="1",
    )

    # Warm-up para remover efeitos da primeira requisição.
    _query_count_for_dashboard(client, plant)

    small_queries = _query_count_for_dashboard(client, plant)

    for number in range(2, 21):
        _make_trigger(
            plant=plant,
            suffix=str(number),
        )

    large_queries = _query_count_for_dashboard(client, plant)

    print(
        "N+1 recovery-control-center: "
        f"small={small_queries}, large={large_queries}"
    )

    assert large_queries <= small_queries + 3
