from __future__ import annotations

from collections import defaultdict
from datetime import datetime, timedelta
from math import ceil

from django.db.models import Q
from django.utils import timezone

from .models import (
    IndustrialShiftBreak,
    LaborRuleSet,
    LaborResource,
    LaborResourceSkill,
    LaborShiftAssignment,
    LaborUnavailability,
    OperationLaborRequirement,
)


def _aware(dt):
    return timezone.make_aware(dt) if timezone.is_naive(dt) else dt


def _subtract(intervals, cut_start, cut_end):
    out = []
    for start, end, meta in intervals:
        if cut_end <= start or cut_start >= end:
            out.append((start, end, meta))
            continue
        if cut_start > start:
            out.append((start, min(cut_start, end), meta))
        if cut_end < end:
            out.append((max(cut_end, start), end, meta))
    return [(s, e, m) for s, e, m in out if e > s]


def labor_windows(*, resource, center, start_date, end_date):
    """Calendário efetivo do trabalhador baseado em turnos, pausas e indisponibilidades."""
    assignments = LaborShiftAssignment.objects.filter(
        labor_resource=resource,
        shift__work_center=center,
        is_active=True,
    ).select_related("shift").filter(
        Q(effective_from__isnull=True) | Q(effective_from__lte=end_date),
        Q(effective_to__isnull=True) | Q(effective_to__gte=start_date),
    )
    absences = list(LaborUnavailability.objects.filter(
        labor_resource=resource,
        end__gt=_aware(datetime.combine(start_date, datetime.min.time())),
        start__lt=_aware(datetime.combine(end_date + timedelta(days=1), datetime.min.time())),
    ).order_by("start"))
    rows = []
    day = start_date
    while day <= end_date:
        for ass in assignments:
            shift = ass.shift
            if shift.weekday != day.weekday():
                continue
            if ass.effective_from and day < ass.effective_from:
                continue
            if ass.effective_to and day > ass.effective_to:
                continue
            start = _aware(datetime.combine(day, shift.start_time))
            end_day = day + timedelta(days=1) if shift.end_time <= shift.start_time else day
            end = _aware(datetime.combine(end_day, shift.end_time))
            pieces = [(start, end, {"shift": shift, "shift_name": shift.name})]
            for brk in IndustrialShiftBreak.objects.filter(shift=shift, is_active=True):
                bs = _aware(datetime.combine(day, brk.start_time))
                be_day = day + timedelta(days=1) if brk.end_time <= brk.start_time else day
                be = _aware(datetime.combine(be_day, brk.end_time))
                pieces = _subtract(pieces, bs, be)
            for absence in absences:
                pieces = _subtract(pieces, absence.start, absence.end)
            rows.extend(pieces)
        day += timedelta(days=1)
    return sorted(rows, key=lambda x: x[0])


def eligible_resources(requirement, *, plant):
    qs = LaborResource.objects.filter(plant=plant, is_active=True)
    skill_rows = LaborResourceSkill.objects.filter(
        skill=requirement.skill,
        proficiency__gte=requirement.min_proficiency,
        labor_resource__in=qs,
    ).select_related("labor_resource", "skill")
    today = timezone.localdate()
    return [
        row.labor_resource for row in skill_rows
        if not row.valid_until or row.valid_until >= today
    ]



def _active_rule(plant, on_date):
    return (LaborRuleSet.objects.filter(plant=plant, is_active=True, effective_from__lte=on_date)
            .filter(Q(effective_to__isnull=True) | Q(effective_to__gte=on_date)).order_by("-effective_from").first())

def _apply_labor_limits_and_costs(model, scenario, usage, granularity):
    """Hard limits by day/week and linear base/overtime/preference cost terms."""
    cost_terms=[]; overtime_terms=[]
    for (worker, day), rows in usage.get('daily', {}).items():
        rule=_active_rule(scenario.plant, day)
        max_h=float(rule.max_daily_hours if rule else 10); normal_h=float(rule.normal_daily_hours if rule else 8)
        max_ticks=max(1,int(max_h*60/granularity)); normal_ticks=max(0,int(normal_h*60/granularity))
        expr=sum(ticks*var for var,ticks in rows); model.Add(expr <= max_ticks)
        ot=model.NewIntVar(0,max_ticks,f"labor_ot_{worker.pk}_{day:%Y%m%d}"); model.Add(ot >= expr-normal_ticks); model.Add(ot >= 0)
        if rule and not rule.overtime_allowed: model.Add(expr <= normal_ticks)
        premium=max(0,float((rule.overtime_multiplier if rule else 1.5)-1)); cents_per_tick=int(round(float(worker.hourly_cost or 0)*100*granularity/60))
        if cents_per_tick: overtime_terms.append((ot,max(0,int(round(cents_per_tick*premium)))))
    for (worker, week), rows in usage.get('weekly', {}).items():
        sample_day=rows[0][2]; rule=_active_rule(scenario.plant,sample_day); max_h=float(rule.max_weekly_hours if rule else 44)
        model.Add(sum(ticks*var for var,ticks,_ in rows) <= max(1,int(max_h*60/granularity)))
    for var, worker, ticks in usage.get('base',[]):
        cents=int(round(float(worker.hourly_cost or 0)*100*(ticks*granularity)/60))
        pref_penalty=max(0,100-int(worker.preference_score or 0))
        if cents: cost_terms.append((var,cents))
        if pref_penalty: cost_terms.append((var,pref_penalty))
    return {'base_cost_terms':cost_terms,'overtime_cost_terms':overtime_terms}

