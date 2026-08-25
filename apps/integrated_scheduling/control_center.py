from __future__ import annotations

from datetime import timedelta
from decimal import Decimal

from django.db import transaction
from django.db.models import Q
from django.utils import timezone

from apps.demand.models import SalesOrderLine
from .models import (
    IntegratedScheduleScenario, ProductionSchedulePublication, RecoveryPlan, RecoveryPolicy,
    ReschedulingTrigger, ScheduleSolverRun,
)
from .execution import prepare_rescheduling_scenario
from .recovery import freeze_baseline_into_scenario, build_recovery_comparison, publish_recovery
from .commercial_pegging import commercial_impact_summary


STRATEGIES = [
    ("BALANCED", {"tardiness": 100, "priority_tardiness": 150, "makespan": 2, "setup": 10, "alternate_resource": 5, "labor_cost": 1}),
    ("DELIVERY_FIRST", {"tardiness": 180, "priority_tardiness": 260, "makespan": 2, "setup": 5, "alternate_resource": 4, "labor_cost": 1}),
    ("COST_STABLE", {"tardiness": 90, "priority_tardiness": 130, "makespan": 2, "setup": 18, "alternate_resource": 12, "labor_cost": 4}),
    ("MIN_CHANGE", {"tardiness": 110, "priority_tardiness": 150, "makespan": 3, "setup": 10, "alternate_resource": 20, "labor_cost": 1}),
]


def get_policy(plant):
    policy, _ = RecoveryPolicy.objects.get_or_create(plant=plant)
    return policy


def _candidate_slots(trigger):
    pub = trigger.publication
    if not pub:
        return []
    qs = pub.slots.filter(planned_end__gte=trigger.affected_from, actual_end__isnull=True).select_related(
        "operation__work_order__item", "machine", "work_center"
    )
    payload = trigger.payload or {}
    if trigger.trigger_type == ReschedulingTrigger.TriggerType.MACHINE_BREAKDOWN and trigger.source_id.isdigit():
        qs = qs.filter(machine_id=int(trigger.source_id))
    elif trigger.trigger_type == ReschedulingTrigger.TriggerType.MATERIAL_SHORTAGE and payload.get("work_order_id"):
        qs = qs.filter(operation__work_order_id=payload["work_order_id"])
    elif trigger.trigger_type == ReschedulingTrigger.TriggerType.LABOR_ABSENCE and trigger.source_id:
        # team_snapshot é JSON; a filtragem precisa ser portátil entre bancos, então fazemos em Python.
        return [s for s in qs if any(str(x.get("labor_resource_id", x.get("id", ""))) == str(trigger.source_id) for x in (s.team_snapshot or []) if isinstance(x, dict))]
    return list(qs)


