from __future__ import annotations

from collections import defaultdict
from datetime import datetime, timedelta
from decimal import Decimal

from django.core.exceptions import ValidationError
from django.db import transaction
from django.utils import timezone

from apps.common.services import append_domain_event
from apps.masterdata.models import RoutingOperation
from apps.production.models import WorkOrderOperation
from apps.shopfloor.models import Machine

from .models import IntegratedScheduleBlock, IntegratedScheduleConflict, IntegratedScheduleScenario
from .services import ZERO, _aware_day, _capacity_per_day, hours_between, overlap_hours, run_integrated_scenario
from .sequencing import sequence_blocks, family_for_block, setup_hours, adjacent_family


def _candidate_resources(block, scenario):
    """Return candidate (work_center, machine, label) tuples ordered by preference."""
    operation = WorkOrderOperation.objects.select_related("work_order__routing", "work_center").get(pk=int(block.source_id))
    centers = [operation.work_center]
    if scenario.allow_alternate_resources and operation.work_order.routing_id:
        routing_op = RoutingOperation.objects.filter(
            routing_id=operation.work_order.routing_id, sequence=operation.sequence
        ).select_related("alternate_work_center").first()
        if routing_op and routing_op.alternate_work_center_id and routing_op.alternate_work_center_id != operation.work_center_id:
            centers.append(routing_op.alternate_work_center)

    resources = []
    for idx, center in enumerate(centers):
        machines = list(Machine.objects.filter(plant=scenario.plant, work_center=center, is_active=True).order_by("code"))
        if scenario.finite_by_machine and machines:
            resources.extend((center, machine, "principal" if idx == 0 else "alternativo") for machine in machines)
        else:
            resources.append((center, None, "principal" if idx == 0 else "alternativo"))
    return resources


def _busy_intervals(scenario, *, center_id, machine_id, exclude_block_id=None):
    qs = scenario.blocks.exclude(pk=exclude_block_id).filter(work_center_id=center_id)
    if machine_id:
        # Machine-specific maintenance/production consumes that machine. Center-wide maintenance with machine NULL blocks all machines.
        qs = qs.filter(machine_id__in=[machine_id, None])
    return sorted([(b.simulated_start, b.simulated_end) for b in qs], key=lambda x: x[0])


def _slot_forward(start, duration, intervals):
    candidate = start
    for busy_start, busy_end in intervals:
        if candidate + duration <= busy_start:
            break
        if overlap_hours(candidate, candidate + duration, busy_start, busy_end) > 0:
            candidate = busy_end
    return candidate, candidate + duration


def _slot_backward(end, duration, intervals):
    candidate_end = end
    for busy_start, busy_end in sorted(intervals, key=lambda x: x[1], reverse=True):
        start = candidate_end - duration
        if start >= busy_end:
            break
        if overlap_hours(start, candidate_end, busy_start, busy_end) > 0:
            candidate_end = busy_start
    return candidate_end - duration, candidate_end


def _score_assignment(block, center, machine, start, end):
    lateness = Decimal("0")
    due = block.details.get("due_date")
    if due:
        due_dt = timezone.make_aware(datetime.fromisoformat(due + "T23:59:59"))
        if end > due_dt:
            lateness = hours_between(due_dt, end)
    move = abs(Decimal(str((start - block.original_start).total_seconds() / 3600)))
    alternate_penalty = Decimal("0") if center.id == block.work_center_id else Decimal("0.25")
    return lateness * Decimal("1000") + move + alternate_penalty


