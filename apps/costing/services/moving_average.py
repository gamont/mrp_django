from decimal import Decimal
from django.db import transaction, models

from apps.costing.models import MovingAverageCostBalance, InventoryCostMovement
from apps.inventory.models import InventoryTransaction
from apps.purchasing.models import GoodsReceipt
from apps.costing.models import CostVersion, ItemCost, WorkOrderCost
from apps.production.models import WorkOrder

ZERO = Decimal("0")


def _plant_for_transaction(tx):
    location = tx.to_location or tx.from_location
    if not location:
        raise ValueError("Movimentação sem local não pode ser valorizada.")
    return location.warehouse.plant


def _receipt_unit_cost(tx, balance, explicit_unit_cost=None):
    if explicit_unit_cost is not None:
        return Decimal(str(explicit_unit_cost))
    if tx.transaction_type == InventoryTransaction.TransactionType.PURCHASE_RECEIPT:
        receipt = GoodsReceipt.objects.select_related("purchase_order_line").filter(inventory_transaction=tx).first()
        if receipt:
            return receipt.purchase_order_line.unit_price
    if tx.transaction_type == InventoryTransaction.TransactionType.PRODUCTION_RECEIPT and tx.reference_type == "WORK_ORDER":
        try:
            wo = WorkOrder.objects.get(pk=tx.reference_id)
        except (WorkOrder.DoesNotExist, ValueError):
            wo = None
        if wo:
            actual = WorkOrderCost.objects.filter(work_order=wo, cost_type=WorkOrderCost.CostType.ACTUAL).first()
            if actual and actual.quantity_basis:
                return actual.unit_cost
            version = CostVersion.objects.filter(plant=wo.plant, status=CostVersion.Status.ACTIVE).order_by("-effective_from").first()
            if version:
                standard = ItemCost.objects.filter(cost_version=version, item=tx.item).values_list("total_cost", flat=True).first()
                if standard is not None:
                    return standard
    return balance.average_unit_cost or tx.item.standard_cost or ZERO


@transaction.atomic
def post_moving_average_cost(tx: InventoryTransaction, explicit_unit_cost=None):
    """Valoriza uma movimentação já postada e atualiza o custo médio do item.

    Transferências internas não alteram quantidade/valor no nível planta; apenas
    registram o movimento financeiro para rastreabilidade.
    """
    existing = InventoryCostMovement.objects.filter(transaction=tx).first()
    if existing:
        return existing, False
    tx = InventoryTransaction.objects.select_related("item", "from_location__warehouse", "to_location__warehouse").get(pk=tx.pk)
    plant = _plant_for_transaction(tx)
    balance, _ = MovingAverageCostBalance.objects.select_for_update().get_or_create(plant=plant, item=tx.item)

    is_transfer = tx.transaction_type == InventoryTransaction.TransactionType.TRANSFER and tx.from_location_id and tx.to_location_id and tx.from_location.warehouse.plant_id == tx.to_location.warehouse.plant_id
    inbound = tx.transaction_type in {InventoryTransaction.TransactionType.RECEIPT, InventoryTransaction.TransactionType.PURCHASE_RECEIPT, InventoryTransaction.TransactionType.PRODUCTION_RECEIPT, InventoryTransaction.TransactionType.RETURN}
    outbound = tx.transaction_type in {InventoryTransaction.TransactionType.ISSUE, InventoryTransaction.TransactionType.PRODUCTION_ISSUE}

    qty = abs(tx.quantity)
    movement_type = InventoryCostMovement.MovementType.TRANSFER if is_transfer else InventoryCostMovement.MovementType.ADJUSTMENT
    if is_transfer:
        unit_cost = balance.average_unit_cost
        value = ZERO
    elif inbound or (tx.transaction_type == InventoryTransaction.TransactionType.ADJUSTMENT and tx.quantity > 0):
        movement_type = InventoryCostMovement.MovementType.RECEIPT if inbound else InventoryCostMovement.MovementType.ADJUSTMENT
        unit_cost = _receipt_unit_cost(tx, balance, explicit_unit_cost)
        value = qty * unit_cost
        balance.quantity += qty
        balance.inventory_value += value
        balance.average_unit_cost = balance.inventory_value / balance.quantity if balance.quantity else ZERO
    elif outbound or (tx.transaction_type == InventoryTransaction.TransactionType.ADJUSTMENT and tx.quantity < 0):
        movement_type = InventoryCostMovement.MovementType.ISSUE if outbound else InventoryCostMovement.MovementType.ADJUSTMENT
        if qty > balance.quantity:
            raise ValueError(f"Saída financeira {qty} excede saldo valorizado {balance.quantity} para {tx.item.code}.")
        unit_cost = balance.average_unit_cost
        value = -(qty * unit_cost)
        balance.quantity -= qty
        balance.inventory_value = max(ZERO, balance.inventory_value + value)
        if not balance.quantity:
            balance.inventory_value = ZERO
            balance.average_unit_cost = ZERO
    else:
        unit_cost = balance.average_unit_cost
        value = ZERO

    balance.last_transaction = tx
    balance.save(update_fields=["quantity", "inventory_value", "average_unit_cost", "last_transaction", "updated_at"])
    movement = InventoryCostMovement.objects.create(
        transaction=tx, plant=plant, item=tx.item, movement_type=movement_type, quantity=tx.quantity,
        unit_cost=unit_cost, value=value, quantity_after=balance.quantity, value_after=balance.inventory_value,
        average_cost_after=balance.average_unit_cost, reference_type=tx.reference_type, reference_id=tx.reference_id,
        posted_at=tx.posted_at, details={"inventory_transaction_type": tx.transaction_type},
    )
    return movement, True


@transaction.atomic
def rebuild_moving_average(plant, through=None):
    MovingAverageCostBalance.objects.filter(plant=plant).delete()
    InventoryCostMovement.objects.filter(plant=plant).delete()
    qs = InventoryTransaction.objects.filter(
        models.Q(from_location__warehouse__plant=plant) | models.Q(to_location__warehouse__plant=plant)
    ).distinct().order_by("posted_at", "id")
    if through:
        qs = qs.filter(posted_at__lte=through)
    count = 0
    for tx in qs.iterator():
        post_moving_average_cost(tx)
        count += 1
    return count
