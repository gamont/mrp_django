from __future__ import annotations

from datetime import date, timedelta
from decimal import Decimal
from django.db import transaction
from django.utils import timezone

from apps.planning.atp import calculate_atp
from apps.planning.capacity import execute_capacity_scenario
from apps.planning.models import CapacityScenario
from .models import SalesOrderPromise, CommercialServiceCase, RecoveryCommercialImpact


def current_approved_promise(line):
    return line.promise_history.filter(status=SalesOrderPromise.Status.APPROVED).order_by("-decided_at", "-created_at").first()


def evaluate_line_atp_ctp(line, *, actor=None, run_ctp=True, horizon_days=365):
    qty = Decimal(str(line.open_quantity))
    if qty <= 0:
        raise ValueError("Linha sem quantidade em aberto.")
    plant = line.sales_order.plant
    atp = calculate_atp(plant=plant, item=line.item, quantity=qty, requested_date=line.requested_date, horizon_days=horizon_days)
    atp_date = date.fromisoformat(atp["promised_date"]) if atp.get("promised_date") else None
    ctp = {}
    ctp_date = None
    if run_ctp:
        scenario = CapacityScenario.objects.create(
            name=f"CTP pedido {line.sales_order.number}/{line.line_number}", scenario_type=CapacityScenario.ScenarioType.CTP,
            plant=plant, item=line.item, quantity=qty, requested_release_date=timezone.localdate(),
            requested_due_date=line.requested_date, parameters={"include_open_orders": True, "capacity_overrides": {}, "sales_order_line_id": line.pk},
        )
        try:
            scenario = execute_capacity_scenario(scenario)
            ctp_date = scenario.promised_date
            ctp = {"scenario_id": scenario.pk, "feasible": scenario.feasible, "promised_date": ctp_date.isoformat() if ctp_date else None, "summary": scenario.summary}
        except Exception as exc:
            ctp = {"scenario_id": scenario.pk, "feasible": None, "promised_date": None, "error": str(exc)}
    dates = [d for d in [atp_date, ctp_date, line.requested_date] if d]
    suggested = max(dates)
    previous = current_approved_promise(line)
    proposal = SalesOrderPromise.objects.create(
        sales_order_line=line, source=SalesOrderPromise.Source.ATP_CTP, proposed_date=suggested,
        previous_approved_date=previous.proposed_date if previous else None, quantity=qty, atp_result=atp, ctp_result=ctp,
        rationale="Data sugerida pela maior restrição entre disponibilidade material (ATP) e capacidade (CTP).", proposed_by=actor,
    )
    _ensure_case(proposal)
    return proposal


def create_recovery_promise_proposals(trigger, plan, *, actor=None):
    proposals=[]
    impacts=RecoveryCommercialImpact.objects.filter(trigger=trigger, recovery_plan=plan, recovered_promise_date__isnull=False).select_related("sales_order_line")
    for impact in impacts:
        line=impact.sales_order_line
        previous=current_approved_promise(line)
        proposal=SalesOrderPromise.objects.create(
            sales_order_line=line, source=SalesOrderPromise.Source.RECOVERY, proposed_date=impact.recovered_promise_date,
            previous_approved_date=previous.proposed_date if previous else None, quantity=impact.pegged_quantity, trigger=trigger, recovery_plan=plan,
            rationale=f"Promessa sugerida pelo recovery {plan.name}; status {impact.promise_status}.", proposed_by=actor,
        )
        _ensure_case(proposal, trigger=trigger, plan=plan, priority="CRITICAL" if impact.promise_delta_days >= 2 else "HIGH" if impact.promise_delta_days >= 1 else "MEDIUM")
        proposals.append(proposal)
    return proposals


def _ensure_case(promise, trigger=None, plan=None, priority="MEDIUM"):
    return CommercialServiceCase.objects.create(
        sales_order_line=promise.sales_order_line, trigger=trigger, recovery_plan=plan, promise=promise, priority=priority,
        reason="PROMISE_CHANGE", notes="Revisar nova promessa antes de comunicar ao cliente.",
    )


@transaction.atomic
def approve_promise(promise, *, actor=None):
    promise = SalesOrderPromise.objects.select_for_update().get(pk=promise.pk)
    if promise.status != SalesOrderPromise.Status.PENDING:
        raise ValueError("Somente proposta pendente pode ser aprovada.")
    SalesOrderPromise.objects.filter(
        sales_order_line=promise.sales_order_line, status=SalesOrderPromise.Status.APPROVED
    ).exclude(pk=promise.pk).update(status=SalesOrderPromise.Status.SUPERSEDED, updated_at=timezone.now())
    promise.status=SalesOrderPromise.Status.APPROVED
    promise.decided_by=actor
    promise.decided_at=timezone.now()
    promise.save(update_fields=["status","decided_by","decided_at","updated_at"])
    promise.service_cases.filter(status__in=[CommercialServiceCase.Status.OPEN, CommercialServiceCase.Status.IN_REVIEW]).update(status=CommercialServiceCase.Status.WAITING_CUSTOMER, updated_at=timezone.now())
    return promise


@transaction.atomic
def reject_promise(promise, *, actor=None, reason=""):
    promise = SalesOrderPromise.objects.select_for_update().get(pk=promise.pk)
    if promise.status != SalesOrderPromise.Status.PENDING:
        raise ValueError("Somente proposta pendente pode ser rejeitada.")
    promise.status=SalesOrderPromise.Status.REJECTED
    promise.decided_by=actor
    promise.decided_at=timezone.now()
    if reason:
        promise.rationale=(promise.rationale+"\nRejeição: "+reason).strip()
    promise.save(update_fields=["status","decided_by","decided_at","rationale","updated_at"])
    promise.service_cases.update(status=CommercialServiceCase.Status.CLOSED, updated_at=timezone.now())
    return promise
