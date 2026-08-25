from datetime import datetime, time
from decimal import Decimal

from django.utils import timezone

from .models import PublishedOperationSchedule, ScheduleOptimizationRun, ScheduleSolverRun


def _aware(day):
    dt = datetime.combine(day, time.max)
    return timezone.make_aware(dt) if timezone.is_naive(dt) else dt


def compare_solver_methods(scenario):
    rows = []
    opt = (ScheduleOptimizationRun.objects.filter(base_scenario=scenario, status="COMPLETED")
           .select_related("best_candidate__scenario").order_by("-created_at").first())
    if opt and opt.best_candidate_id:
        c = opt.best_candidate
        m = c.metrics or {}
        rows.append({
            "method": "HEURISTIC", "label": f"Heurístico · {c.strategy_code}", "status": "FEASIBLE" if c.feasible else "INFEASIBLE",
            "score": str(c.objective_score), "tardiness_minutes": str(Decimal(str(m.get("lateness_hours", 0) or 0)) * Decimal(60)),
            "setup_hours": str(m.get("setup_hours", 0)), "overtime_hours": str(m.get("overtime_hours", 0)),
            "conflicts": int(m.get("conflicts", 0) or 0), "reference_id": c.scenario_id,
        })

    cp = (ScheduleSolverRun.objects.filter(scenario=scenario, status__in=[ScheduleSolverRun.Status.OPTIMAL, ScheduleSolverRun.Status.FEASIBLE])
          .order_by("-created_at").first())
    if cp:
        rows.append({
            "method": "CP_SAT", "label": "CP-SAT", "status": cp.status,
            "score": str(cp.objective_value or ""),
            "tardiness_minutes": sum(a.tardiness_minutes for a in cp.assignments.all()),
            "setup_hours": "-",
            "overtime_hours": "-", "conflicts": cp.conflicts, "reference_id": cp.pk,
            "best_bound": str(cp.best_bound or ""), "incumbents": cp.incumbents.count(),
        })

    published = list(PublishedOperationSchedule.objects.filter(scenario=scenario).select_related("operation__work_order"))
    if published:
        tardy = 0
        for p in published:
            due = _aware(p.operation.work_order.due_date)
            tardy += max(0, int((p.planned_end - due).total_seconds() // 60))
        rows.append({
            "method": "PUBLISHED", "label": "Cronograma publicado", "status": "PUBLISHED", "score": "-",
            "tardiness_minutes": tardy, "setup_hours": "-", "overtime_hours": "-", "conflicts": "-",
            "reference_id": scenario.pk, "operations": len(published),
        })
    return rows