def _rebuild_dynamic_conflicts(scenario):
    scenario.conflicts.all().delete()
    prod = list(scenario.blocks.filter(block_type=IntegratedScheduleBlock.BlockType.PRODUCTION).select_related("work_center", "machine"))
    maint = list(scenario.blocks.filter(block_type=IntegratedScheduleBlock.BlockType.MAINTENANCE).select_related("work_center", "machine"))

    # Production × maintenance after finite assignment. Machine-specific maintenance blocks only its machine;
    # center-wide maintenance (machine NULL) blocks the whole center.
    for p in prod:
        for m in maint:
            if p.work_center_id != m.work_center_id:
                continue
            if m.machine_id and p.machine_id and m.machine_id != p.machine_id:
                continue
            p_segments = list(p.segments.all())
            overlap = sum((overlap_hours(seg.start, seg.end, m.simulated_start, m.simulated_end) for seg in p_segments), ZERO) if p_segments else overlap_hours(p.simulated_start, p.simulated_end, m.simulated_start, m.simulated_end)
            if overlap:
                IntegratedScheduleConflict.objects.create(
                    scenario=scenario, conflict_type=IntegratedScheduleConflict.ConflictType.MAINTENANCE_PRODUCTION,
                    severity=IntegratedScheduleConflict.Severity.CRITICAL, work_center=p.work_center,
                    production_block=p, maintenance_block=m, overlap_hours=overlap,
                    message=f"{m.source_number} ainda sobrepõe {p.source_number} em {overlap} h.",
                )

    for i, a in enumerate(prod):
        for b in prod[i + 1:]:
            same_resource = a.machine_id and a.machine_id == b.machine_id
            same_center_fallback = not a.machine_id and not b.machine_id and a.work_center_id == b.work_center_id
            if not (same_resource or same_center_fallback):
                continue
            a_segments, b_segments = list(a.segments.all()), list(b.segments.all())
            if a_segments and b_segments:
                overlap = sum((overlap_hours(sa.start, sa.end, sb.start, sb.end) for sa in a_segments for sb in b_segments), ZERO)
            else:
                overlap = overlap_hours(a.simulated_start, a.simulated_end, b.simulated_start, b.simulated_end)
            if overlap:
                IntegratedScheduleConflict.objects.create(
                    scenario=scenario, conflict_type=IntegratedScheduleConflict.ConflictType.MACHINE_OVERLAP,
                    severity=IntegratedScheduleConflict.Severity.CRITICAL, work_center=a.work_center,
                    production_block=a, overlap_hours=overlap,
                    message=f"Conflito finito entre {a.source_number} e {b.source_number}: {overlap} h no mesmo recurso.",
                    details={"other_block_id": b.pk, "machine_id": a.machine_id},
                )
        due = a.details.get("due_date")
        if due:
            due_dt = timezone.make_aware(datetime.fromisoformat(due + "T23:59:59"))
            a.late_hours = hours_between(due_dt, a.simulated_end) if a.simulated_end > due_dt else ZERO
            a.save(update_fields=["late_hours", "updated_at"])
            if a.late_hours:
                IntegratedScheduleConflict.objects.create(
                    scenario=scenario, conflict_type=IntegratedScheduleConflict.ConflictType.DUE_DATE,
                    severity=IntegratedScheduleConflict.Severity.CRITICAL, work_center=a.work_center,
                    production_block=a, overlap_hours=ZERO,
                    message=f"{a.source_number} projeta atraso de {a.late_hours} h.",
                )

    # Aggregate center capacity remains a useful guard even when machines are scheduled finitely.
    day = scenario.horizon_start
    while day <= scenario.horizon_end:
        day_start, day_end = _aware_day(day), _aware_day(day + timedelta(days=1))
        center_ids = {b.work_center_id for b in prod + maint}
        for center_id in center_ids:
            center = next((b.work_center for b in prod + maint if b.work_center_id == center_id), None)
            if not center:
                continue
            prod_hours = ZERO
            for b in prod:
                if b.work_center_id != center_id:
                    continue
                b_segments = list(b.segments.all())
                if b_segments:
                    prod_hours += sum((overlap_hours(seg.start, seg.end, day_start, day_end) for seg in b_segments), ZERO)
                else:
                    prod_hours += overlap_hours(b.simulated_start, b.simulated_end, day_start, day_end)
            maint_hours = sum((overlap_hours(b.simulated_start, b.simulated_end, day_start, day_end) for b in maint if b.work_center_id == center_id), ZERO)
            capacity = _capacity_per_day(center, day)
            available = max(ZERO, capacity - maint_hours)
            if prod_hours > available:
                overload = prod_hours - available
                IntegratedScheduleConflict.objects.create(
                    scenario=scenario, conflict_type=IntegratedScheduleConflict.ConflictType.CAPACITY_OVERLOAD,
                    severity=IntegratedScheduleConflict.Severity.CRITICAL if overload >= Decimal("4") else IntegratedScheduleConflict.Severity.WARNING,
                    work_center=center, overlap_hours=overload,
                    message=f"Sobrecarga agregada de {overload} h em {center.code} em {day:%d/%m/%Y}.",
                    details={"capacity_hours": str(capacity), "maintenance_hours": str(maint_hours), "production_hours": str(prod_hours)},
                )
        day += timedelta(days=1)


