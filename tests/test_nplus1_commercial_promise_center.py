from datetime import date
from decimal import Decimal
from unittest.mock import patch

import pytest
from django.contrib.auth import get_user_model
from django.db import connection
from django.test.utils import CaptureQueriesContext
from django.urls import reverse

from apps.common.models import Plant
from apps.demand.models import SalesOrder, SalesOrderLine
from apps.integrated_scheduling.models import (
    CustomerPromiseResponse,
    SalesOrderPromise,
)
from apps.masterdata.models import Item


pytestmark = pytest.mark.django_db


def _make_user():
    return get_user_model().objects.create_user(
        username="nplus1-commercial-promise-user",
        password="test-password",
    )


def _make_base_case():
    plant = Plant.objects.create(
        code="N1-CP",
        name="N+1 Commercial Promise",
    )

    item = Item.objects.create(
        code="FG-N1-CP",
        description="Produto teste N+1",
        item_type=Item.ItemType.FINISHED,
    )

    order = SalesOrder.objects.create(
        number="SO-N1-CP",
        plant=plant,
        customer_code="C-N1",
        customer_name="Cliente N+1",
        order_date=date(2026, 8, 1),
        requested_date=date(2026, 8, 20),
        status=SalesOrder.Status.CONFIRMED,
    )

    line = SalesOrderLine.objects.create(
        sales_order=order,
        line_number=10,
        item=item,
        quantity=Decimal("100"),
        requested_date=date(2026, 8, 20),
    )

    return plant, line


def _make_promise(line, suffix):
    promise = SalesOrderPromise.objects.create(
        sales_order_line=line,
        source=SalesOrderPromise.Source.MANUAL,
        proposed_date=date(2026, 8, 20),
        quantity=Decimal("10"),
        status=SalesOrderPromise.Status.APPROVED,
        rationale=f"Promise {suffix}",
    )

    CustomerPromiseResponse.objects.create(
        promise=promise,
        response=CustomerPromiseResponse.Response.ACCEPTED,
        confirmed_date=date(2026, 8, 20),
        notes=f"Response {suffix}",
    )

    return promise


def _query_count_for_center(client, plant):
    url = reverse(
        "integrated-scheduling:commercial-promise-center"
    )

    with patch(
        "apps.integrated_scheduling.views._plant",
        return_value=plant,
    ):
        with CaptureQueriesContext(connection) as captured:
            response = client.get(url)

    assert response.status_code == 200
    return len(captured)


def test_commercial_promise_center_does_not_scale_queries_with_promises(
    client,
):
    user = _make_user()
    client.force_login(user)

    plant, line = _make_base_case()

    _make_promise(line, "small")

    # Warm-up para retirar efeitos de primeira requisição da comparação.
    _query_count_for_center(client, plant)

    small_queries = _query_count_for_center(client, plant)

    for index in range(19):
        _make_promise(line, f"large-{index}")

    large_queries = _query_count_for_center(client, plant)

    print(
        "N+1 commercial-promise-center: "
        f"small={small_queries}, large={large_queries}"
    )

    assert large_queries <= small_queries + 3