def calculate_trigger_impact(trigger):
    slots = _candidate_slots(trigger)
    work_orders = {}
    item_ids = set()
    frozen = 0
    for slot in slots:
        wo = slot.operation.work_order
        work_orders[wo.pk] = wo
        item_ids.add(wo.item_id)
        frozen += int(slot.frozen)
    today = timezone.localdate()
    exact = commercial_impact_summary(trigger)
    if exact.get("exact"):
        sales = [
            {"number": x["sales_order"], "customer_code": x["customer_code"], "customer_name": x["customer_name"],
             "item": x["item"], "requested_date": x["requested_date"], "open_quantity": x["pegged_quantity"],
             "line_number": x["line_number"], "promise_status": x["status"]}
            for x in exact.get("lines", [])
        ]
        customer_impact_method = "EXACT_MRP_SOURCE"
    else:
        sales_qs = SalesOrderLine.objects.filter(
            sales_order__plant=trigger.plant, item_id__in=item_ids, requested_date__gte=today,
            sales_order__status__in=["CONFIRMED", "PARTIAL"],
        ).select_related("sales_order", "item").order_by("requested_date")[:100]
        sales = [
            {"number": l.sales_order.number, "customer_code": l.sales_order.customer_code, "customer_name": l.sales_order.customer_name,
             "item": l.item.code, "requested_date": l.requested_date.isoformat(), "open_quantity": str(l.open_quantity)}
            for l in sales_qs
        ]
        customer_impact_method = "LEGACY_INFERRED_BY_ITEM_DATE"
    base = {
        ReschedulingTrigger.TriggerType.MACHINE_BREAKDOWN: 40,
        ReschedulingTrigger.TriggerType.MATERIAL_SHORTAGE: 35,
        ReschedulingTrigger.TriggerType.LABOR_ABSENCE: 30,
        ReschedulingTrigger.TriggerType.PRIORITY_CHANGE: 20,
        ReschedulingTrigger.TriggerType.MANUAL: 15,
    }.get(trigger.trigger_type, 20)
    score = min(100, base + min(len(slots) * 2, 20) + min(len(work_orders) * 3, 18) + min(len(sales) * 4, 24) + min(frozen * 5, 15))
    severity = "LOW" if score < 25 else "MEDIUM" if score < 50 else "HIGH" if score < 75 else "CRITICAL"
    impact = {
        "affected_slots": len(slots), "affected_work_orders": len(work_orders), "frozen_slots": frozen,
        "impacted_sales_orders": len({x["number"] for x in sales}), "customers": sorted({x["customer_name"] for x in sales}),
        "sales_orders": sales,
        "customer_impact_method": customer_impact_method,
        "risk_score": score,
    }
    trigger.severity = severity
    trigger.impact_summary = impact
    policy = get_policy(trigger.plant)
    trigger.recovery_eta_seconds = policy.solver_time_limit_seconds * min(policy.candidate_count, len(STRATEGIES))
    trigger.save(update_fields=["severity", "impact_summary", "recovery_eta_seconds", "updated_at"])
    return impact


def _clone_recovery_scenario(trigger, name, horizon_days=14):
    start = timezone.localdate(trigger.affected_from)
    scenario = IntegratedScheduleScenario.objects.create(
        name=name, plant=trigger.plant, horizon_start=start, horizon_end=start + timedelta(days=max(1, horizon_days)-1),
        scheduling_direction="FORWARD", finite_by_machine=True, allow_alternate_resources=True, respect_industrial_calendar=True,
        dispatch_rule="PRIORITY", minimize_setups=True,
        parameters={"rescheduling_trigger_id": trigger.pk, "freeze_publication_id": trigger.publication_id,
                    "affected_from": trigger.affected_from.isoformat(), "event_payload": trigger.payload},
        created_by=trigger.created_by,
    )
    freeze_baseline_into_scenario(trigger, scenario)
    return scenario


@transaction.atomic
def create_recovery_plans(trigger, *, candidate_count=None, horizon_days=14):
    policy = get_policy(trigger.plant)
    count = max(1, min(int(candidate_count or policy.candidate_count), len(STRATEGIES)))
    calculate_trigger_impact(trigger)
    plans = []
    for i, (strategy, weights) in enumerate(STRATEGIES[:count], start=1):
        name = f"{strategy} #{trigger.pk}"
        plan = RecoveryPlan.objects.filter(trigger=trigger, name=name).first()
        if plan:
            plans.append(plan); continue
        scenario = _clone_recovery_scenario(trigger, f"Recovery #{trigger.pk} · {strategy}", horizon_days=horizon_days)
        plan = RecoveryPlan.objects.create(trigger=trigger, name=name, strategy=strategy, scenario=scenario, status=RecoveryPlan.Status.QUEUED, rank=i, metrics={"weights": weights})
        plans.append(plan)
    trigger.status = ReschedulingTrigger.Status.SOLVING
    trigger.save(update_fields=["status", "updated_at"])
    return plans


