from decimal import Decimal

import pytest
from django.contrib.auth import get_user_model
from django.urls import reverse
from django.utils import timezone

from apps.common.models import Plant
from apps.masterdata.models import Item
from apps.production.models import WorkOrder, WorkOrderMaterial, WorkOrderOperation
from apps.masterdata.models import WorkCenter


pytestmark = pytest.mark.django_db


def _make_user():
    User = get_user_model()
    user = User.objects.create_user(
        username="nplus1-user",
        password="test-pass",
    )
    user.is_superuser = True
    user.is_staff = True
    user.save(update_fields=["is_superuser", "is_staff"])
    return user


def _make_order(child_count, *, plant, work_center):
    finished_item = Item.objects.create(
        code=f"FG-{child_count}",
        description=f"Finished good {child_count}",
        item_type=Item.ItemType.FINISHED,
    )

    order = WorkOrder.objects.create(
        number=f"OP-N1-{child_count}",
        plant=plant,
        item=finished_item,
        quantity=Decimal("100"),
        release_date=timezone.localdate(),
        due_date=timezone.localdate(),
    )

    for index in range(child_count):
        component = Item.objects.create(
            code=f"COMP-{child_count}-{index}",
            description=f"Component {index}",
            item_type=Item.ItemType.PURCHASED,
        )

        WorkOrderMaterial.objects.create(
            work_order=order,
            item=component,
            required_quantity=Decimal("1"),
            issued_quantity=Decimal("0"),
            required_date=timezone.localdate(),
        )

        WorkOrderOperation.objects.create(
            work_order=order,
            sequence=(index + 1) * 10,
            description=f"Operation {index}",
            work_center=work_center,
        )

    return order

def _query_count_for_detail(client, order):
    from django.db import connection
    from django.test.utils import CaptureQueriesContext

    url = reverse("ui:work-order-detail", args=[order.pk])

    with CaptureQueriesContext(connection) as captured:
        response = client.get(url)

    assert response.status_code == 200
    return len(captured)


def test_work_order_detail_query_count_does_not_grow_with_children(client):
    user = _make_user()
    client.force_login(user)

    plant = Plant.objects.create(
        code="P-N1",
        name="N+1 Test Plant",
    )

    work_center = WorkCenter.objects.create(
        plant=plant,
        code="WC-N1",
        name="N+1 Work Center",
        capacity_hours_per_day=Decimal("8"),
    )

    small = _make_order(
        1,
        plant=plant,
        work_center=work_center,
    )

    large = _make_order(
        20,
        plant=plant,
        work_center=work_center,
    )

    small_queries = _query_count_for_detail(client, small)
    large_queries = _query_count_for_detail(client, large)

    print(
        f"\nN+1 work-order-detail: "
        f"small={small_queries}, large={large_queries}"
    )

    assert large_queries <= small_queries + 3, (
        f"Possible N+1 detected: "
        f"1 material/op = {small_queries} queries; "
        f"20 materials/ops = {large_queries} queries"
    )

