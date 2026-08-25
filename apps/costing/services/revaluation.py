from decimal import Decimal
from django.db import transaction
from django.db.models import Sum
from django.utils import timezone

from apps.costing.models import (
    AccountingPeriod, CostLedgerEntry, FinancialInventoryAdjustment,
    InventoryRevaluation, MovingAverageCostBalance,
)
from apps.inventory.models import StockBalance

ZERO = Decimal("0")


def _ledger(*, plant, period, account, debit=ZERO, credit=ZERO, key, description, reference_type, reference_id):
    obj, _ = CostLedgerEntry.objects.get_or_create(
        idempotency_key=key,
        defaults={
            "period": period, "plant": plant, "entry_type": CostLedgerEntry.EntryType.ADJUSTMENT,
            "posting_date": (period.end_date if period else timezone.localdate()), "account_code": account,
            "debit": debit, "credit": credit, "description": description,
            "reference_type": reference_type, "reference_id": str(reference_id),
        },
    )
    return obj


@transaction.atomic
def revalue_item(*, plant, item, new_unit_cost, reason, user=None, period=None, idempotency_key):
    existing = InventoryRevaluation.objects.filter(idempotency_key=idempotency_key).first()
    if existing:
        return existing, False
    if period and period.status == AccountingPeriod.Status.CLOSED:
        raise ValueError("Não é permitido reavaliar estoque em período fechado.")
    balance, _ = MovingAverageCostBalance.objects.select_for_update().get_or_create(plant=plant, item=item)
    qty = balance.quantity
    old_cost = balance.average_unit_cost
    new_cost = Decimal(str(new_unit_cost))
    old_value = balance.inventory_value
    new_value = (qty * new_cost).quantize(Decimal("0.0001"))
    variance = new_value - old_value
    balance.inventory_value = new_value
    balance.average_unit_cost = new_cost if qty else ZERO
    balance.save(update_fields=["inventory_value", "average_unit_cost", "updated_at"])
    obj = InventoryRevaluation.objects.create(
        plant=plant, item=item, period=period, method=InventoryRevaluation.Method.MANUAL,
        quantity=qty, old_unit_cost=old_cost, new_unit_cost=new_cost, old_value=old_value,
        new_value=new_value, variance_value=variance, reason=reason, posted_by=user,
        idempotency_key=idempotency_key,
    )
    if variance:
        amount = abs(variance)
        if variance > 0:
            debit = _ledger(plant=plant, period=period, account="INVENTORY-CONTROL", debit=amount,
                            key=f"{idempotency_key}:dr", description=reason, reference_type="INVENTORY_REVALUATION", reference_id=obj.pk)
            credit = _ledger(plant=plant, period=period, account="INVENTORY-REVALUATION", credit=amount,
                             key=f"{idempotency_key}:cr", description=reason, reference_type="INVENTORY_REVALUATION", reference_id=obj.pk)
        else:
            debit = _ledger(plant=plant, period=period, account="INVENTORY-REVALUATION", debit=amount,
                            key=f"{idempotency_key}:dr", description=reason, reference_type="INVENTORY_REVALUATION", reference_id=obj.pk)
            credit = _ledger(plant=plant, period=period, account="INVENTORY-CONTROL", credit=amount,
                             key=f"{idempotency_key}:cr", description=reason, reference_type="INVENTORY_REVALUATION", reference_id=obj.pk)
        obj.ledger_debit, obj.ledger_credit = debit, credit
        obj.save(update_fields=["ledger_debit", "ledger_credit", "updated_at"])
    return obj, True


@transaction.atomic
def post_financial_adjustment(adjustment: FinancialInventoryAdjustment, user=None):
    adjustment = FinancialInventoryAdjustment.objects.select_for_update().get(pk=adjustment.pk)
    if adjustment.status == FinancialInventoryAdjustment.Status.POSTED:
        return adjustment
    if adjustment.period and adjustment.period.status == AccountingPeriod.Status.CLOSED:
        raise ValueError("Período fechado.")
    amount = abs(adjustment.value_delta)
    if adjustment.value_delta > 0:
        debit = _ledger(plant=adjustment.plant, period=adjustment.period, account="INVENTORY-CONTROL", debit=amount,
                        key=f"{adjustment.idempotency_key}:dr", description=adjustment.reason, reference_type="FINANCIAL_ADJUSTMENT", reference_id=adjustment.pk)
        credit = _ledger(plant=adjustment.plant, period=adjustment.period, account="INVENTORY-ADJUSTMENT", credit=amount,
                         key=f"{adjustment.idempotency_key}:cr", description=adjustment.reason, reference_type="FINANCIAL_ADJUSTMENT", reference_id=adjustment.pk)
    else:
        debit = _ledger(plant=adjustment.plant, period=adjustment.period, account="INVENTORY-ADJUSTMENT", debit=amount,
                        key=f"{adjustment.idempotency_key}:dr", description=adjustment.reason, reference_type="FINANCIAL_ADJUSTMENT", reference_id=adjustment.pk)
        credit = _ledger(plant=adjustment.plant, period=adjustment.period, account="INVENTORY-CONTROL", credit=amount,
                         key=f"{adjustment.idempotency_key}:cr", description=adjustment.reason, reference_type="FINANCIAL_ADJUSTMENT", reference_id=adjustment.pk)
    adjustment.ledger_debit, adjustment.ledger_credit = debit, credit
    adjustment.status = FinancialInventoryAdjustment.Status.POSTED
    adjustment.posted_at = timezone.now(); adjustment.posted_by = user
    adjustment.save(update_fields=["ledger_debit", "ledger_credit", "status", "posted_at", "posted_by", "updated_at"])
    return adjustment
