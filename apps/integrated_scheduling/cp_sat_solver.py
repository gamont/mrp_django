from __future__ import annotations

from collections import defaultdict
from datetime import datetime, time, timedelta
from decimal import Decimal
from math import ceil

from django.core.exceptions import ValidationError
from django.utils import timezone

from apps.common.services import append_domain_event
from apps.masterdata.models import RoutingOperation
from apps.production.models import WorkOrderOperation
from apps.shopfloor.models import Machine

from .calendar_engine import resource_windows
from .models import (
    IntegratedScheduleBlock, IntegratedScheduleScenario, ScheduleOptimizationRun, ScheduleSolverAssignment,
    ScheduleSolverIncumbent, ScheduleSolverRun, ScheduleSolverLaborAssignment,
)
from .sequencing import family_for_block, setup_hours

DEFAULT_WEIGHTS = {
    "tardiness": 100,
    "priority_tardiness": 150,
    "makespan": 2,
    "setup": 10,
    "alternate_resource": 5,
    "labor_cost": 1,
}


def ortools_available():
    try:
        from ortools.sat.python import cp_model  # noqa: F401
        return True
    except Exception:
        return False


def _cp_model():
    try:
        from ortools.sat.python import cp_model
        return cp_model
    except Exception as exc:
        raise ValidationError(
            "OR-Tools não está instalado. Execute a imagem Docker atualizada (requirements inclui ortools>=9.14,<10)."
        ) from exc


def _aware(day, at=time.min):
    value = datetime.combine(day, at)
    return timezone.make_aware(value) if timezone.is_naive(value) else value


