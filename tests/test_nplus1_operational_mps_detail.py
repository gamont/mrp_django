from datetime import date
from decimal import Decimal

import pytest
from django.contrib.auth import get_user_model
from django.db import connection
from django.test.utils import CaptureQueriesContext
from django.urls import reverse

from apps.common.models import Plant
from apps.integrated_scheduling.models import (
    MPSBucketChangeRequest,
    MPSOperationalPolicy,
    MPSRevision,
    MPSWeeklyBucket,
    OperationalMPSPublication,
    SAndOPCycle,
)
from apps.masterdata.models import Item

pytestmark = pytest.mark.django_db


def _make_user(username):
    return get_user_model().objects.create_user(
        username=username,
        password="test-password",
    )


def _make_base_case():
    plant = Plant.objects.create(
        code="P-N1-DETAIL",
        name="N+1 MPS Detail Plant",
    )

    item = Item.objects.create(
        code="FG-N1-DETAIL",
        description="N+1 MPS Detail Finished Good",
        item_type=Item.ItemType.FINISHED,
    )

    policy = MPSOperationalPolicy.objects.create(
        plant=plant,
    )

    cycle = SAndOPCycle.objects.create(
        plant=plant,
        code="SOP-N1-DETAIL",
        version=1,
        cycle_month=date(2026, 8, 1),
        horizon_start=date(2026, 8, 1),
        horizon_end=date(2026, 8, 31),
        status=SAndOPCycle.Status.APPROVED,
    )

    publication = OperationalMPSPublication.objects.create(
        cycle=cycle,
        policy=policy,
        as_of_date=date(2026, 8, 1),
        horizon_start=date(2026, 8, 1),
        horizon_end=date(2026, 8, 31),
        source="N+1-MPS-DETAIL",
    )

    bucket = MPSWeeklyBucket.objects.create(
        publication=publication,
        item=item,
        bucket_start=date(2026, 8, 1),
        bucket_end=date(2026, 8, 7),
        quantity=Decimal("100"),
        baseline_quantity=Decimal("100"),
    )

    return publication, bucket


def _query_count_for_detail(client, publication):
    url = reverse(
        "integrated-scheduling:operational-mps-detail",
        args=[publication.pk],
    )

    with CaptureQueriesContext(connection) as captured:
        response = client.get(url)

    assert response.status_code == 200

    return len(captured)


def _make_decided_change(
    *,
    publication,
    bucket,
    decided_by,
    index,
):
    return MPSBucketChangeRequest.objects.create(
        publication=publication,
        source_bucket=bucket,
        source_quantity_before=Decimal("100"),
        source_quantity_after=Decimal("99"),
        violation=MPSBucketChangeRequest.Violation.NONE,
        status=MPSBucketChangeRequest.Status.APPROVED,
        reason=f"N+1 change {index}",
        requested_by=decided_by,
        decided_by=decided_by,
    )


def _make_revision(*, publication, number):
    return MPSRevision.objects.create(
        publication=publication,
        number=number,
        kind=MPSRevision.Kind.WORKING,
        status=MPSRevision.Status.DRAFT,
        label=f"N+1 revision {number}",
    )


def test_operational_mps_detail_change_decided_by_does_not_cause_nplus1(
    client,
):
    user = _make_user("nplus1-mps-detail-change-user")
    client.force_login(user)

    publication, bucket = _make_base_case()

    _make_decided_change(
        publication=publication,
        bucket=bucket,
        decided_by=user,
        index=1,
    )

    # Warm-up para retirar efeitos da primeira requisição.
    _query_count_for_detail(client, publication)

    small_queries = _query_count_for_detail(
        client,
        publication,
    )

    for index in range(2, 21):
        _make_decided_change(
            publication=publication,
            bucket=bucket,
            decided_by=user,
            index=index,
        )

    large_queries = _query_count_for_detail(
        client,
        publication,
    )

    print(
        f"\nN+1 operational-mps-detail decided_by: "
        f"small={small_queries}, large={large_queries}"
    )

    assert large_queries <= small_queries + 3, (
        "Possible N+1 detected for MPS change decided_by: "
        f"1 change = {small_queries} queries; "
        f"20 changes = {large_queries} queries"
    )


def test_operational_mps_detail_revision_simulations_do_not_cause_nplus1(
    client,
):
    user = _make_user("nplus1-mps-detail-revision-user")
    client.force_login(user)

    publication, _bucket = _make_base_case()

    _make_revision(
        publication=publication,
        number=1,
    )

    # Warm-up para retirar efeitos da primeira requisição.
    _query_count_for_detail(client, publication)

    small_queries = _query_count_for_detail(
        client,
        publication,
    )

    for number in range(2, 21):
        _make_revision(
            publication=publication,
            number=number,
        )

    large_queries = _query_count_for_detail(
        client,
        publication,
    )

    print(
        f"\nN+1 operational-mps-detail revisions: "
        f"small={small_queries}, large={large_queries}"
    )

    assert large_queries <= small_queries + 3, (
        "Possible N+1 detected for MPS revision simulations: "
        f"1 revision = {small_queries} queries; "
        f"20 revisions = {large_queries} queries"
    )
