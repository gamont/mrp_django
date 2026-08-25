from decimal import Decimal
from django.db import transaction
from django.utils import timezone

from apps.inventory.models import StockBalance
from apps.production.models import WorkOrder
from apps.costing.models import (
    AccountingPeriod,
    CostVersion,
    InventoryValuationSnapshot,
    InventoryValuationLine,
    ItemCost,
    MovingAverageCostBalance,
    WIPSnapshot,
    WIPLine,
    WorkOrderCost,
)

ZERO = Decimal("0")


def _active_cost_version(plant, period=None):
    if period and period.cost_version_id:
        return period.cost_version
    version = CostVersion.objects.filter(plant=plant, status=CostVersion.Status.ACTIVE).order_by("-effective_from").first()
    if not version:
        raise ValueError("Não existe versão de custo ativa para a planta.")
    return version


@transaction.atomic
def create_inventory_valuation(period: AccountingPeriod, valuation_method="STANDARD"):
    if period.status == AccountingPeriod.Status.CLOSED:
        raise ValueError("Período fechado não pode ser recalculado.")
    if valuation_method not in {InventoryValuationSnapshot.ValuationMethod.STANDARD, InventoryValuationSnapshot.ValuationMethod.MOVING_AVERAGE}:
        raise ValueError("Método suportado: STANDARD ou MOVING_AVERAGE.")

    version = _active_cost_version(period.plant, period)
    snapshot, _ = InventoryValuationSnapshot.objects.update_or_create(
        period=period,
        valuation_method=valuation_method,
        defaults={"cost_version": version, "as_of": timezone.now(), "total_quantity": ZERO, "total_value": ZERO},
    )
    snapshot.lines.all().delete()

    if valuation_method == InventoryValuationSnapshot.ValuationMethod.MOVING_AVERAGE:
        costs = {row.item_id: row.average_unit_cost for row in MovingAverageCostBalance.objects.filter(plant=period.plant)}
    else:
        costs = {row.item_id: row.total_cost for row in ItemCost.objects.filter(cost_version=version)}
    total_qty = ZERO
    total_value = ZERO
    balances = StockBalance.objects.select_related("item", "location__warehouse").filter(location__warehouse__plant=period.plant, on_hand__gt=0)
    lines = []
    for balance in balances.iterator():
        unit_cost = costs.get(balance.item_id, balance.item.standard_cost or ZERO)
        value = balance.on_hand * unit_cost
        total_qty += balance.on_hand
        total_value += value
        lines.append(InventoryValuationLine(
            snapshot=snapshot,
            item=balance.item,
            location=balance.location,
            quantity=balance.on_hand,
            unit_cost=unit_cost,
            total_value=value,
        ))
    InventoryValuationLine.objects.bulk_create(lines, batch_size=1000)
    snapshot.total_quantity = total_qty
    snapshot.total_value = total_value
    snapshot.save(update_fields=["total_quantity", "total_value", "as_of", "updated_at"])
    return snapshot


@transaction.atomic
def create_wip_snapshot(period: AccountingPeriod):
    if period.status == AccountingPeriod.Status.CLOSED:
        raise ValueError("Período fechado não pode ser recalculado.")
    version = _active_cost_version(period.plant, period)
    snapshot, _ = WIPSnapshot.objects.update_or_create(
        period=period,
        defaults={"cost_version": version, "as_of": timezone.now(), "total_value": ZERO},
    )
    snapshot.lines.all().delete()

    active_statuses = [WorkOrder.Status.RELEASED, WorkOrder.Status.IN_PROGRESS]
    orders = WorkOrder.objects.filter(plant=period.plant, status__in=active_statuses).select_related("item")
    total = ZERO
    lines = []
    for wo in orders.iterator():
        actual = WorkOrderCost.objects.filter(work_order=wo, cost_type=WorkOrderCost.CostType.ACTUAL).first()
        if actual:
            material = actual.material_cost
            setup = actual.setup_cost
            labor = actual.labor_cost
            machine = actual.machine_cost
            overhead = actual.overhead_cost
            subcontract = actual.subcontract_cost
            scrap = actual.scrap_cost
            incurred = actual.total_cost
        else:
            material = setup = labor = machine = overhead = subcontract = scrap = incurred = ZERO

        completed_value = ZERO
        if wo.quantity and wo.completed_quantity:
            standard = ItemCost.objects.filter(cost_version=version, item=wo.item).first()
            if standard:
                completed_value = min(incurred, wo.completed_quantity * standard.total_cost)
        wip_value = max(ZERO, incurred - completed_value)
        total += wip_value
        lines.append(WIPLine(
            snapshot=snapshot,
            work_order=wo,
            material_cost=material,
            setup_cost=setup,
            labor_cost=labor,
            machine_cost=machine,
            overhead_cost=overhead,
            subcontract_cost=subcontract,
            scrap_cost=scrap,
            completed_value=completed_value,
            wip_value=wip_value,
        ))
    WIPLine.objects.bulk_create(lines, batch_size=500)
    snapshot.total_value = total
    snapshot.save(update_fields=["total_value", "as_of", "updated_at"])
    return snapshot


@transaction.atomic
def close_accounting_period(period: AccountingPeriod, user=None):
    period = AccountingPeriod.objects.select_for_update(of=("self",)).select_related("plant", "cost_version").get(pk=period.pk)
    if period.status == AccountingPeriod.Status.CLOSED:
        return period
    period.status = AccountingPeriod.Status.CLOSING
    period.save(update_fields=["status", "updated_at"])
    version = _active_cost_version(period.plant, period)
    if not period.cost_version_id:
        period.cost_version = version
        period.save(update_fields=["cost_version", "updated_at"])
    create_inventory_valuation(period)
    create_wip_snapshot(period)
    from apps.costing.services.accounting import post_period_variances, post_period_close_balances
    post_period_variances(period)
    post_period_close_balances(period)
    period.status = AccountingPeriod.Status.CLOSED
    period.closed_at = timezone.now()
    period.closed_by = user if getattr(user, "is_authenticated", False) else None
    period.save(update_fields=["status", "closed_at", "closed_by", "updated_at"])
    return period
