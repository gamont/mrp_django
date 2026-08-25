import pytest
from django.contrib.auth import get_user_model
from apps.common.models import Plant
from apps.costing.models import AccountingPeriod, CostLedgerEntry, PeriodReopenRequest
from apps.costing.services.period_close import request_reopen, decide_reopen, reverse_ledger_entry

@pytest.mark.django_db
def test_reopen_requires_closed_period():
    plant=Plant.objects.create(code="T44", name="Test 044")
    period=AccountingPeriod.objects.create(plant=plant, code="2099-01", start_date="2099-01-01", end_date="2099-01-31")
    with pytest.raises(ValueError): request_reopen(period, "teste")

@pytest.mark.django_db
def test_reversal_is_idempotent():
    plant=Plant.objects.create(code="T45", name="Test 045")
    entry=CostLedgerEntry.objects.create(plant=plant, entry_type="ADJUSTMENT", posting_date="2099-01-31", account_code="INV", debit=10, credit=0, idempotency_key="t44-original")
    r1=reverse_ledger_entry(entry, "correção")
    r2=reverse_ledger_entry(entry, "correção")
    assert r1.pk == r2.pk
    assert r1.reversal_entry.credit == 10
