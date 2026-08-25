from __future__ import annotations

from decimal import Decimal
from math import sqrt

from django.core.exceptions import ValidationError
from django.db import transaction

from apps.common.services import append_domain_event
from apps.production.models import WorkOrderOperation

from .advanced import run_finite_scenario
from .models import (
    IntegratedScheduleBlock,
    IntegratedScheduleConflict,
    IntegratedScheduleScenario,
    ScheduleOptimizationCandidate,
    ScheduleOptimizationRun,
)

ZERO = Decimal("0")
DEFAULT_WEIGHTS = {
    "lateness": Decimal("0.30"),
    "setup": Decimal("0.20"),
    "overtime": Decimal("0.15"),
    "priority_tardiness": Decimal("0.15"),
    "utilization_imbalance": Decimal("0.10"),
    "conflicts": Decimal("0.10"),
}


def _weights(raw):
    values = {k: max(ZERO, Decimal(str((raw or {}).get(k, v)))) for k, v in DEFAULT_WEIGHTS.items()}
    total = sum(values.values(), ZERO)
    if total <= 0:
        raise ValidationError("Ao menos um peso de otimização deve ser maior que zero.")
    return {k: v / total for k, v in values.items()}


def _clone_scenario(base, *, name, rule, direction, minimize_setups, campaign_mode, actor):
    return IntegratedScheduleScenario.objects.create(
        name=name,
        plant=base.plant,
        horizon_start=base.horizon_start,
        horizon_end=base.horizon_end,
        include_planned_production=base.include_planned_production,
        include_maintenance=base.include_maintenance,
        parameters={**(base.parameters or {}), "optimizer_parent_scenario_id": base.pk},
        scheduling_direction=direction,
        finite_by_machine=base.finite_by_machine,
        allow_alternate_resources=base.allow_alternate_resources,
        respect_industrial_calendar=base.respect_industrial_calendar,
        dispatch_rule=rule,
        minimize_setups=minimize_setups,
        campaign_mode=campaign_mode,
        created_by=actor,
    )


def _metric_snapshot(scenario):
    blocks = list(scenario.blocks.filter(block_type=IntegratedScheduleBlock.BlockType.PRODUCTION).select_related("machine"))
    conflicts = list(scenario.conflicts.all())
    late = sum((Decimal(b.late_hours or 0) for b in blocks), ZERO)
    setup = sum((Decimal(b.sequence_setup_hours or 0) for b in blocks), ZERO)
    overtime = ZERO
    for block in blocks:
        overtime += sum((Decimal(seg.effective_hours or 0) for seg in block.segments.filter(segment_type="OVERTIME")), ZERO)

    priority_tardiness = ZERO
    for block in blocks:
        if not block.late_hours:
            continue
        priority = Decimal(str(block.details.get("commercial_priority", 50) or 50)) / Decimal("100")
        if priority == Decimal("0.5"):
            try:
                op = WorkOrderOperation.objects.select_related("work_order__item").get(pk=int(block.source_id))
                profile = op.work_order.item.scheduling_profiles.filter(plant=scenario.plant).first()
                priority = Decimal(profile.commercial_priority if profile else 50) / Decimal("100")
            except Exception:
                pass
        priority_tardiness += Decimal(block.late_hours) * priority

    machine_hours = {}
    for block in blocks:
        key = str(block.machine_id or f"WC-{block.work_center_id}")
        hours = sum((Decimal(seg.effective_hours or 0) for seg in block.segments.all()), ZERO)
        if hours <= 0:
            hours = Decimal(str(max(0, (block.simulated_end - block.simulated_start).total_seconds()) / 3600))
        machine_hours[key] = machine_hours.get(key, ZERO) + hours
    vals = [float(v) for v in machine_hours.values()]
    imbalance = Decimal("0")
    if len(vals) > 1:
        mean = sum(vals) / len(vals)
        variance = sum((v - mean) ** 2 for v in vals) / len(vals)
        imbalance = Decimal(str(sqrt(variance)))

    critical = sum(c.severity == IntegratedScheduleConflict.Severity.CRITICAL for c in conflicts)
    return {
        "lateness": late,
        "setup": setup,
        "overtime": overtime,
        "priority_tardiness": priority_tardiness,
        "utilization_imbalance": imbalance,
        "conflicts": Decimal(len(conflicts)),
        "critical_conflicts": critical,
        "shifted_operations": int((scenario.simulated_summary or {}).get("shifted_operations", 0) or 0),
    }


def _normalize(candidates, key):
    vals = [Decimal(str(c.metrics.get(key, "0"))) for c in candidates]
    low, high = min(vals), max(vals)
    if high == low:
        return {c.pk: ZERO for c in candidates}
    return {c.pk: (Decimal(str(c.metrics.get(key, "0"))) - low) / (high - low) for c in candidates}