def add_nonpreemptive_labor_constraints(*, model, scenario, operations, alternatives, origin, horizon_end, granularity):
    """Acopla mão de obra às alternativas de máquina/janela do CP-SAT não-preemptivo."""
    labor_intervals = defaultdict(list)
    assignment_vars = defaultdict(list)
    selected_vars = []
    usage = {"daily": defaultdict(list), "weekly": defaultdict(list), "base": []}
    requirements_by_op = {
        op_id: list(OperationLaborRequirement.objects.filter(operation=op).select_related("skill"))
        for op_id, op in operations.items()
    }
    for op_id, requirements in requirements_by_op.items():
        if not requirements:
            continue
        for alt_index, alt in enumerate(alternatives[op_id]):
            per_worker = defaultdict(list)
            for req in requirements:
                choices = []
                for worker in eligible_resources(req, plant=scenario.plant):
                    for win_index, (ws, we, winmeta) in enumerate(labor_windows(
                        resource=worker, center=alt["center"], start_date=scenario.horizon_start, end_date=scenario.horizon_end
                    )):
                        low = max(0, int((ws - origin).total_seconds() // (granularity * 60)))
                        high_end = max(0, int((we - origin).total_seconds() // (granularity * 60)))
                        if high_end - low < alt["duration_ticks"]:
                            continue
                        use = model.NewBoolVar(f"lab_{op_id}_{alt_index}_{req.pk}_{worker.pk}_{win_index}")
                        model.Add(use <= alt["presence"])
                        model.Add(alt["start"] >= low).OnlyEnforceIf(use)
                        model.Add(alt["end"] <= high_end).OnlyEnforceIf(use)
                        rest_ticks = int(ceil(float(worker.min_rest_hours or 0) * 60 / granularity))
                        extended_end = model.NewIntVar(0, max(high_end + rest_ticks, 1) + 100000, f"labend_{op_id}_{alt_index}_{req.pk}_{worker.pk}_{win_index}")
                        model.Add(extended_end == alt["end"] + rest_ticks).OnlyEnforceIf(use)
                        interval = model.NewOptionalIntervalVar(
                            alt["start"], alt["duration_ticks"] + rest_ticks, extended_end, use,
                            f"labi_{op_id}_{alt_index}_{req.pk}_{worker.pk}_{win_index}",
                        )
                        labor_intervals[worker.pk].append(interval)
                        choices.append(use)
                        per_worker[worker.pk].append(use)
                        selected_vars.append((use, {"operation_id": op_id, "worker": worker, "requirement": req, "alt": alt, "shift_name": winmeta["shift_name"], "duration_minutes": alt["duration_ticks"]*granularity}))
                        ticks=alt["duration_ticks"]; usage["daily"][(worker, ws.date())].append((use,ticks)); usage["weekly"][(worker, ws.isocalendar()[:2])].append((use,ticks,ws.date())); usage["base"].append((use,worker,ticks))
                if choices:
                    model.Add(sum(choices) == int(req.min_workers) * alt["presence"])
                else:
                    model.Add(alt["presence"] == 0)
                assignment_vars[(op_id, alt_index, req.pk)] = choices
            for worker_vars in per_worker.values():
                model.Add(sum(worker_vars) <= alt["presence"])
    for intervals in labor_intervals.values():
        model.AddNoOverlap(intervals)
    costs=_apply_labor_limits_and_costs(model, scenario, usage, granularity)
    return {"selected_vars": selected_vars, "assignment_vars": assignment_vars, "labor_intervals": labor_intervals, **costs}


def add_preemptive_labor_constraints(*, model, scenario, operations, chunk_alternatives, origin, granularity):
    """Mão de obra por segmento; permite handoff de equipe entre segmentos/turnos."""
    labor_intervals = defaultdict(list)
    selected_vars = []
    usage = {"daily": defaultdict(list), "weekly": defaultdict(list), "base": []}
    requirements_by_op = {
        op_id: list(OperationLaborRequirement.objects.filter(operation=op).select_related("skill"))
        for op_id, op in operations.items()
    }
    worker_segment_vars = defaultdict(list)
    segment_sequences = defaultdict(set)
    for (op_id, seq), choices in chunk_alternatives.items():
        requirements = requirements_by_op.get(op_id, [])
        if not requirements:
            continue
        for alt_index, alt in enumerate(choices):
            per_worker = defaultdict(list)
            for req in requirements:
                vars_ = []
                for worker in eligible_resources(req, plant=scenario.plant):
                    for win_index, (ws, we, winmeta) in enumerate(labor_windows(
                        resource=worker, center=alt["center"], start_date=scenario.horizon_start, end_date=scenario.horizon_end
                    )):
                        low = max(0, int((ws - origin).total_seconds() // (granularity * 60)))
                        high_end = max(0, int((we - origin).total_seconds() // (granularity * 60)))
                        duration_ticks = max(1, int(ceil(alt["elapsed_minutes"] / granularity)))
                        if high_end - low < duration_ticks:
                            continue
                        use = model.NewBoolVar(f"plab_{op_id}_{seq}_{alt_index}_{req.pk}_{worker.pk}_{win_index}")
                        model.Add(use <= alt["presence"])
                        model.Add(alt["start"] >= low).OnlyEnforceIf(use)
                        model.Add(alt["end"] <= high_end).OnlyEnforceIf(use)
                        rest_ticks = int(ceil(float(worker.min_rest_hours or 0) * 60 / granularity))
                        extended_end = model.NewIntVar(0, high_end + rest_ticks + 100000, f"plabend_{op_id}_{seq}_{req.pk}_{worker.pk}_{win_index}")
                        model.Add(extended_end == alt["end"] + rest_ticks).OnlyEnforceIf(use)
                        interval = model.NewOptionalIntervalVar(
                            alt["start"], duration_ticks + rest_ticks, extended_end, use,
                            f"plabi_{op_id}_{seq}_{alt_index}_{req.pk}_{worker.pk}_{win_index}",
                        )
                        labor_intervals[worker.pk].append(interval)
                        vars_.append(use); per_worker[worker.pk].append(use)
                        worker_segment_vars[(op_id, req.pk, seq, worker.pk)].append(use)
                        segment_sequences[(op_id, req.pk)].add(seq)
                        selected_vars.append((use, {"operation_id": op_id, "segment_sequence": seq, "worker": worker, "requirement": req, "alt": alt, "shift_name": winmeta["shift_name"], "duration_minutes": alt["elapsed_minutes"]}))
                        ticks=duration_ticks; usage["daily"][(worker, ws.date())].append((use,ticks)); usage["weekly"][(worker, ws.isocalendar()[:2])].append((use,ticks,ws.date())); usage["base"].append((use,worker,ticks))
                if vars_:
                    model.Add(sum(vars_) == int(req.min_workers) * alt["presence"])
                else:
                    model.Add(alt["presence"] == 0)
            for worker_vars in per_worker.values():
                model.Add(sum(worker_vars) <= alt["presence"])
    for (op_id, req_id), sequences in segment_sequences.items():
        req = next((r for r in requirements_by_op.get(op_id, []) if r.pk == req_id), None)
        if req and not req.allow_shift_handoff and sequences:
            first_seq = min(sequences)
            worker_ids = {key[3] for key in worker_segment_vars if key[0] == op_id and key[1] == req_id}
            for worker_id in worker_ids:
                base = worker_segment_vars.get((op_id, req_id, first_seq, worker_id), [])
                for seq in sorted(sequences):
                    current = worker_segment_vars.get((op_id, req_id, seq, worker_id), [])
                    model.Add(sum(current) == sum(base))
    for intervals in labor_intervals.values():
        model.AddNoOverlap(intervals)
    costs=_apply_labor_limits_and_costs(model, scenario, usage, granularity)
    return {"selected_vars": selected_vars, "labor_intervals": labor_intervals, **costs}


def selected_labor_entries(*, solver, context):
    out = []
    for var, info in context.get("selected_vars", []):
        if solver.Value(var) == 1:
            out.append(info)
    return out
