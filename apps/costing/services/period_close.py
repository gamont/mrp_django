from decimal import Decimal
from django.db import transaction
from django.db.models import Sum
from django.utils import timezone

from apps.common.models import DomainEvent
from apps.costing.models import (
    AccountingPeriod, CostLedgerEntry, CostLedgerReversal, CostPeriodAudit,
    InventoryReconciliationRun, InventoryValuationSnapshot, PeriodCloseRun,
    PeriodReopenRequest, PeriodVariancePosting, WIPSnapshot,
)
from apps.costing.services.accounting import post_period_close_balances, post_period_variances
from apps.costing.services.reconciliation import reconcile_inventory
from apps.costing.services.valuation import create_inventory_valuation, create_wip_snapshot

ZERO = Decimal("0")


def _actor(user):
    return user if getattr(user, "is_authenticated", False) else None


def _audit(period, action, user=None, reference_type="", reference_id="", payload=None):
    row = CostPeriodAudit.objects.create(
        period=period, action=action, actor=_actor(user), reference_type=reference_type,
        reference_id=str(reference_id or ""), payload=payload or {},
    )
    DomainEvent.objects.get_or_create(
        idempotency_key=f"cost-audit:{row.pk}",
        defaults={
            "event_type": f"COST_{action}", "aggregate_type": "AccountingPeriod",
            "aggregate_id": str(period.pk), "payload": row.payload, "actor": _actor(user),
        },
    )
    return row


def _ledger_totals(period):
    values = period.ledger_entries.aggregate(debit=Sum("debit"), credit=Sum("credit"))
    return values["debit"] or ZERO, values["credit"] or ZERO


@transaction.atomic
def final_close_period(period, user=None, strict_reconciliation=False):
    period = AccountingPeriod.objects.select_for_update().select_related("plant", "cost_version").get(pk=period.pk)
    if period.status == AccountingPeriod.Status.CLOSED:
        return period.close_runs.filter(status=PeriodCloseRun.Status.COMPLETED).first()
    if period.status not in {AccountingPeriod.Status.OPEN, AccountingPeriod.Status.CLOSING}:
        raise ValueError("Período não está disponível para fechamento.")

    run = PeriodCloseRun.objects.create(period=period, strict_reconciliation=bool(strict_reconciliation), executed_by=_actor(user))
    _audit(period, CostPeriodAudit.Action.CLOSE_STARTED, user, "PeriodCloseRun", run.pk)
    period.status = AccountingPeriod.Status.CLOSING
    period.save(update_fields=["status", "updated_at"])

    try:
        inv = create_inventory_valuation(period, "STANDARD")
        wip = create_wip_snapshot(period)
        reconciliation = reconcile_inventory(period.plant, period=period, user=user)
        if strict_reconciliation and (reconciliation.quantity_variance != 0 or reconciliation.value_variance != 0):
            raise ValueError("Fechamento bloqueado: conciliação físico x financeiro possui divergências.")

        variances = post_period_variances(period)
        post_period_close_balances(period)
        debit, credit = _ledger_totals(period)
        if debit != credit:
            raise ValueError(f"Subledger desbalanceado: débito {debit} / crédito {credit}.")

        variance_value = sum((row.amount for row in variances), ZERO)
        run.status = PeriodCloseRun.Status.COMPLETED
        run.finished_at = timezone.now()
        run.inventory_value = inv.total_value
        run.wip_value = wip.total_value
        run.variance_value = variance_value
        run.ledger_debits = debit
        run.ledger_credits = credit
        run.reconciliation_quantity_variance = reconciliation.quantity_variance
        run.reconciliation_value_variance = reconciliation.value_variance
        run.save()

        period.status = AccountingPeriod.Status.CLOSED
        period.closed_at = timezone.now()
        period.closed_by = _actor(user)
        period.save(update_fields=["status", "closed_at", "closed_by", "updated_at"])
        _audit(period, CostPeriodAudit.Action.CLOSE_COMPLETED, user, "PeriodCloseRun", run.pk, {
            "inventory_value": str(inv.total_value), "wip_value": str(wip.total_value),
            "variance_value": str(variance_value), "ledger_debits": str(debit), "ledger_credits": str(credit),
            "reconciliation_quantity_variance": str(reconciliation.quantity_variance),
            "reconciliation_value_variance": str(reconciliation.value_variance),
        })
        return run
    except Exception as exc:
        run.status = PeriodCloseRun.Status.FAILED
        run.finished_at = timezone.now()
        run.error_message = str(exc)
        run.save(update_fields=["status", "finished_at", "error_message", "updated_at"])
        period.status = AccountingPeriod.Status.OPEN
        period.save(update_fields=["status", "updated_at"])
        _audit(period, CostPeriodAudit.Action.CLOSE_FAILED, user, "PeriodCloseRun", run.pk, {"error": str(exc)})
        raise