def _pareto(candidates):
    keys = ["lateness", "setup", "overtime", "priority_tardiness", "utilization_imbalance", "conflicts"]
    result = set()
    feasible = [c for c in candidates if c.feasible]
    for a in feasible:
        a_vals = [Decimal(str(a.metrics.get(k, "0"))) for k in keys]
        dominated = False
        for b in feasible:
            if a.pk == b.pk:
                continue
            b_vals = [Decimal(str(b.metrics.get(k, "0"))) for k in keys]
            if all(x <= y for x, y in zip(b_vals, a_vals)) and any(x < y for x, y in zip(b_vals, a_vals)):
                dominated = True
                break
        if not dominated:
            result.add(a.pk)
    return result


@transaction.atomic
def optimize_schedule(*, base_scenario, candidate_count=8, weights=None, actor=None):
    candidate_count = max(2, min(int(candidate_count), 12))
    normalized_weights = _weights(weights)
    run = ScheduleOptimizationRun.objects.create(
        base_scenario=base_scenario, status=ScheduleOptimizationRun.Status.RUNNING,
        candidate_count=candidate_count,
        weights={k: str(v) for k, v in normalized_weights.items()}, created_by=actor,
    )
    strategies = [
        ("EDD-FWD", "EDD", "FORWARD", True, False),
        ("SPT-FWD", "SPT", "FORWARD", True, False),
        ("CR-FWD", "CR", "FORWARD", True, False),
        ("PRIORITY-FWD", "PRIORITY", "FORWARD", True, False),
        ("SETUP-FWD", "SETUP_MIN", "FORWARD", True, False),
        ("SETUP-CAMPAIGN", "SETUP_MIN", "FORWARD", True, True),
        ("EDD-BWD", "EDD", "BACKWARD", True, False),
        ("PRIORITY-BWD", "PRIORITY", "BACKWARD", True, False),
        ("CR-BWD", "CR", "BACKWARD", True, False),
        ("SPT-BWD", "SPT", "BACKWARD", True, False),
        ("EDD-NOSETUP", "EDD", "FORWARD", False, False),
        ("PRIORITY-CAMPAIGN", "PRIORITY", "FORWARD", True, True),
    ][:candidate_count]
    candidates = []
    try:
        for code, rule, direction, minimize, campaign in strategies:
            scenario = _clone_scenario(
                base_scenario, name=f"{base_scenario.name} · {code}", rule=rule, direction=direction,
                minimize_setups=minimize, campaign_mode=campaign, actor=actor,
            )
            run_finite_scenario(scenario=scenario, actor=actor)
            metrics = _metric_snapshot(scenario)
            candidate = ScheduleOptimizationCandidate.objects.create(
                run=run, scenario=scenario, strategy_code=code,
                feasible=metrics["critical_conflicts"] == 0,
                metrics={k: str(v) if isinstance(v, Decimal) else v for k, v in metrics.items()},
            )
            candidates.append(candidate)

        norm_by_key = {k: _normalize(candidates, k) for k in normalized_weights}
        pareto_ids = _pareto(candidates)
        for candidate in candidates:
            norm = {k: norm_by_key[k][candidate.pk] for k in normalized_weights}
            score = sum((normalized_weights[k] * norm[k] for k in normalized_weights), ZERO)
            if not candidate.feasible:
                score += Decimal("10") + Decimal(str(candidate.metrics.get("critical_conflicts", 0)))
            candidate.objective_score = score
            candidate.normalized_metrics = {k: str(v) for k, v in norm.items()}
            candidate.pareto_front = candidate.pk in pareto_ids
            candidate.save(update_fields=["objective_score", "normalized_metrics", "pareto_front", "updated_at"])

        ranked = sorted(candidates, key=lambda c: (not c.feasible, c.objective_score, c.pk))
        for idx, candidate in enumerate(ranked, start=1):
            candidate.rank = idx
            candidate.save(update_fields=["rank", "updated_at"])
        best = ranked[0] if ranked else None
        run.status = ScheduleOptimizationRun.Status.COMPLETED
        run.best_candidate = best
        run.summary = {
            "candidates": len(ranked), "feasible_candidates": sum(c.feasible for c in ranked),
            "pareto_candidates": sum(c.pareto_front for c in ranked),
            "best_candidate_id": best.pk if best else None,
            "best_scenario_id": best.scenario_id if best else None,
            "best_score": str(best.objective_score) if best else None,
        }
        run.save(update_fields=["status", "best_candidate", "summary", "updated_at"])
        append_domain_event(
            event_type="MULTIOBJECTIVE_SCHEDULE_OPTIMIZED", aggregate_type="ScheduleOptimizationRun",
            aggregate_id=str(run.pk), actor=actor, payload=run.summary,
            idempotency_key=f"schedule-opt:{run.pk}",
        )
        return run
    except Exception as exc:
        run.status = ScheduleOptimizationRun.Status.FAILED
        run.error_message = str(exc)
        run.save(update_fields=["status", "error_message", "updated_at"])
        raise