def _tick(dt, origin, granularity):
    return max(0, int((dt - origin).total_seconds() // (granularity * 60)))


def _dt(tick, origin, granularity):
    return origin + timedelta(minutes=tick * granularity)


def _operation_blocks(scenario):
    # Build baseline with the existing engine if necessary so the solver shares the same source population.
    from .advanced import run_finite_scenario
    if not scenario.blocks.filter(block_type=IntegratedScheduleBlock.BlockType.PRODUCTION).exists():
        run_finite_scenario(scenario=scenario, actor=scenario.created_by)
    qs = scenario.blocks.filter(block_type=IntegratedScheduleBlock.BlockType.PRODUCTION, source_type="WORK_ORDER_OPERATION")
    excluded = [int(x) for x in (scenario.parameters or {}).get("frozen_operation_ids", [])]
    if excluded:
        qs = qs.exclude(source_id__in=[str(x) for x in excluded])
    return list(qs.select_related("work_center", "machine").order_by("original_start", "pk"))


def _candidate_resources(operation, scenario):
    centers = [operation.work_center]
    if scenario.allow_alternate_resources and operation.work_order.routing_id:
        ro = RoutingOperation.objects.filter(
            routing_id=operation.work_order.routing_id, sequence=operation.sequence
        ).select_related("alternate_work_center").first()
        if ro and ro.alternate_work_center_id and ro.alternate_work_center_id != operation.work_center_id:
            centers.append(ro.alternate_work_center)
    resources = []
    for idx, center in enumerate(centers):
        machines = list(Machine.objects.filter(plant=scenario.plant, work_center=center, is_active=True).order_by("code"))
        if machines:
            resources.extend((center, m, idx > 0) for m in machines)
        else:
            resources.append((center, None, idx > 0))
    return resources




def _warm_start_blocks(scenario):
    """Use the best heuristic candidate when available; otherwise use the current scenario."""
    opt = (ScheduleOptimizationRun.objects.filter(base_scenario=scenario, status="COMPLETED")
           .select_related("best_candidate__scenario").order_by("-created_at").first())
    source = opt.best_candidate.scenario if opt and opt.best_candidate_id else scenario
    blocks = {
        int(b.source_id): b for b in source.blocks.filter(
            block_type=IntegratedScheduleBlock.BlockType.PRODUCTION, source_type="WORK_ORDER_OPERATION"
        ).select_related("work_center", "machine") if str(b.source_id).isdigit()
    }
    return source, blocks


def request_solver_cancel(run, *, reason="Solicitado pelo usuário"):
    now = timezone.now()
    ScheduleSolverRun.objects.filter(pk=run.pk, cancel_requested_at__isnull=True).update(
        cancel_requested_at=now, cancellation_reason=reason, progress={**(run.progress or {}), "cancel_requested": True}
    )
    run.refresh_from_db()
    return run

def _weight_map(raw):
    out = DEFAULT_WEIGHTS.copy()
    for key in out:
        if raw and key in raw:
            out[key] = max(0, int(raw[key]))
    if not any(out.values()):
        raise ValidationError("Ao menos um peso do solver deve ser maior que zero.")
    return out


def solve_cp_sat(*, scenario, actor=None, time_limit_seconds=30, workers=8, granularity_minutes=5, weights=None,
                 apply_to_scenario=True, relative_gap_limit=0, warm_start=True, run=None, execution_mode="SYNC",
                 preemptive_operations=False, max_consecutive_minutes=240, handoff_penalty=5, use_labor_constraints=True):

    if preemptive_operations:
        from .cp_sat_preemptive import solve_cp_sat_preemptive
        return solve_cp_sat_preemptive(
            scenario=scenario, actor=actor, time_limit_seconds=time_limit_seconds, workers=workers,
            granularity_minutes=granularity_minutes, weights=weights, apply_to_scenario=apply_to_scenario,
            relative_gap_limit=relative_gap_limit, warm_start=warm_start, run=run, execution_mode=execution_mode,
            max_consecutive_minutes=max_consecutive_minutes, handoff_penalty=handoff_penalty,
            use_labor_constraints=use_labor_constraints,
        )

    cp_model = _cp_model()
    granularity = max(1, min(int(granularity_minutes), 60))
    limit = max(1, min(int(time_limit_seconds), 3600))
    workers = max(1, min(int(workers), 64))
    weights = _weight_map(weights or {})

    gap_limit = max(Decimal("0"), min(Decimal(str(relative_gap_limit or 0)), Decimal("1")))
    if run is None:
        run = ScheduleSolverRun.objects.create(
            scenario=scenario, status=ScheduleSolverRun.Status.RUNNING, time_limit_seconds=limit,
            workers=workers, time_granularity_minutes=granularity, weights=weights, created_by=actor,
            relative_gap_limit=gap_limit, warm_start_enabled=bool(warm_start), execution_mode=execution_mode,
            use_labor_constraints=bool(use_labor_constraints),
            started_at=timezone.now(), progress={"phase": "model"},
        )
    else:
        run.status = ScheduleSolverRun.Status.RUNNING
        run.time_limit_seconds = limit
        run.workers = workers
        run.time_granularity_minutes = granularity
        run.weights = weights
        run.relative_gap_limit = gap_limit
        run.warm_start_enabled = bool(warm_start)
        run.execution_mode = execution_mode or run.execution_mode
        run.use_labor_constraints = bool(use_labor_constraints)
        run.started_at = timezone.now()
        run.finished_at = None
        run.error_message = ""
        run.progress = {"phase": "model"}
        run.save(update_fields=["status", "time_limit_seconds", "workers", "time_granularity_minutes", "weights",
                                "relative_gap_limit", "warm_start_enabled", "execution_mode", "use_labor_constraints", "started_at",
                                "finished_at", "error_message", "progress", "updated_at"])
    try:
        run.assignments.all().delete()
        run.incumbents.all().delete()
        blocks = _operation_blocks(scenario)
        if not blocks:
            raise ValidationError("O cenário não possui operações produtivas para otimizar.")
        operations = {
            int(b.source_id): WorkOrderOperation.objects.select_related("work_order__item", "work_order__routing", "work_center").get(pk=int(b.source_id))
            for b in blocks
        }
        block_by_op = {int(b.source_id): b for b in blocks}
        origin = _aware(scenario.horizon_start)
        horizon_end = _aware(scenario.horizon_end + timedelta(days=1))
        horizon_ticks = max(1, _tick(horizon_end, origin, granularity))

        model = cp_model.CpModel()
        starts, ends, presences = {}, {}, {}
        alternatives = defaultdict(list)
        machine_intervals = defaultdict(list)
        setup_terms = []
        alternate_terms = []

        # One optional interval for every feasible resource/calendar window. This makes the CP-SAT calendar-aware
        # while keeping operations non-preemptive in solver mode.
        for op_id, op in operations.items():
            block = block_by_op[op_id]
            required_hours = Decimal(block.required_hours or 0) + Decimal(block.sequence_setup_hours or 0)
            if required_hours <= 0:
                required_hours = Decimal(op.setup_hours or 0) + Decimal(op.run_hours or 0)
            required_hours = max(required_hours, Decimal("0.0834"))
            alt_index = 0
            for center, machine, is_alt in _candidate_resources(op, scenario):
                windows = resource_windows(
                    scenario=scenario, work_center=center, machine=machine,
                    start_date=scenario.horizon_start, end_date=scenario.horizon_end,
                ) if scenario.respect_industrial_calendar else [(origin, horizon_end, Decimal("1"), "REGULAR")]
                for ws, we, rate, kind in windows:
                    if rate <= 0:
                        continue
                    elapsed_minutes = int(ceil(float(required_hours / Decimal(rate)) * 60 / granularity) * granularity)
                    duration_ticks = max(1, elapsed_minutes // granularity)
                    low = _tick(max(ws, origin), origin, granularity)
                    high = _tick(min(we, horizon_end), origin, granularity) - duration_ticks
                    if high < low:
                        continue
                    suffix = f"{op_id}_{alt_index}"
                    presence = model.NewBoolVar(f"p_{suffix}")
                    start = model.NewIntVar(low, high, f"s_{suffix}")
                    end = model.NewIntVar(low + duration_ticks, high + duration_ticks, f"e_{suffix}")
                    interval = model.NewOptionalIntervalVar(start, duration_ticks, end, presence, f"i_{suffix}")
                    key = machine.pk if machine else f"WC-{center.pk}"
                    machine_intervals[key].append(interval)
                    alternatives[op_id].append({
                        "presence": presence, "start": start, "end": end, "duration_ticks": duration_ticks,
                        "center": center, "machine": machine, "alternate": is_alt, "kind": kind,
                        "rate": str(rate), "required_hours": str(required_hours),
                    })
                    if is_alt:
                        alternate_terms.append(presence)
                    alt_index += 1
            if not alternatives[op_id]:
                raise ValidationError(f"{op.work_order.number}/{op.sequence}: sem janela de calendário/recurso suficiente no horizonte.")
            model.Add(sum(a["presence"] for a in alternatives[op_id]) == 1)
            starts[op_id] = model.NewIntVar(0, horizon_ticks, f"start_{op_id}")
            ends[op_id] = model.NewIntVar(0, horizon_ticks, f"end_{op_id}")
            for a in alternatives[op_id]:
                model.Add(starts[op_id] == a["start"]).OnlyEnforceIf(a["presence"])
                model.Add(ends[op_id] == a["end"]).OnlyEnforceIf(a["presence"])

        # Fixed maintenance occupies the same resource and is part of the global no-overlap model.
        for mb in scenario.blocks.filter(block_type__in=[IntegratedScheduleBlock.BlockType.MAINTENANCE, IntegratedScheduleBlock.BlockType.CAPACITY_LOSS]).select_related("machine", "work_center"):
            ms = _tick(max(mb.simulated_start, origin), origin, granularity)
            me = _tick(min(mb.simulated_end, horizon_end), origin, granularity)
            if me <= ms:
                continue
            fixed = model.NewIntervalVar(ms, me - ms, me, f"maint_{mb.pk}")
            if mb.machine_id:
                machine_intervals[mb.machine_id].append(fixed)
            else:
                # Center-wide maintenance blocks every active machine in that center; fallback center resource too.
                machines = list(Machine.objects.filter(plant=scenario.plant, work_center=mb.work_center, is_active=True))
                if machines:
                    for m in machines:
                        machine_intervals[m.pk].append(fixed)
                else:
                    machine_intervals[f"WC-{mb.work_center_id}"].append(fixed)

        for intervals in machine_intervals.values():
            model.AddNoOverlap(intervals)

        labor_context = None
        if run.use_labor_constraints:
            from .labor import add_nonpreemptive_labor_constraints
            labor_context = add_nonpreemptive_labor_constraints(
                model=model, scenario=scenario, operations=operations, alternatives=alternatives,
                origin=origin, horizon_end=horizon_end, granularity=granularity,
            )

        # Work-order technological precedence.
        by_wo = defaultdict(list)
        for op in operations.values():
            by_wo[op.work_order_id].append(op)
        for rows in by_wo.values():
            rows.sort(key=lambda x: x.sequence)
            for prev, nxt in zip(rows, rows[1:]):
                model.Add(starts[nxt.pk] >= ends[prev.pk])

        # Sequence-dependent setup on the same machine/resource, using pairwise disjunctions.
        op_ids = list(operations)
        families = {op_id: family_for_block(block_by_op[op_id]) for op_id in op_ids}
        machine_presence = defaultdict(dict)
        for op_id in op_ids:
            by_resource = defaultdict(list)
            for a in alternatives[op_id]:
                key = a["machine"].pk if a["machine"] else f"WC-{a['center'].pk}"
                by_resource[key].append(a["presence"])
            for key, vars_ in by_resource.items():
                mp = model.NewBoolVar(f"uses_{op_id}_{str(key).replace('-', '_')}")
                model.Add(mp == sum(vars_))
                machine_presence[key][op_id] = mp

        for key, presence_map in machine_presence.items():
            ids = list(presence_map)
            for ix, a_id in enumerate(ids):
                for b_id in ids[ix + 1:]:
                    a_before = model.NewBoolVar(f"ord_{a_id}_{b_id}_{str(key).replace('-', '_')}")
                    b_before = model.NewBoolVar(f"ord_{b_id}_{a_id}_{str(key).replace('-', '_')}")
                    pa, pb = presence_map[a_id], presence_map[b_id]
                    model.Add(a_before + b_before >= pa + pb - 1)
                    model.Add(a_before + b_before <= 1)
                    model.Add(a_before <= pa); model.Add(a_before <= pb)
                    model.Add(b_before <= pa); model.Add(b_before <= pb)
                    center = next(a["center"] for a in alternatives[a_id] if (a["machine"].pk if a["machine"] else f"WC-{a['center'].pk}") == key)
                    machine = next(a["machine"] for a in alternatives[a_id] if (a["machine"].pk if a["machine"] else f"WC-{a['center'].pk}") == key)
                    sab = setup_hours(scenario=scenario, work_center=center, machine=machine, from_family=families[a_id], to_family=families[b_id])
                    sba = setup_hours(scenario=scenario, work_center=center, machine=machine, from_family=families[b_id], to_family=families[a_id])
                    sab_ticks = int(ceil(float(sab) * 60 / granularity))
                    sba_ticks = int(ceil(float(sba) * 60 / granularity))
                    model.Add(starts[b_id] >= ends[a_id] + sab_ticks).OnlyEnforceIf(a_before)
                    model.Add(starts[a_id] >= ends[b_id] + sba_ticks).OnlyEnforceIf(b_before)
                    if sab_ticks:
                        setup_terms.append((a_before, sab_ticks))
                    if sba_ticks:
                        setup_terms.append((b_before, sba_ticks))

        # Objective: tardiness + commercial priority tardiness + makespan + setup + alternate-resource penalty.
        tardiness_terms, priority_terms = [], []
        for op_id, op in operations.items():
            due = _aware(op.work_order.due_date, time.max)
            due_tick = min(horizon_ticks, _tick(due, origin, granularity))
            tardy = model.NewIntVar(0, horizon_ticks, f"tardy_{op_id}")
            model.Add(tardy >= ends[op_id] - due_tick)
            tardiness_terms.append(tardy)
            priority = 50
            try:
                profile = op.work_order.item.scheduling_profiles.filter(plant=scenario.plant).first()
                priority = int(profile.commercial_priority if profile else 50)
            except Exception:
                pass
            priority_terms.append((tardy, max(1, priority)))
        makespan = model.NewIntVar(0, horizon_ticks, "makespan")
        model.AddMaxEquality(makespan, list(ends.values()))
        objective = []
        objective.extend(weights["tardiness"] * t for t in tardiness_terms)
        objective.extend(weights["priority_tardiness"] * p * t for t, p in priority_terms)
        objective.append(weights["makespan"] * makespan)
        objective.extend(weights["setup"] * ticks * lit for lit, ticks in setup_terms)
        objective.extend(weights["alternate_resource"] * 10 * lit for lit in alternate_terms)
        if labor_context and run.use_labor_costs:
            objective += [weights.get("labor_cost", 1) * coeff * var for var, coeff in labor_context.get("base_cost_terms", [])]
            objective += [weights.get("labor_cost", 1) * coeff * var for var, coeff in labor_context.get("overtime_cost_terms", [])]
        model.Minimize(sum(objective))

        # Warm start from the best heuristic scenario (or the current simulated scenario).
        if warm_start:
            warm_scenario, warm_blocks = _warm_start_blocks(scenario)
            hinted = 0
            for op_id, wb in warm_blocks.items():
                if op_id not in starts:
                    continue
                st = min(horizon_ticks, _tick(wb.simulated_start, origin, granularity))
                en = min(horizon_ticks, _tick(wb.simulated_end, origin, granularity))
                if en > st:
                    model.AddHint(starts[op_id], st)
                    model.AddHint(ends[op_id], en)
                matched_alt = None
                for a in alternatives[op_id]:
                    same_machine = (wb.machine_id and a["machine"] and wb.machine_id == a["machine"].pk)
                    same_center = (not wb.machine_id and wb.work_center_id == a["center"].pk)
                    if (same_machine or same_center) and matched_alt is None:
                        matched_alt = a
                if matched_alt is not None:
                    for a in alternatives[op_id]:
                        model.AddHint(a["presence"], 1 if a is matched_alt else 0)
                hinted += 1
            run.warm_start_source = "BEST_HEURISTIC" if warm_scenario.pk != scenario.pk else "CURRENT_SCENARIO"
            run.warm_start_scenario = warm_scenario
            run.progress = {"phase": "solve", "warm_start_operations": hinted}
            run.save(update_fields=["warm_start_source", "warm_start_scenario", "progress", "updated_at"])

        solver = cp_model.CpSolver()
        solver.parameters.max_time_in_seconds = float(limit)
        solver.parameters.num_search_workers = workers
        solver.parameters.log_search_progress = False
        if gap_limit > 0:
            solver.parameters.relative_gap_limit = float(gap_limit)

        class IncumbentCallback(cp_model.CpSolverSolutionCallback):
            def __init__(self, run_id):
                super().__init__()
                self.run_id = run_id
                self.sequence = 0

            def on_solution_callback(self):
                self.sequence += 1
                obj = Decimal(str(self.ObjectiveValue()))
                bound = Decimal(str(self.BestObjectiveBound()))
                denom = max(abs(obj), Decimal("1"))
                gap = abs(obj - bound) / denom
                now = timezone.now()
                ScheduleSolverIncumbent.objects.create(
                    run_id=self.run_id, sequence=self.sequence, objective_value=obj, best_bound=bound,
                    relative_gap=gap, wall_time_seconds=Decimal(str(round(self.WallTime(), 4))),
                    solution_count=self.sequence, summary={"objective": str(obj), "best_bound": str(bound), "gap": str(gap)},
                )
                ScheduleSolverRun.objects.filter(pk=self.run_id).update(
                    last_incumbent_at=now, progress={"phase": "solve", "incumbents": self.sequence,
                                                     "objective": str(obj), "best_bound": str(bound), "relative_gap": str(gap)}
                )
                if ScheduleSolverRun.objects.filter(pk=self.run_id, cancel_requested_at__isnull=False).exists():
                    self.StopSearch()

        callback = IncumbentCallback(run.pk)
        status = solver.Solve(model, callback)
        status_name = solver.StatusName(status)
        run.refresh_from_db(fields=["cancel_requested_at", "cancellation_reason"])
        cancelled = bool(run.cancel_requested_at)
        status_map = {
            "OPTIMAL": ScheduleSolverRun.Status.OPTIMAL, "FEASIBLE": ScheduleSolverRun.Status.FEASIBLE,
            "INFEASIBLE": ScheduleSolverRun.Status.INFEASIBLE, "UNKNOWN": ScheduleSolverRun.Status.UNKNOWN,
            "MODEL_INVALID": ScheduleSolverRun.Status.FAILED,
        }
        run.status = ScheduleSolverRun.Status.CANCELLED if cancelled else status_map.get(status_name, ScheduleSolverRun.Status.UNKNOWN)
        run.wall_time_seconds = Decimal(str(round(solver.WallTime(), 4)))
        run.conflicts = int(solver.NumConflicts())
        run.branches = int(solver.NumBranches())
        try:
            run.objective_value = Decimal(str(solver.ObjectiveValue()))
            run.best_bound = Decimal(str(solver.BestObjectiveBound()))
        except Exception:
            pass

        if status_name in {"OPTIMAL", "FEASIBLE"}:
            total_tardy = 0
            alternate_count = 0
            assignment_by_op = {}
            for op_id, op in operations.items():
                selected = next(a for a in alternatives[op_id] if solver.Value(a["presence"]) == 1)
                start_tick, end_tick = solver.Value(starts[op_id]), solver.Value(ends[op_id])
                start_dt, end_dt = _dt(start_tick, origin, granularity), _dt(end_tick, origin, granularity)
                due = _aware(op.work_order.due_date, time.max)
                tardy_minutes = max(0, int((end_dt - due).total_seconds() // 60))
                total_tardy += tardy_minutes
                alternate_count += int(selected["alternate"])
                assignment = ScheduleSolverAssignment.objects.create(
                    run=run, operation=op, work_center=selected["center"], machine=selected["machine"],
                    start=start_dt, end=end_dt, duration_minutes=(end_tick - start_tick) * granularity,
                    is_alternate_resource=selected["alternate"], tardiness_minutes=tardy_minutes,
                    details={"calendar_kind": selected["kind"], "capacity_rate": selected["rate"]},
                )
                assignment_by_op[op_id] = assignment
                if apply_to_scenario and not cancelled:
                    block = block_by_op[op_id]
                    block.work_center = selected["center"]
                    block.machine = selected["machine"]
                    block.simulated_start = start_dt
                    block.simulated_end = end_dt
                    block.assignment_reason = f"CP-SAT {status_name}"
                    block.details = {**(block.details or {}), "solver_run_id": run.pk, "solver_status": status_name}
                    block.save(update_fields=["work_center", "machine", "simulated_start", "simulated_end", "assignment_reason", "details", "updated_at"])
            labor_count = 0
            if labor_context:
                from .labor import selected_labor_entries
                for info in selected_labor_entries(solver=solver, context=labor_context):
                    assignment = assignment_by_op[info["operation_id"]]
                    ScheduleSolverLaborAssignment.objects.create(
                        run=run, assignment=assignment, operation_id=info["operation_id"],
                        labor_resource=info["worker"], skill=info["requirement"].skill,
                        start=assignment.start, end=assignment.end, shift_name=info.get("shift_name", ""), is_handoff=False,
                    )
                    labor_count += 1
            labor_cost_total = Decimal("0")
            if labor_count and run.use_labor_costs:
                from .labor_costing import calculate_run_labor_costs
                labor_cost_total = calculate_run_labor_costs(run)
            run.summary = {
                "status": "CANCELLED" if cancelled else status_name, "assignments": run.assignments.count(), "total_tardiness_minutes": total_tardy,
                "alternate_resource_assignments": alternate_count, "objective_value": str(run.objective_value),
                "best_bound": str(run.best_bound), "wall_time_seconds": str(run.wall_time_seconds),
                "granularity_minutes": granularity,
                "global_optimum_proven": status_name == "OPTIMAL" and gap_limit == 0 and not cancelled,
                "success_with_gap_tolerance": status_name == "OPTIMAL" and gap_limit > 0 and not cancelled,
                "relative_gap_limit": str(gap_limit), "warm_start_source": run.warm_start_source,
                "incumbents": run.incumbents.count(), "cancelled": cancelled,
                "labor_constraints": bool(run.use_labor_constraints), "labor_assignments": labor_count,
                "labor_costs": bool(run.use_labor_costs), "labor_cost_total": str(labor_cost_total),
            }
            if apply_to_scenario and not cancelled:
                scenario.status = IntegratedScheduleScenario.Status.COMPLETED
                scenario.simulated_summary = {**(scenario.simulated_summary or {}), "cp_sat": run.summary}
                scenario.save(update_fields=["status", "simulated_summary", "updated_at"])
        else:
            run.summary = {"status": status_name, "assignments": 0, "message": "Nenhuma solução factível encontrada dentro dos limites."}
        run.finished_at = timezone.now()
        run.progress = {**(run.progress or {}), "phase": "finished", "status": run.status}
        run.save(update_fields=["status", "objective_value", "best_bound", "wall_time_seconds", "conflicts", "branches",
                                "summary", "finished_at", "progress", "updated_at"])
        append_domain_event(
            event_type="CP_SAT_SCHEDULE_SOLVED", aggregate_type="ScheduleSolverRun", aggregate_id=str(run.pk), actor=actor,
            payload=run.summary, idempotency_key=f"cp-sat-solve:{run.pk}",
        )
        return run
    except Exception as exc:
        run.status = ScheduleSolverRun.Status.FAILED
        run.error_message = str(exc)
        run.finished_at = timezone.now()
        run.progress = {**(run.progress or {}), "phase": "failed", "error": str(exc)}
        run.save(update_fields=["status", "error_message", "finished_at", "progress", "updated_at"])
        raise