def score_plan(plan):
    if not plan.solver_run or plan.solver_run.status not in {ScheduleSolverRun.Status.OPTIMAL, ScheduleSolverRun.Status.FEASIBLE}:
        return None
    cmp = build_recovery_comparison_for_plan(plan)
    s = cmp["summary"]
    max_delay = max([abs(r.get("delta_minutes") or 0) for r in cmp["rows"]] or [0])
    impacted_sales = int((plan.trigger.impact_summary or {}).get("impacted_sales_orders", 0))
    risk = min(100, s.get("late_operations", 0)*20 + s.get("machine_changes", 0)*6 + s.get("moved_operations", 0)*2 + impacted_sales*8 + min(max_delay/10, 20))
    policy = get_policy(plan.trigger.plant)
    low = (risk <= float(policy.max_risk_score) and s.get("moved_operations", 0) <= policy.max_moved_operations
           and s.get("late_operations", 0) <= policy.max_late_operations and s.get("machine_changes", 0) <= policy.max_machine_changes
           and impacted_sales <= policy.max_impacted_sales_orders and max_delay <= policy.max_delay_minutes)
    plan.risk_score = Decimal(str(round(risk, 2)))
    plan.low_risk = low
    plan.auto_publish_eligible = bool(policy.is_active and policy.auto_publish_enabled and low)
    commercial = commercial_impact_summary(plan.trigger, plan=plan)
    if commercial.get("exact"):
        impacted_sales = commercial.get("impacted_sales_orders", impacted_sales)
        s["impacted_sales_orders"] = impacted_sales
        s["late_sales_orders"] = commercial.get("late_sales_orders", 0)
        s["commercial_pegging_method"] = commercial.get("method")
    plan.metrics = {**(plan.metrics or {}), **s, "max_delay_minutes": max_delay}
    plan.impact = plan.trigger.impact_summary or {}
    plan.status = RecoveryPlan.Status.READY
    plan.save(update_fields=["risk_score", "low_risk", "auto_publish_eligible", "metrics", "impact", "status", "updated_at"])
    return plan


def build_recovery_comparison_for_plan(plan):
    trigger = plan.trigger
    original = trigger.resulting_solver_run_id
    try:
        trigger.resulting_solver_run = plan.solver_run
        return build_recovery_comparison(trigger)
    finally:
        trigger.resulting_solver_run_id = original


def rank_recovery_plans(trigger):
    ready = list(trigger.recovery_plans.filter(status=RecoveryPlan.Status.READY).select_related("solver_run"))
    ready.sort(key=lambda p: (float(p.risk_score), int((p.metrics or {}).get("late_operations", 0)), int((p.metrics or {}).get("moved_operations", 0)), float(p.solver_run.objective_value or 0)))
    for rank, plan in enumerate(ready, 1):
        if plan.rank != rank:
            plan.rank = rank; plan.save(update_fields=["rank", "updated_at"])
    return ready


def maybe_auto_publish(trigger):
    policy = get_policy(trigger.plant)
    if not (policy.is_active and policy.auto_publish_enabled):
        return None
    trigger.auto_publish_attempted_at = timezone.now()
    trigger.save(update_fields=["auto_publish_attempted_at", "updated_at"])
    plans = rank_recovery_plans(trigger)
    if not plans or not plans[0].auto_publish_eligible:
        return None
    best = plans[0]
    trigger.resulting_scenario = best.scenario
    trigger.resulting_solver_run = best.solver_run
    trigger.save(update_fields=["resulting_scenario", "resulting_solver_run", "updated_at"])
    pub = publish_recovery(trigger, actor=trigger.created_by, notes=f"Auto-publicação 0.7.2 · {best.name}")
    best.status = RecoveryPlan.Status.PUBLISHED
    best.save(update_fields=["status", "updated_at"])
    trigger.auto_published_at = timezone.now()
    trigger.save(update_fields=["auto_published_at", "updated_at"])
    return pub
