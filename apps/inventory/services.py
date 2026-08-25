from __future__ import annotations

from decimal import Decimal

from django.core.exceptions import ValidationError
from django.db import IntegrityError, transaction

from .models import InventoryTransaction, Location, StockBalance

ZERO = Decimal("0")


def _validate_idempotent_replay(existing: InventoryTransaction, candidate: InventoryTransaction) -> None:
    comparable_fields = (
        "transaction_type",
        "item_id",
        "from_location_id",
        "to_location_id",
        "quantity",
        "reference_type",
        "reference_id",
    )
    mismatches = [
        field
        for field in comparable_fields
        if getattr(existing, field) != getattr(candidate, field)
    ]
    if mismatches:
        raise ValidationError(
            {
                "idempotency_key": (
                    "A chave já foi usada por uma movimentação diferente. "
                    f"Campos divergentes: {', '.join(mismatches)}."
                )
            }
        )


def _ensure_balance(*, item_id: int, location_id: int) -> None:
    if StockBalance.objects.filter(item_id=item_id, location_id=location_id).exists():
        return
    try:
        # Savepoint isolado: se outra transação criar a mesma linha, o erro de
        # unicidade não invalida a transação externa.
        with transaction.atomic():
            StockBalance.objects.create(
                item_id=item_id,
                location_id=location_id,
                on_hand=ZERO,
                allocated=ZERO,
            )
    except IntegrityError:
        pass


def _locked_balances(*, item_id: int, locations: list[Location]) -> dict[int, StockBalance]:
    """Bloqueia saldos em ordem determinística para reduzir deadlocks."""

    location_ids = sorted({location.pk for location in locations if location is not None})
    for location_id in location_ids:
        _ensure_balance(item_id=item_id, location_id=location_id)

    rows = (
        StockBalance.objects.select_for_update()
        .filter(item_id=item_id, location_id__in=location_ids)
        .order_by("location_id")
    )
    balances = {row.location_id: row for row in rows}
    missing = set(location_ids) - set(balances)
    if missing:  # defesa adicional contra inconsistência inesperada
        raise ValidationError({"stock": f"Saldos não encontrados para locais: {sorted(missing)}"})
    return balances


@transaction.atomic
def post_inventory_transaction(tx: InventoryTransaction) -> InventoryTransaction:
    """Publica uma movimentação com idempotência e bloqueio pessimista.

    As linhas de saldo são adquiridas sempre pela ordem do ``location_id``.
    Isso evita o deadlock clássico de duas transferências concorrentes em
    sentidos opostos. A unicidade da chave de idempotência é tratada também
    no cenário de corrida entre processos.
    """

    if tx.idempotency_key:
        existing = InventoryTransaction.objects.filter(idempotency_key=tx.idempotency_key).first()
        if existing:
            _validate_idempotent_replay(existing, tx)
            return existing

    tx.full_clean()
    try:
        with transaction.atomic():
            tx.save(force_insert=True)
    except IntegrityError:
        if not tx.idempotency_key:
            raise
        existing = InventoryTransaction.objects.get(idempotency_key=tx.idempotency_key)
        _validate_idempotent_replay(existing, tx)
        return existing

    outgoing_types = {
        InventoryTransaction.TransactionType.ISSUE,
        InventoryTransaction.TransactionType.TRANSFER,
        InventoryTransaction.TransactionType.PRODUCTION_ISSUE,
    }
    incoming_types = {
        InventoryTransaction.TransactionType.RECEIPT,
        InventoryTransaction.TransactionType.TRANSFER,
        InventoryTransaction.TransactionType.PURCHASE_RECEIPT,
        InventoryTransaction.TransactionType.PRODUCTION_RECEIPT,
        InventoryTransaction.TransactionType.RETURN,
    }

    involved_locations: list[Location] = []
    if tx.transaction_type in outgoing_types:
        if not tx.from_location_id:
            raise ValidationError("A movimentação exige local de origem.")
        involved_locations.append(tx.from_location)
    if tx.transaction_type in incoming_types:
        if not tx.to_location_id:
            raise ValidationError("A movimentação exige local de destino.")
        involved_locations.append(tx.to_location)
    if tx.transaction_type == InventoryTransaction.TransactionType.ADJUSTMENT:
        location = tx.to_location or tx.from_location
        if not location:
            raise ValidationError("O ajuste exige um local.")
        involved_locations.append(location)

    if tx.from_location_id and tx.to_location_id:
        source_plant = tx.from_location.warehouse.plant_id
        target_plant = tx.to_location.warehouse.plant_id
        if source_plant != target_plant:
            raise ValidationError("Transferências entre plantas exigem um processo interplanta.")

    balances = _locked_balances(item_id=tx.item_id, locations=involved_locations)

    if tx.transaction_type in outgoing_types:
        source = balances[tx.from_location_id]
        if source.on_hand < tx.quantity:
            raise ValidationError(
                f"Saldo físico insuficiente: {source.on_hand}; solicitado: {tx.quantity}."
            )
        # Movimentações genéricas não podem consumir quantidades reservadas.
        if tx.transaction_type != InventoryTransaction.TransactionType.PRODUCTION_ISSUE:
            available = source.on_hand - source.allocated
            if available < tx.quantity:
                raise ValidationError(
                    f"Saldo disponível insuficiente: {available}; solicitado: {tx.quantity}."
                )
        source.on_hand -= tx.quantity
        source.save(update_fields=["on_hand", "updated_at"])

    if tx.transaction_type in incoming_types:
        target = balances[tx.to_location_id]
        target.on_hand += tx.quantity
        target.save(update_fields=["on_hand", "updated_at"])

    if tx.transaction_type == InventoryTransaction.TransactionType.ADJUSTMENT:
        location_id = (tx.to_location or tx.from_location).pk
        balance = balances[location_id]
        balance.on_hand += tx.quantity
        if balance.on_hand < ZERO:
            raise ValidationError("O ajuste resultaria em saldo negativo.")
        if balance.on_hand < balance.allocated:
            raise ValidationError("O ajuste deixaria o saldo físico abaixo do saldo reservado.")
        balance.save(update_fields=["on_hand", "updated_at"])

    return tx
