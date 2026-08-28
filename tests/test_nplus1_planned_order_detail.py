from datetime import timedelta
from decimal import Decimal

import pytest
from django.contrib.auth import get_user_model
from django.db import connection
from django.test.utils import CaptureQueriesContext
from django.urls import reverse
from django.utils import timezone

from apps.common.models import Plant
from apps.masterdata.models import Item
from apps.planning.models import (
    PeggingRecord,
    PlannedOrder,
    PlanningBucket,
    PlanningMessage,
    PlanningRun,
)

pytestmark = pytest.mark.django_db


def _make_user():
    return get_user_model().objects.create_user(
        username="nplus1-planned-order-user",
        password="test-password",
    )


def _make_case(child_count, *, plant, suffix):
    today = timezone.localdate()

    finished_item = Item.objects.create(
        code=f"FG-N1-{suffix}",
        description=f"Finished good {suffix}",
        item_type=Item.ItemType.FINISHED,
    )

    parent_item = Item.objects.create(
        code=f"PARENT-N1-{suffix}",
        description=f"Parent {suffix}",
        item_type=Item.ItemType.FINISHED,
    )

    top_level_item = Item.objects.create(
        code=f"TOP-N1-{suffix}",
        description=f"Top level {suffix}",
        item_type=Item.ItemType.FINISHED,
    )

    run = PlanningRun.objects.create(
        name=f"N+1 run {suffix}",
        plant=plant,
        horizon_start=today,
        horizon_end=today + timedelta(days=max(child_count, 30)),
    )

    order = PlannedOrder.objects.create(
        planning_run=run,
        item=finished_item,
        order_type=PlannedOrder.OrderType.MAKE,
        quantity=Decimal("100"),
        release_date=today,
        due_date=today + timedelta(days=10),
        status=PlannedOrder.Status.PLANNED,
        source="N+1 TEST",
    )

    for index in range(child_count):
        component = Item.objects.create(
            code=f"COMP-N1-{suffix}-{index}",
            description=f"Component {suffix} {index}",
            item_type=Item.ItemType.PURCHASED,
        )

        PlanningBucket.objects.create(
            planning_run=run,
            item=finished_item,
            bucket_date=today + timedelta(days=index),
            gross_requirements=Decimal("10"),
            scheduled_receipts=Decimal("2"),
            projected_available=Decimal("8"),
            net_requirements=Decimal("2"),
            planned_order_receipts=Decimal("2"),
            planned_order_releases=Decimal("2"),
        )

        PeggingRecord.objects.create(
            planning_run=run,
            component_item=component,
            parent_item=parent_item,
            parent_planned_order=order,
            top_level_item=top_level_item,
            requirement_date=today + timedelta(days=index),
            quantity=Decimal("1"),
        )

        PlanningMessage.objects.create(
            planning_run=run,
            item=finished_item,
            planned_order=order,
            message_type=PlanningMessage.MessageType.RELEASE,
            severity=PlanningMessage.Severity.INFO,
            action_date=today + timedelta(days=index),
            message=f"Test message {suffix} {index}",
        )

    return order


def _query_count_for_detail(client, order):
    url = reverse("ui:planned-order-detail", args=[order.pk])

    with CaptureQueriesContext(connection) as captured:
        response = client.get(url)

    assert response.status_code == 200
    return len(captured)


def test_planned_order_detail_query_count_does_not_grow_with_children(client):
    user = _make_user()
    client.force_login(user)

    plant = Plant.objects.create(
        code="P-N1-PLAN",
        name="N+1 Planning Test Plant",
    )

    small = _make_case(
        1,
        plant=plant,
        suffix="SMALL",
    )

    large = _make_case(
        20,
        plant=plant,
        suffix="LARGE",
    )

    small_queries = _query_count_for_detail(client, small)
    large_queries = _query_count_for_detail(client, large)

    print(
        f"\nN+1 planned-order-detail: "
        f"small={small_queries}, large={large_queries}"
    )

    assert large_queries <= small_queries + 3, (
        f"Possible N+1 detected: "
        f"1 bucket/pegging/message = {small_queries} queries; "
        f"20 buckets/peggings/messages = {large_queries} queries"
    )
