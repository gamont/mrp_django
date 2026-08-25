from __future__ import annotations

from collections import defaultdict
from datetime import time, timedelta
from decimal import Decimal
from math import ceil

from django.core.exceptions import ValidationError
from django.utils import timezone

from apps.common.services import append_domain_event
from apps.production.models import WorkOrderOperation
from apps.shopfloor.models import Machine

from .calendar_engine import resource_windows
from .models import (
    IntegratedScheduleBlock,
    IntegratedScheduleScenario,
    ScheduleSolverAssignment,
    ScheduleSolverIncumbent,
    ScheduleSolverRun,
    ScheduleSolverSegment,
    ScheduleSolverLaborAssignment,
)
from .sequencing import family_for_block, setup_hours


def _helpers():
    # Imported lazily to avoid a module import cycle with cp_sat_solver.
    from .cp_sat_solver import (
        _aware, _candidate_resources, _cp_model, _dt, _operation_blocks, _tick, _warm_start_blocks, _weight_map,
    )
    return _aware, _candidate_resources, _cp_model, _dt, _operation_blocks, _tick, _warm_start_blocks, _weight_map


def _resource_key(center, machine):
    return machine.pk if machine else f"WC-{center.pk}"


def _split_minutes(total_minutes: int, max_consecutive: int, granularity: int):
    max_chunk = max(granularity, (max_consecutive // granularity) * granularity)
    remaining = max(granularity, int(ceil(total_minutes / granularity) * granularity))
    out = []
    while remaining > 0:
        chunk = min(max_chunk, remaining)
        out.append(chunk)
        remaining -= chunk
    return out


def _shift_name(center, start_dt):
    try:
        local = timezone.localtime(start_dt)
        rows = center.shifts.filter(weekday=local.weekday(), is_active=True).order_by("start_time")
        for shift in rows:
            st, et = shift.start_time, shift.end_time
            tm = local.time().replace(tzinfo=None)
            if et > st and st <= tm < et:
                return shift.name
            if et <= st and (tm >= st or tm < et):
                return shift.name
    except Exception:
        pass
    return ""


def solve_cp_sat_preemptive(*, scenario, actor=None, time_limit_seconds=30, workers=8, granularity_minutes=5,
                            weights=None, apply_to_scenario=True, relative_gap_limit=0, warm_start=True,
                            run=None, execution_mode="SYNC", max_consecutive_minutes=240, handoff_penalty=5,
                            use_labor_constraints=True):
    _aware, _candidate_resources, _cp_model, _dt, _operation_blocks, _tick, _warm_start_blocks, _weight_map = _helpers()
    cp_model = _cp_model()
    granularity = max(1, min(int(granularity_minutes), 60))
    limit = max(1, min(int(time_limit_seconds), 7200))
    workers = max(1, min(int(workers), 64))
    max_consecutive = max(granularity, int(max_consecutive_minutes or 240))
    handoff_penalty = max(0, int(handoff_penalty or 0))
    weights = _weight_map(weights or {})
    gap_limit = max(Decimal("0"), min(Decimal(str(relative_gap_limit or 0)), Decimal("1")))

    if run is None:
        run = ScheduleSolverRun.objects.create(
            scenario=scenario, status=ScheduleSolverRun.Status.RUNNING, time_limit_seconds=limit,
            workers=workers, time_granularity_minutes=granularity, weights=weights, created_by=actor,
            relative_gap_limit=gap_limit, warm_start_enabled=bool(warm_start), execution_mode=execution_mode,
            preemptive_operations=True, max_consecutive_minutes=max_consecutive, handoff_penalty=handoff_penalty,
            use_labor_constraints=bool(use_labor_constraints),
            started_at=timezone.now(), progress={"phase": "model", "mode": "PREEMPTIVE"},
        )
    else:
        run.status = ScheduleSolverRun.Status.RUNNING
        run.preemptive_operations = True
        run.max_consecutive_minutes = max_consecutive
        run.handoff_penalty = handoff_penalty
        run.use_labor_constraints = bool(use_labor_constraints)
        run.time_limit_seconds = limit
        run.workers = workers
        run.time_granularity_minutes = granularity
        run.weights = weights
        run.relative_gap_limit = gap_limit
        run.warm_start_enabled = bool(warm_start)
        run.execution_mode = execution_mode or run.execution_mode
        run.started_at = timezone.now()
        run.finished_at = None
        run.error_message = ""
        run.progress = {"phase": "model", "mode": "PREEMPTIVE"}
        run.save(update_fields=[
            "status", "preemptive_operations", "max_consecutive_minutes", "handoff_penalty", "use_labor_constraints",
            "time_limit_seconds", "workers", "time_granularity_minutes", "weights", "relative_gap_limit",
            "warm_start_enabled", "execution_mode", "started_at", "finished_at", "error_message", "progress", "updated_at",
        ])

    try:
        run.assignments.all().delete()
        run.incumbents.all().delete()
        blocks = _operation_blocks(scenario)
        if not blocks:
            raise ValidationError("O cenário não possui operações produtivas para otimizar.")
        operations = {
            int(b.source_id): WorkOrderOperation.objects.select_related(
                "work_order__item", "work_order__routing", "work_center"
            ).get(pk=int(b.source_id)) for b in blocks
        }
        block_by_op = {int(b.source_id): b for b in blocks}
        origin = _aware(scenario.horizon_start)
        horizon_end = _aware(scenario.horizon_end + timedelta(days=1))
        horizon_ticks = max(1, _tick(horizon_end, origin, granularity))

        model = cp_model.CpModel()
        op_starts, op_ends = {}, {}
        op_resource_use = defaultdict(dict)
        chunk_alternatives = defaultdict(list)
        chunk_vars = defaultdict(list)
        machine_intervals = defaultdict(list)
        alternate_terms, handoff_terms, setup_terms = [], [], []
        total_segments = 0

        for op_id, op in operations.items():
            block = block_by_op[op_id]
            required_hours = Decimal(block.required_hours or 0)
            if required_hours <= 0:
                required_hours = Decimal(op.setup_hours or 0) + Decimal(op.run_hours or 0)
            required_minutes = max(granularity, int(ceil(float(required_hours) * 60)))
            chunks = _split_minutes(required_minutes, max_consecutive, granularity)
            total_segments += len(chunks)
            resources = _candidate_resources(op, scenario)
            resource_catalog = {}
            for center, machine, is_alt in resources:
                key = _resource_key(center, machine)
                resource_catalog[key] = (center, machine, is_alt)
                op_resource_use[op_id][key] = model.NewBoolVar(f"use_{op_id}_{str(key).replace('-', '_')}")
            model.Add(sum(op_resource_use[op_id].values()) == 1)

            previous_chunk_end = None
            for seq, processing_minutes in enumerate(chunks, start=1):
                chunk_key = (op_id, seq)
                processing_ticks = max(1, int(ceil(processing_minutes / granularity)))
                chunk_start = model.NewIntVar(0, horizon_ticks, f"seg_start_{op_id}_{seq}")
                chunk_end = model.NewIntVar(0, horizon_ticks, f"seg_end_{op_id}_{seq}")
                chunk_vars[op_id].append((chunk_start, chunk_end, processing_minutes))
                choices = []
                alt_ix = 0
                for key, (center, machine, is_alt) in resource_catalog.items():
                    windows = resource_windows(
                        scenario=scenario, work_center=center, machine=machine,
                        start_date=scenario.horizon_start, end_date=scenario.horizon_end,
                    ) if scenario.respect_industrial_calendar else [(origin, horizon_end, Decimal("1"), "REGULAR")]
                    for ws, we, rate, kind in windows:
                        if rate <= 0:
                            continue
                        elapsed_minutes = int(ceil((processing_minutes / float(rate)) / granularity) * granularity)
                        duration_ticks = max(1, elapsed_minutes // granularity)
                        low = _tick(max(ws, origin), origin, granularity)
                        high = _tick(min(we, horizon_end), origin, granularity) - duration_ticks
                        if high < low:
                            continue
                        presence = model.NewBoolVar(f"pseg_{op_id}_{seq}_{alt_ix}")
                        start = model.NewIntVar(low, high, f"sseg_{op_id}_{seq}_{alt_ix}")
                        end = model.NewIntVar(low + duration_ticks, high + duration_ticks, f"eseg_{op_id}_{seq}_{alt_ix}")
                        interval = model.NewOptionalIntervalVar(start, duration_ticks, end, presence, f"iseg_{op_id}_{seq}_{alt_ix}")
                        machine_intervals[key].append(interval)
                        model.Add(chunk_start == start).OnlyEnforceIf(presence)
                        model.Add(chunk_end == end).OnlyEnforceIf(presence)
                        model.Add(presence <= op_resource_use[op_id][key])
                        choice = {
                            "presence": presence, "start": start, "end": end, "center": center, "machine": machine,
                            "alternate": is_alt, "kind": kind, "rate": str(rate), "resource_key": key,
                            "processing_minutes": processing_minutes, "elapsed_minutes": elapsed_minutes,
                        }
                        choices.append(choice)
                        if is_alt:
                            alternate_terms.append(presence)
                        alt_ix += 1
                if not choices:
                    raise ValidationError(
                        f"{op.work_order.number}/{op.sequence}: segmento {seq} sem janela suficiente; "
                        f"reduza max_consecutive_minutes ou amplie o horizonte."
                    )
                model.Add(sum(c["presence"] for c in choices) == 1)
                # Every chunk must use the same resource selected for the operation.
                for key, use in op_resource_use[op_id].items():
                    on_key = [c["presence"] for c in choices if c["resource_key"] == key]
                    if on_key:
                        model.Add(sum(on_key) == use)
                    else:
                        model.Add(use == 0)
                chunk_alternatives[chunk_key] = choices
                if previous_chunk_end is not None:
                    model.Add(chunk_start >= previous_chunk_end)
                    handoff = model.NewBoolVar(f"handoff_{op_id}_{seq-1}_{seq}")
                    model.Add(chunk_start >= previous_chunk_end + 1).OnlyEnforceIf(handoff)
                    model.Add(chunk_start == previous_chunk_end).OnlyEnforceIf(handoff.Not())
                    handoff_terms.append(handoff)
                previous_chunk_end = chunk_end

            op_starts[op_id] = chunk_vars[op_id][0][0]
            op_ends[op_id] = chunk_vars[op_id][-1][1]

        # Fixed maintenance blocks resources in the same global no-overlap constraint.
        for mb in scenario.blocks.filter(block_type__in=[IntegratedScheduleBlock.BlockType.MAINTENANCE, IntegratedScheduleBlock.BlockType.CAPACITY_LOSS]).select_related("machine", "work_center"):
            ms = _tick(max(mb.simulated_start, origin), origin, granularity)
            me = _tick(min(mb.simulated_end, horizon_end), origin, granularity)
            if me <= ms:
                continue
            fixed = model.NewIntervalVar(ms, me - ms, me, f"maint_{mb.pk}")
            if mb.machine_id:
                machine_intervals[mb.machine_id].append(fixed)
            else:
                machines = list(Machine.objects.filter(plant=scenario.plant, work_center=mb.work_center, is_active=True))
                if machines:
                    for machine in machines:
                        machine_intervals[machine.pk].append(fixed)
                else:
                    machine_intervals[f"WC-{mb.work_center_id}"].append(fixed)
        for intervals in machine_intervals.values():
            model.AddNoOverlap(intervals)

        labor_context = None
        if run.use_labor_constraints:
            from .labor import add_preemptive_labor_constraints
            labor_context = add_preemptive_labor_constraints(
                model=model, scenario=scenario, operations=operations, chunk_alternatives=chunk_alternatives,
                origin=origin, granularity=granularity,
            )

        # Technological precedence between operations.
        by_wo = defaultdict(list)
        for op in operations.values():
            by_wo[op.work_order_id].append(op)
        for rows in by_wo.values():
            rows.sort(key=lambda x: x.sequence)
            for prev, nxt in zip(rows, rows[1:]):
                model.Add(op_starts[nxt.pk] >= op_ends[prev.pk])

        # Sequence-dependent setup between operations sharing a resource.
        families = {op_id: family_for_block(block_by_op[op_id]) for op_id in operations}
        resource_to_ops = defaultdict(dict)
        for op_id, uses in op_resource_use.items():
            for key, use in uses.items():
                resource_to_ops[key][op_id] = use
        for key, presence_map in resource_to_ops.items():
            ids = list(presence_map)
            for ix, a_id in enumerate(ids):
                for b_id in ids[ix + 1:]:
                    pa, pb = presence_map[a_id], presence_map[b_id]
                    a_before = model.NewBoolVar(f"pord_{a_id}_{b_id}_{str(key).replace('-', '_')}")
                    b_before = model.NewBoolVar(f"pord_{b_id}_{a_id}_{str(key).replace('-', '_')}")
                    model.Add(a_before + b_before >= pa + pb - 1)
                    model.Add(a_before + b_before <= 1)
                    model.Add(a_before <= pa); model.Add(a_before <= pb)
                    model.Add(b_before <= pa); model.Add(b_before <= pb)
                    # Lookup the common resource metadata from the first chunk choices.
                    sample = next(c for c in chunk_alternatives[(a_id, 1)] if c["resource_key"] == key)
                    center, machine = sample["center"], sample["machine"]
                    sab = setup_hours(scenario=scenario, work_center=center, machine=machine,
                                      from_family=families[a_id], to_family=families[b_id])
                    sba = setup_hours(scenario=scenario, work_center=center, machine=machine,
                                      from_family=families[b_id], to_family=families[a_id])
                    sab_ticks = int(ceil(float(sab) * 60 / granularity))
                    sba_ticks = int(ceil(float(sba) * 60 / granularity))
                    model.Add(op_starts[b_id] >= op_ends[a_id] + sab_ticks).OnlyEnforceIf(a_before)
                    model.Add(op_starts[a_id] >= op_ends[b_id] + sba_ticks).OnlyEnforceIf(b_before)
                    if sab_ticks: setup_terms.append((a_before, sab_ticks))
                    if sba_ticks: setup_terms.append((b_before, sba_ticks))

        tardiness_terms, priority_terms = [], []
        for op_id, op in operations.items():
            due = _aware(op.work_order.due_date, time.max)
            due_tick = min(horizon_ticks, _tick(due, origin, granularity))
            tardy = model.NewIntVar(0, horizon_ticks, f"ptardy_{op_id}")
            model.Add(tardy >= op_ends[op_id] - due_tick)
            tardiness_terms.append(tardy)
            priority = 50
            profile = op.work_order.item.scheduling_profiles.filter(plant=scenario.plant).first()
            if profile:
                priority = int(profile.commercial_priority)
            priority_terms.append((tardy, max(1, priority)))
        makespan = model.NewIntVar(0, horizon_ticks, "pmakespan")
        model.AddMaxEquality(makespan, list(op_ends.values()))
        objective = [weights["tardiness"] * t for t in tardiness_terms]
        objective += [weights["priority_tardiness"] * p * t for t, p in priority_terms]
        objective += [weights["makespan"] * makespan]
        objective += [weights["setup"] * ticks * lit for lit, ticks in setup_terms]
        objective += [weights["alternate_resource"] * 10 * lit for lit in alternate_terms]
        objective += [handoff_penalty * lit for lit in handoff_terms]
        if labor_context and run.use_labor_costs:
            objective += [weights.get("labor_cost", 1) * coeff * var for var, coeff in labor_context.get("base_cost_terms", [])]
            objective += [weights.get("labor_cost", 1) * coeff * var for var, coeff in labor_context.get("overtime_cost_terms", [])]
        model.Minimize(sum(objective))

        if warm_start:
            warm_scenario, warm_blocks = _warm_start_blocks(scenario)
            hinted = 0
            for op_id, wb in warm_blocks.items():
                if op_id not in op_starts:
                    continue
                st = min(horizon_ticks, _tick(wb.simulated_start, origin, granularity))
                model.AddHint(op_starts[op_id], st)
                hinted += 1
            run.warm_start_source = "BEST_HEURISTIC" if warm_scenario.pk != scenario.pk else "CURRENT_SCENARIO"
            run.warm_start_scenario = warm_scenario
            run.progress = {"phase": "solve", "mode": "PREEMPTIVE", "warm_start_operations": hinted, "segments": total_segments}
            run.save(update_fields=["warm_start_source", "warm_start_scenario", "progress", "updated_at"])

        solver = cp_model.CpSolver()
        solver.parameters.max_time_in_seconds = float(limit)
        solver.parameters.num_search_workers = workers
        solver.parameters.log_search_progress = False
        if gap_limit > 0:
            solver.parameters.relative_gap_limit = float(gap_limit)

        class IncumbentCallback(cp_model.CpSolverSolutionCallback):
            def __init__(self, run_id):
                super().__init__(); self.run_id = run_id; self.sequence = 0
            def on_solution_callback(self):
                self.sequence += 1
                obj = Decimal(str(self.ObjectiveValue())); bound = Decimal(str(self.BestObjectiveBound()))
                gap = abs(obj - bound) / max(abs(obj), Decimal("1"))
                ScheduleSolverIncumbent.objects.create(
                    run_id=self.run_id, sequence=self.sequence, objective_value=obj, best_bound=bound,
                    relative_gap=gap, wall_time_seconds=Decimal(str(round(self.WallTime(), 4))),
                    solution_count=self.sequence, summary={"mode": "PREEMPTIVE", "objective": str(obj), "gap": str(gap)},
                )
                ScheduleSolverRun.objects.filter(pk=self.run_id).update(
                    last_incumbent_at=timezone.now(),
                    progress={"phase": "solve", "mode": "PREEMPTIVE", "incumbents": self.sequence, "objective": str(obj), "relative_gap": str(gap)},
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
        run.conflicts = int(solver.NumConflicts()); run.branches = int(solver.NumBranches())
        try:
            run.objective_value = Decimal(str(solver.ObjectiveValue())); run.best_bound = Decimal(str(solver.BestObjectiveBound()))
        except Exception:
            pass

        total_tardy = alternate_count = handoffs = persisted_segments = 0
        assignment_by_op = {}
        segment_by_op_seq = {}
        if status_name in {"OPTIMAL", "FEASIBLE"}:
            for op_id, op in operations.items():
                selected_key = next(key for key, use in op_resource_use[op_id].items() if solver.Value(use) == 1)
                first_choice = next(c for c in chunk_alternatives[(op_id, 1)] if c["resource_key"] == selected_key and solver.Value(c["presence"]) == 1)
                segment_rows = []
                for seq, _ in enumerate(chunk_vars[op_id], start=1):
                    selected = next(c for c in chunk_alternatives[(op_id, seq)] if solver.Value(c["presence"]) == 1)
                    segment_rows.append(selected)
                start_dt = _dt(solver.Value(op_starts[op_id]), origin, granularity)
                end_dt = _dt(solver.Value(op_ends[op_id]), origin, granularity)
                due = _aware(op.work_order.due_date, time.max)
                tardy_minutes = max(0, int((end_dt - due).total_seconds() // 60)); total_tardy += tardy_minutes
                alternate_count += int(first_choice["alternate"])
                assignment = ScheduleSolverAssignment.objects.create(
                    run=run, operation=op, work_center=first_choice["center"], machine=first_choice["machine"],
                    start=start_dt, end=end_dt,
                    duration_minutes=sum(int(c["processing_minutes"]) for c in segment_rows),
                    is_alternate_resource=first_choice["alternate"], tardiness_minutes=tardy_minutes,
                    details={"preemptive": True, "segment_count": len(segment_rows), "max_consecutive_minutes": max_consecutive},
                )
                assignment_by_op[op_id] = assignment
                previous_end = None
                for seq, selected in enumerate(segment_rows, start=1):
                    ss = _dt(solver.Value(selected["start"]), origin, granularity)
                    se = _dt(solver.Value(selected["end"]), origin, granularity)
                    handoff_after = previous_end is not None and ss > previous_end
                    if handoff_after: handoffs += 1
                    solver_segment = ScheduleSolverSegment.objects.create(
                        assignment=assignment, sequence=seq, start=ss, end=se,
                        processing_minutes=int(selected["processing_minutes"]), calendar_kind=selected["kind"],
                        shift_name=_shift_name(selected["center"], ss), handoff_after=handoff_after,
                        details={"capacity_rate": selected["rate"], "elapsed_minutes": selected["elapsed_minutes"]},
                    )
                    segment_by_op_seq[(op_id, seq)] = solver_segment
                    previous_end = se; persisted_segments += 1
                if apply_to_scenario and not cancelled:
                    block = block_by_op[op_id]
                    block.work_center = first_choice["center"]; block.machine = first_choice["machine"]
                    block.simulated_start = start_dt; block.simulated_end = end_dt
                    block.assignment_reason = f"CP-SAT preemptivo {status_name}"
                    block.details = {**(block.details or {}), "solver_run_id": run.pk, "solver_status": status_name,
                                     "preemptive": True, "solver_segments": len(segment_rows)}
                    block.save(update_fields=["work_center", "machine", "simulated_start", "simulated_end", "assignment_reason", "details", "updated_at"])
                    # Mirror solver segments into the scenario's operational segment table for Gantt/reporting.
                    block.segments.all().delete()
                    from .models import IntegratedScheduleSegment
                    for sr in assignment.segments.all():
                        elapsed_hours = Decimal(str((sr.end - sr.start).total_seconds() / 3600))
                        IntegratedScheduleSegment.objects.create(
                            block=block, segment_type=(IntegratedScheduleSegment.SegmentType.OVERTIME if sr.calendar_kind == "OVERTIME" else IntegratedScheduleSegment.SegmentType.REGULAR),
                            start=sr.start, end=sr.end, effective_hours=Decimal(sr.processing_minutes) / Decimal("60"),
                            capacity_factor=(Decimal(sr.processing_minutes) / Decimal("60") / elapsed_hours if elapsed_hours > 0 else Decimal("1")),
                        )
            labor_count = 0
            if labor_context:
                from .labor import selected_labor_entries
                for info in selected_labor_entries(solver=solver, context=labor_context):
                    assignment = assignment_by_op[info["operation_id"]]
                    segment = segment_by_op_seq.get((info["operation_id"], info.get("segment_sequence")))
                    ScheduleSolverLaborAssignment.objects.create(
                        run=run, assignment=assignment, segment=segment, operation_id=info["operation_id"],
                        labor_resource=info["worker"], skill=info["requirement"].skill,
                        start=segment.start if segment else assignment.start, end=segment.end if segment else assignment.end,
                        shift_name=info.get("shift_name", ""), is_handoff=bool(segment and segment.sequence > 1),
                    )
                    labor_count += 1
            labor_cost_total = Decimal("0")
            if labor_count and run.use_labor_costs:
                from .labor_costing import calculate_run_labor_costs
                labor_cost_total = calculate_run_labor_costs(run)
            run.summary = {
                "status": "CANCELLED" if cancelled else status_name, "solver_mode": "PREEMPTIVE",
                "assignments": run.assignments.count(), "segments": persisted_segments, "handoffs": handoffs,
                "max_consecutive_minutes": max_consecutive, "handoff_penalty": handoff_penalty,
                "total_tardiness_minutes": total_tardy, "alternate_resource_assignments": alternate_count,
                "objective_value": str(run.objective_value), "best_bound": str(run.best_bound),
                "wall_time_seconds": str(run.wall_time_seconds), "granularity_minutes": granularity,
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
            run.summary = {"status": status_name, "solver_mode": "PREEMPTIVE", "assignments": 0,
                           "message": "Nenhuma solução preemptiva factível encontrada dentro dos limites."}

        run.finished_at = timezone.now(); run.progress = {**(run.progress or {}), "phase": "finished", "status": run.status}
        run.save(update_fields=["status", "objective_value", "best_bound", "wall_time_seconds", "conflicts", "branches", "summary", "finished_at", "progress", "updated_at"])
        append_domain_event(
            event_type="CP_SAT_PREEMPTIVE_SCHEDULE_SOLVED", aggregate_type="ScheduleSolverRun", aggregate_id=str(run.pk), actor=actor,
            payload=run.summary, idempotency_key=f"cp-sat-preemptive:{run.pk}",
        )
        return run
    except Exception as exc:
        run.status = ScheduleSolverRun.Status.FAILED; run.error_message = str(exc); run.finished_at = timezone.now()
        run.progress = {**(run.progress or {}), "phase": "failed", "error": str(exc)}
        run.save(update_fields=["status", "error_message", "finished_at", "progress", "updated_at"])
        raise