def _refresh_summary(scenario):
    blocks = list(scenario.blocks.all())
    conflicts = list(scenario.conflicts.all())
    prod = [b for b in blocks if b.block_type == IntegratedScheduleBlock.BlockType.PRODUCTION]
    maint = [b for b in blocks if b.block_type == IntegratedScheduleBlock.BlockType.MAINTENANCE]
    scenario.simulated_summary = {
        **scenario.simulated_summary,
        "production_blocks": len(prod),
        "maintenance_blocks": len(maint),
        "conflicts": len(conflicts),
        "critical_conflicts": sum(c.severity == IntegratedScheduleConflict.Severity.CRITICAL for c in conflicts),
        "shifted_operations": sum(b.simulated_start != b.original_start or b.simulated_end != b.original_end for b in prod),
        "machine_assigned_operations": sum(bool(b.machine_id) for b in prod),
        "alternate_resource_operations": sum(bool(b.details.get("alternate_resource")) for b in prod),
        "manual_blocks": sum(b.manually_locked for b in prod),
        "late_hours": str(sum((b.late_hours for b in prod), ZERO)),
        "max_late_hours": str(max((b.late_hours for b in prod), default=ZERO)),
    }
    scenario.save(update_fields=["simulated_summary", "updated_at"])


@transaction.atomic
def run_finite_scenario(*, scenario: IntegratedScheduleScenario, actor=None):
    """Build baseline and schedule finitely; 0.6.2 delegates to the industrial calendar engine by default."""
    if scenario.respect_industrial_calendar:
        from .calendar_aware import run_calendar_aware_scenario
        return run_calendar_aware_scenario(scenario=scenario, actor=actor)
    scenario = run_integrated_scenario(scenario=scenario, actor=actor)
    scenario = IntegratedScheduleScenario.objects.select_for_update().get(pk=scenario.pk)
    prod = list(scenario.blocks.filter(block_type=IntegratedScheduleBlock.BlockType.PRODUCTION).select_related("work_center"))

    reverse = scenario.scheduling_direction == "BACKWARD"
    prod = sequence_blocks(prod, scenario)
    assigned = []

    for block in prod:
        if block.manually_locked:
            assigned.append(block)
            continue
        candidates = []
        block_family = family_for_block(block, scenario)
        for center, machine, label in _candidate_resources(block, scenario):
            neighbour_family = adjacent_family(assigned, center=center, machine=machine, direction=scenario.scheduling_direction)
            if reverse:
                transition = setup_hours(scenario=scenario, center=center, machine=machine, from_family=block_family, to_family=neighbour_family) if neighbour_family else Decimal("0")
            else:
                transition = setup_hours(scenario=scenario, center=center, machine=machine, from_family=neighbour_family, to_family=block_family)
            duration = (block.original_end - block.original_start) + timedelta(hours=float(transition))
            # Busy = maintenance + production already assigned to this resource only.
            intervals = []
            for m in scenario.blocks.filter(block_type=IntegratedScheduleBlock.BlockType.MAINTENANCE, work_center=center):
                if m.machine_id is None or machine is None or m.machine_id == machine.id:
                    intervals.append((m.simulated_start, m.simulated_end))
            for used in assigned:
                if machine and used.machine_id == machine.id:
                    intervals.append((used.simulated_start, used.simulated_end))
                elif machine is None and used.machine_id is None and used.work_center_id == center.id:
                    intervals.append((used.simulated_start, used.simulated_end))
            if reverse:
                start, end = _slot_backward(block.original_end, duration, intervals)
            else:
                start, end = _slot_forward(block.original_start, duration, intervals)
            score = _score_assignment(block, center, machine, start, end) + (transition * Decimal("10") if scenario.minimize_setups else Decimal("0"))
            candidates.append((score, center, machine, label, start, end, transition, block_family, neighbour_family))
        if not candidates:
            continue
        _, center, machine, label, start, end, transition, block_family, neighbour_family = min(candidates, key=lambda x: x[0])
        old_center_id = block.work_center_id
        details = dict(block.details)
        details.update({
            "alternate_resource": center.id != old_center_id,
            "resource_label": label,
            "scheduled_machine_code": machine.code if machine else None,
            "product_family": block_family.code if block_family else None,
            "previous_family": neighbour_family.code if neighbour_family else None,
            "sequence_setup_hours": str(transition),
            "dispatch_rule": scenario.dispatch_rule,
        })
        block.work_center = center
        block.machine = machine
        block.simulated_start = start
        block.simulated_end = end
        block.sequence_setup_hours = transition
        block.sequence_position = len(assigned) + 1
        block.assignment_reason = f"Finite {scenario.scheduling_direction.lower()} · {label} · {machine.code if machine else center.code}"
        block.details = details
        block.save(update_fields=["work_center", "machine", "simulated_start", "simulated_end", "sequence_setup_hours", "sequence_position", "assignment_reason", "details", "updated_at"])
        assigned.append(block)

    _rebuild_dynamic_conflicts(scenario)
    _refresh_summary(scenario)
    append_domain_event(
        event_type="FINITE_SCHEDULE_SIMULATED",
        aggregate_type="IntegratedScheduleScenario",
        aggregate_id=str(scenario.pk), actor=actor,
        payload={"direction": scenario.scheduling_direction, **scenario.simulated_summary},
        idempotency_key=f"finite-sim:{scenario.pk}:{scenario.updated_at.isoformat()}",
    )
    return scenario


