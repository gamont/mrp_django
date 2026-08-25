from decimal import Decimal
from django.db import transaction
from django.db.models import Sum
from django.utils import timezone

from apps.costing.models import (AccountingPeriod, CostLedgerEntry, CostVariance, PeriodVariancePosting, WIPSnapshot, InventoryValuationSnapshot)

ZERO = Decimal("0")


def _entry(*, period, entry_type, account, debit=ZERO, credit=ZERO, key, description="", reference_type="", reference_id="", details=None):
    obj, _ = CostLedgerEntry.objects.get_or_create(
        idempotency_key=key,
        defaults={
            "period": period, "plant": period.plant, "entry_type": entry_type, "posting_date": period.end_date,
            "account_code": account, "debit": debit, "credit": credit, "description": description,
            "reference_type": reference_type, "reference_id": str(reference_id or ""), "details": details or {},
        },
    )
    return obj


@transaction.atomic
def post_period_variances(period: AccountingPeriod):
    if period.status == AccountingPeriod.Status.CLOSED and period.variance_postings.exists():
        return list(period.variance_postings.select_related("ledger_debit", "ledger_credit"))
    qs = CostVariance.objects.filter(work_order__plant=period.plant, updated_at__date__gte=period.start_date, updated_at__date__lte=period.end_date)
    rows = qs.values("variance_type").annotate(amount=Sum("variance_amount"))
    result=[]
    for row in rows:
        amount = row["amount"] or ZERO
        if amount == 0:
            continue
        vt=row["variance_type"]
        # Valor positivo = desfavorável: débito na conta de variação e crédito no clearing.
        if amount > 0:
            debit=_entry(period=period, entry_type=CostLedgerEntry.EntryType.VARIANCE, account=f"VAR-{vt}", debit=amount, key=f"period:{period.pk}:variance:{vt}:debit", description=f"Variação {vt}")
            credit=_entry(period=period, entry_type=CostLedgerEntry.EntryType.VARIANCE, account="VARIANCE-CLEARING", credit=amount, key=f"period:{period.pk}:variance:{vt}:credit", description=f"Contrapartida variação {vt}")
        else:
            abs_amount=abs(amount)
            debit=_entry(period=period, entry_type=CostLedgerEntry.EntryType.VARIANCE, account="VARIANCE-CLEARING", debit=abs_amount, key=f"period:{period.pk}:variance:{vt}:debit", description=f"Contrapartida variação {vt}")
            credit=_entry(period=period, entry_type=CostLedgerEntry.EntryType.VARIANCE, account=f"VAR-{vt}", credit=abs_amount, key=f"period:{period.pk}:variance:{vt}:credit", description=f"Variação favorável {vt}")
        posting,_=PeriodVariancePosting.objects.update_or_create(period=period, variance_type=vt, defaults={"amount": amount, "favorable": amount < 0, "posted_at": timezone.now(), "ledger_debit": debit, "ledger_credit": credit})
        result.append(posting)
    return result


@transaction.atomic
def post_period_close_balances(period: AccountingPeriod):
    inv = InventoryValuationSnapshot.objects.filter(period=period).order_by("-as_of").first()
    wip = WIPSnapshot.objects.filter(period=period).order_by("-as_of").first()
    entries=[]
    if inv and inv.total_value:
        entries.append(_entry(period=period, entry_type=CostLedgerEntry.EntryType.PERIOD_CLOSE, account="INVENTORY-CONTROL", debit=inv.total_value, key=f"period:{period.pk}:inventory:debit", description="Snapshot de estoque no fechamento"))
        entries.append(_entry(period=period, entry_type=CostLedgerEntry.EntryType.PERIOD_CLOSE, account="INVENTORY-OPENING-CLEARING", credit=inv.total_value, key=f"period:{period.pk}:inventory:credit", description="Contrapartida do snapshot de estoque"))
    if wip and wip.total_value:
        entries.append(_entry(period=period, entry_type=CostLedgerEntry.EntryType.PERIOD_CLOSE, account="WIP-CONTROL", debit=wip.total_value, key=f"period:{period.pk}:wip:debit", description="WIP no fechamento"))
        entries.append(_entry(period=period, entry_type=CostLedgerEntry.EntryType.PERIOD_CLOSE, account="WIP-OPENING-CLEARING", credit=wip.total_value, key=f"period:{period.pk}:wip:credit", description="Contrapartida do WIP"))
    return entries
