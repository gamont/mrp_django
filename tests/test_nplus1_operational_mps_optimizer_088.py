from datetime import timedelta

import pytest
from django.contrib.auth import get_user_model
from django.db import connection
from django.test.utils import CaptureQueriesContext
from django.urls import reverse
from django.utils import timezone

from apps.common.models import Plant
from apps.masterdata.models import Item, Supplier
from apps.integrated_scheduling.models import (
    MPSOperationalPolicy,
    MPSRevision,
    MPSRevisionOptimizationAction,
    MPSRevisionOptimizationCandidate,
    MPSRevisionOptimizationRun,
    OperationalMPSPublication,
    SAndOPCycle,
)


pytestmark = pytest.mark.django_db


def _make_user():
    return get_user_model().objects.create_user(
        username="nplus1-mps-optimizer-user",
        password="test-password",
    )


def _make_candidate(*, optimization_run, item, supplier, number):
    candidate = MPSRevisionOptimizationCandidate.objects.create(
        optimization_run=optimization_run,
        strategy=MPSRevisionOptimizationCandidate.Strategy.SHIFT_LATER,
        name=f"Candidate {number}",
        rank=number,
        metrics={
            "financially_feasible": True,
            "peak_working_capital_need": 100,
            "interest_cost": 10,
            "rccp_overload_hours": 0,
            "purchase_spend": 50,
        },
    )

    MPSRevisionOptimizationAction.objects.create(
        candidate=candidate,
        action_type="SHIFT",
        item=item,
        supplier_to=supplier,
        quantity=10,
    )

    return candidate


def _query_count_for_report(client, publication, optimization_run):
    url = reverse(
        "integrated-scheduling:operational-mps-optimizer-report-088",
        kwargs={
            "pk": publication.pk,
            "run_id": optimization_run.pk,
        },
    )

    with CaptureQueriesContext(connection) as captured:
        response = client.get(url)

    assert response.status_code == 200
    return len(captured)


def test_operational_mps_optimizer_report_does_not_scale_queries_with_actions(
    client,
):
    user = _make_user()
    client.force_login(user)

    plant = Plant.objects.create(
        code="N1-MPS-OPT",
        name="N+1 MPS Optimizer",
    )

    today = timezone.localdate()
    horizon_end = today + timedelta(days=84)

    cycle = SAndOPCycle.objects.create(
        plant=plant,
        code="N1-MPS-OPT",
        cycle_month=today.replace(day=1),
        horizon_start=today,
        horizon_end=horizon_end,
    )

    policy = MPSOperationalPolicy.objects.create(
        plant=plant,
    )

    publication = OperationalMPSPublication.objects.create(
        cycle=cycle,
        policy=policy,
        horizon_start=today,
        horizon_end=horizon_end,
        source="N1-MPS-OPT",
    )

    baseline_revision = MPSRevision.objects.create(
        publication=publication,
        number=1,
        kind=MPSRevision.Kind.BASELINE,
    )

    revision = MPSRevision.objects.create(
        publication=publication,
        number=2,
        parent=baseline_revision,
        kind=MPSRevision.Kind.WORKING,
    )

    optimization_run = MPSRevisionOptimizationRun.objects.create(
        revision=revision,
        compare_revision=baseline_revision,
        status=MPSRevisionOptimizationRun.Status.COMPLETED,
        summary={
            "objective": "N+1 regression test",
            "warning": "",
        },
    )

    item = Item.objects.create(
        code="N1-MPS-ITEM",
        description="N+1 optimizer item",
        uom="EA",
    )

    supplier = Supplier.objects.create(
        code="N1-MPS-SUP",
        name="N+1 optimizer supplier",
    )

    _make_candidate(
        optimization_run=optimization_run,
        item=item,
        supplier=supplier,
        number=1,
    )

    # Warm-up para remover efeitos da primeira requisição.
    _query_count_for_report(
        client,
        publication,
        optimization_run,
    )

    small_queries = _query_count_for_report(
        client,
        publication,
        optimization_run,
    )

    for number in range(2, 21):
        _make_candidate(
            optimization_run=optimization_run,
            item=item,
            supplier=supplier,
            number=number,
        )

    large_queries = _query_count_for_report(
        client,
        publication,
        optimization_run,
    )

    print(
        "N+1 operational-mps-optimizer-088: "
        f"small={small_queries}, large={large_queries}"
    )

    assert large_queries <= small_queries + 3
