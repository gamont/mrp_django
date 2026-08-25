from __future__ import annotations

from decimal import Decimal
from threading import Barrier, Thread

import pytest
from django.conf import settings
from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.db import IntegrityError, close_old_connections, connection, transaction
from rest_framework.test import APIClient

from apps.common.models import Plant
from apps.common.roles import ROLE_AUDITOR, sync_default_roles
from apps.inventory.models import InventoryTransaction, Location, StockBalance, Warehouse
from apps.inventory.services import post_inventory_transaction
from apps.masterdata.models import Item


@pytest.fixture
def stock_context(db):
    plant = Plant.objects.create(code="STB", name="Estabilização")
    warehouse = Warehouse.objects.create(plant=plant, code="GERAL", name="Geral")
    location = Location.objects.create(warehouse=warehouse, code="A1")
    item = Item.objects.create(
        code="STB-ITEM",
        description="Item de estabilização",
        item_type=Item.ItemType.PURCHASED,
    )
    return plant, warehouse, location, item


@pytest.mark.django_db
def test_inventory_idempotency_rejects_different_payload(stock_context):
    _, _, location, item = stock_context
    first = InventoryTransaction(
        transaction_type=InventoryTransaction.TransactionType.RECEIPT,
        item=item,
        to_location=location,
        quantity=Decimal("10"),
        idempotency_key="same-key",
    )
    post_inventory_transaction(first)

    replay_with_different_payload = InventoryTransaction(
        transaction_type=InventoryTransaction.TransactionType.RECEIPT,
        item=item,
        to_location=location,
        quantity=Decimal("11"),
        idempotency_key="same-key",
    )
    with pytest.raises(ValidationError, match="chave já foi usada"):
        post_inventory_transaction(replay_with_different_payload)

    assert StockBalance.objects.get(item=item, location=location).on_hand == Decimal("10.0000")
    assert InventoryTransaction.objects.filter(idempotency_key="same-key").count() == 1


@pytest.mark.django_db
def test_database_rejects_negative_stock(stock_context):
    _, _, location, item = stock_context
    with pytest.raises(IntegrityError):
        with transaction.atomic():
            StockBalance.objects.create(item=item, location=location, on_hand=Decimal("-1"))


@pytest.mark.django_db
def test_health_endpoints(client):
    live = client.get("/health/live/")
    ready = client.get("/health/ready/")
    metrics = client.get("/metrics/")

    assert live.status_code == 200
    assert live.json()["version"] == settings.MRP_VERSION
    assert ready.status_code == 200
    assert ready.json()["checks"]["database"] == "ok"
    assert metrics.status_code == 200
    assert "mrp_database_up 1" in metrics.content.decode()


@pytest.mark.django_db
def test_auditor_role_has_read_only_api_access(stock_context):
    _, _, _, item = stock_context
    sync_default_roles()
    user = get_user_model().objects.create_user(username="auditor", password="secret-123")
    user.groups.add(user.groups.model.objects.get(name=ROLE_AUDITOR))

    client = APIClient()
    client.force_authenticate(user=user)

    response = client.get("/api/items/")
    assert response.status_code == 200

    response = client.post(
        "/api/items/",
        {
            "code": "BLOCKED",
            "description": "Não deve criar",
            "item_type": Item.ItemType.PURCHASED,
        },
        format="json",
    )
    assert response.status_code == 403
    assert Item.objects.filter(code="BLOCKED").exists() is False
    assert Item.objects.filter(pk=item.pk).exists()


@pytest.mark.django_db(transaction=True)
def test_concurrent_same_idempotency_key_posts_once(stock_context):
    if connection.vendor != "postgresql":
        pytest.skip("Teste de bloqueio concorrente executado somente em PostgreSQL.")

    _, _, location, item = stock_context
    barrier = Barrier(2)
    results: list[int] = []
    errors: list[BaseException] = []

    def worker() -> None:
        close_old_connections()
        try:
            local_item = Item.objects.get(pk=item.pk)
            local_location = Location.objects.get(pk=location.pk)
            barrier.wait(timeout=10)
            tx = post_inventory_transaction(
                InventoryTransaction(
                    transaction_type=InventoryTransaction.TransactionType.RECEIPT,
                    item=local_item,
                    to_location=local_location,
                    quantity=Decimal("7"),
                    idempotency_key="concurrent-receipt",
                )
            )
            results.append(tx.pk)
        except BaseException as exc:  # pragma: no cover - diagnóstico de concorrência
            errors.append(exc)
        finally:
            close_old_connections()

    threads = [Thread(target=worker), Thread(target=worker)]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join(timeout=20)

    assert errors == []
    assert len(results) == 2
    assert len(set(results)) == 1
    assert InventoryTransaction.objects.filter(idempotency_key="concurrent-receipt").count() == 1
    assert StockBalance.objects.get(item=item, location=location).on_hand == Decimal("7.0000")