@transaction.atomic
def move_schedule_block(*, block: IntegratedScheduleBlock, start, end, machine=None, actor=None, lock=True):
    block = IntegratedScheduleBlock.objects.select_for_update().select_related("scenario", "work_center").get(pk=block.pk)
    if block.block_type != IntegratedScheduleBlock.BlockType.PRODUCTION:
        raise ValidationError("Somente blocos produtivos podem ser movidos manualmente nesta versão.")
    if end <= start:
        raise ValidationError("Fim deve ser posterior ao início.")
    if machine:
        if machine.plant_id != block.scenario.plant_id:
            raise ValidationError("Máquina não pertence à planta do cenário.")
        block.machine = machine
        block.work_center = machine.work_center
    block.simulated_start = start
    block.simulated_end = end
    block.manually_locked = lock
    block.assignment_reason = "Ajuste manual pelo Gantt"
    block.save(update_fields=["machine", "work_center", "simulated_start", "simulated_end", "manually_locked", "assignment_reason", "updated_at"])
    _rebuild_dynamic_conflicts(block.scenario)
    _refresh_summary(block.scenario)
    append_domain_event(event_type="INTEGRATED_SCHEDULE_BLOCK_MOVED", aggregate_type="IntegratedScheduleBlock", aggregate_id=str(block.pk), actor=actor, payload={"start": start.isoformat(), "end": end.isoformat(), "machine_id": block.machine_id}, idempotency_key=f"intsched-move:{block.pk}:{block.updated_at.isoformat()}")
    return block


def compare_scenarios(scenarios):
    rows = []
    for s in scenarios:
        m = s.simulated_summary or {}
        rows.append({
            "id": s.pk, "name": s.name, "direction": s.scheduling_direction,
            "conflicts": int(m.get("conflicts", 0) or 0),
            "critical_conflicts": int(m.get("critical_conflicts", 0) or 0),
            "shifted_operations": int(m.get("shifted_operations", 0) or 0),
            "alternate_resource_operations": int(m.get("alternate_resource_operations", 0) or 0),
            "late_hours": Decimal(str(m.get("late_hours", "0") or "0")),
            "max_late_hours": Decimal(str(m.get("max_late_hours", "0") or "0")),
        })
    return sorted(rows, key=lambda r: (r["critical_conflicts"], r["late_hours"], r["conflicts"], r["shifted_operations"]))