@transaction.atomic
def reverse_ledger_entry(entry, reason, user=None):
    entry = CostLedgerEntry.objects.select_for_update().get(pk=entry.pk)
    if hasattr(entry, "reversal_record"):
        return entry.reversal_record
    reversal = CostLedgerEntry.objects.create(
        period=entry.period, plant=entry.plant, entry_type=entry.entry_type,
        posting_date=timezone.localdate(), account_code=entry.account_code,
        debit=entry.credit, credit=entry.debit,
        reference_type="REVERSAL", reference_id=str(entry.pk),
        description=f"Estorno: {entry.description}"[:240],
        idempotency_key=f"reverse-ledger:{entry.pk}",
        details={"original_entry": entry.pk, "reason": reason},
    )
    record = CostLedgerReversal.objects.create(original_entry=entry, reversal_entry=reversal, reason=reason, reversed_by=_actor(user))
    if entry.period_id:
        _audit(entry.period, CostPeriodAudit.Action.LEDGER_REVERSED, user, "CostLedgerEntry", entry.pk, {"reversal_entry": reversal.pk, "reason": reason})
    return record


@transaction.atomic
def request_reopen(period, reason, user=None):
    period = AccountingPeriod.objects.select_for_update().get(pk=period.pk)
    if period.status != AccountingPeriod.Status.CLOSED:
        raise ValueError("Somente períodos fechados podem ter reabertura solicitada.")
    if period.reopen_requests.filter(status__in=[PeriodReopenRequest.Status.REQUESTED, PeriodReopenRequest.Status.APPROVED]).exists():
        raise ValueError("Já existe solicitação de reabertura pendente para o período.")
    req = PeriodReopenRequest.objects.create(period=period, reason=reason, requested_by=_actor(user))
    _audit(period, CostPeriodAudit.Action.REOPEN_REQUESTED, user, "PeriodReopenRequest", req.pk, {"reason": reason})
    return req


@transaction.atomic
def decide_reopen(request_obj, approve, user=None, notes=""):
    req = PeriodReopenRequest.objects.select_for_update().select_related("period").get(pk=request_obj.pk)
    if req.status != PeriodReopenRequest.Status.REQUESTED:
        raise ValueError("Solicitação já foi decidida.")
    req.status = PeriodReopenRequest.Status.APPROVED if approve else PeriodReopenRequest.Status.REJECTED
    req.decided_by = _actor(user)
    req.decided_at = timezone.now()
    req.decision_notes = notes
    req.save(update_fields=["status", "decided_by", "decided_at", "decision_notes", "updated_at"])
    action = CostPeriodAudit.Action.REOPEN_APPROVED if approve else CostPeriodAudit.Action.REOPEN_REJECTED
    _audit(req.period, action, user, "PeriodReopenRequest", req.pk, {"notes": notes})
    return req


@transaction.atomic
def apply_reopen(request_obj, user=None):
    req = PeriodReopenRequest.objects.select_for_update().select_related("period").get(pk=request_obj.pk)
    period = AccountingPeriod.objects.select_for_update().get(pk=req.period_id)
    if req.status != PeriodReopenRequest.Status.APPROVED:
        raise ValueError("A reabertura precisa estar aprovada.")
    if period.status != AccountingPeriod.Status.CLOSED:
        raise ValueError("O período não está fechado.")

    entries = list(period.ledger_entries.filter(entry_type__in=[CostLedgerEntry.EntryType.PERIOD_CLOSE, CostLedgerEntry.EntryType.VARIANCE]).order_by("id"))
    for entry in entries:
        reverse_ledger_entry(entry, f"Reabertura do período {period.code}: {req.reason}", user)

    period.status = AccountingPeriod.Status.OPEN
    period.closed_at = None
    period.closed_by = None
    period.save(update_fields=["status", "closed_at", "closed_by", "updated_at"])
    req.status = PeriodReopenRequest.Status.APPLIED
    req.applied_by = _actor(user)
    req.applied_at = timezone.now()
    req.save(update_fields=["status", "applied_by", "applied_at", "updated_at"])
    period.close_runs.filter(status=PeriodCloseRun.Status.COMPLETED).update(status=PeriodCloseRun.Status.REVERSED)
    _audit(period, CostPeriodAudit.Action.REOPEN_APPLIED, user, "PeriodReopenRequest", req.pk, {"reversed_entries": len(entries)})
    return req


def period_cost_report(period):
    inv = period.inventory_snapshots.order_by("-as_of").first()
    wip = period.wip_snapshots.order_by("-as_of").first()
    reconciliation = period.reconciliation_runs.order_by("-as_of").first()
    variance_rows = list(period.variance_postings.values("variance_type", "amount", "favorable"))
    debit, credit = _ledger_totals(period)
    return {
        "period": period.code, "status": period.status,
        "inventory_value": inv.total_value if inv else ZERO,
        "wip_value": wip.total_value if wip else ZERO,
        "variances": variance_rows,
        "variance_total": sum((row["amount"] for row in variance_rows), ZERO),
        "ledger_debits": debit, "ledger_credits": credit, "ledger_balanced": debit == credit,
        "reconciliation": None if not reconciliation else {
            "status": reconciliation.status,
            "quantity_variance": reconciliation.quantity_variance,
            "value_variance": reconciliation.value_variance,
        },
        "close_runs": period.close_runs.count(),
        "reopen_requests": period.reopen_requests.count(),
    }
