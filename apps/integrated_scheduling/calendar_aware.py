from __future__ import annotations

from decimal import Decimal
from django.core.exceptions import ValidationError
from django.db import transaction

from apps.common.services import append_domain_event
from .advanced import _candidate_resources, _rebuild_dynamic_conflicts, _refresh_summary
from .calendar_engine import resource_windows, schedule_backward, schedule_forward
from .models import IntegratedScheduleBlock, IntegratedScheduleConflict, IntegratedScheduleScenario, IntegratedScheduleSegment
from .services import run_integrated_scenario
from .sequencing import sequence_blocks, family_for_block, setup_hours, adjacent_family


def _required_hours(block):
    if block.required_hours and block.required_hours > 0:
        return Decimal(block.required_hours)
    return Decimal(str((block.original_end - block.original_start).total_seconds() / 3600))


def _busy_segments(scenario, center, machine, assigned):
    intervals = []
    for m in scenario.blocks.filter(block_type=IntegratedScheduleBlock.BlockType.MAINTENANCE, work_center=center):
        if m.machine_id is None or machine is None or m.machine_id == machine.id:
            intervals.append((m.simulated_start, m.simulated_end))
    for used in assigned:
        if machine and used.machine_id != machine.id:
            continue
        if machine is None and (used.machine_id is not None or used.work_center_id != center.id):
            continue
        segs = list(used.segments.all())
        if segs:
            intervals.extend((s.start, s.end) for s in segs)
        else:
            intervals.append((used.simulated_start, used.simulated_end))
    return intervals


def _score(block, center, segments):
    if not segments:
        return Decimal("999999999")
    start, end = segments[0][0], segments[-1][1]
    move = abs(Decimal(str((start - block.original_start).total_seconds() / 3600)))
    alternate = Decimal("0.25") if center.id != block.work_center_id else Decimal("0")
    return move + alternate


@transaction.atomic
def run_calendar_aware_scenario(*, scenario: IntegratedScheduleScenario, actor=None):
    """Programação finita respeitando turnos, pausas, feriados, hora extra e capacidade variável."""
    scenario = run_integrated_scenario(scenario=scenario, actor=actor)
    scenario = IntegratedScheduleScenario.objects.select_for_update().get(pk=scenario.pk)
    IntegratedScheduleSegment.objects.filter(block__scenario=scenario).delete()
    prod = list(scenario.blocks.filter(block_type=IntegratedScheduleBlock.BlockType.PRODUCTION).select_related("work_center"))
    reverse = scenario.scheduling_direction == "BACKWARD"
    prod = sequence_blocks(prod, scenario)
    assigned = []
    unscheduled = 0

    for block in prod:
        if block.manually_locked:
            # manual remains a continuous override; still expose one segment for reporting.
            IntegratedScheduleSegment.objects.create(block=block, start=block.simulated_start, end=block.simulated_end, effective_hours=_required_hours(block), capacity_factor=1)
            assigned.append(block)
            continue
        candidates = []
        block_family = family_for_block(block, scenario)
        for center, machine, label in _candidate_resources(block, scenario):
            windows = resource_windows(scenario=scenario, work_center=center, machine=machine)
            busy = _busy_segments(scenario, center, machine, assigned)
            neighbour_family = adjacent_family(assigned, center=center, machine=machine, direction=scenario.scheduling_direction)
            if reverse:
                transition = setup_hours(scenario=scenario, center=center, machine=machine, from_family=block_family, to_family=neighbour_family) if neighbour_family else Decimal("0")
            else:
                transition = setup_hours(scenario=scenario, center=center, machine=machine, from_family=neighbour_family, to_family=block_family)
            total_required = _required_hours(block) + transition
            kwargs = dict(windows=windows, busy_intervals=busy, required_hours=total_required)
            segments = schedule_backward(latest=block.original_end, **kwargs) if reverse else schedule_forward(earliest=block.original_start, **kwargs)
            if segments:
                score = _score(block, center, segments) + (transition * Decimal("10") if scenario.minimize_setups else Decimal("0"))
                candidates.append((score, center, machine, label, segments, transition, block_family, neighbour_family))
        if not candidates:
            unscheduled += 1
            details = dict(block.details)
            details["calendar_unscheduled"] = True
            block.details = details
            block.assignment_reason = "Sem janela de calendário/capacidade suficiente no horizonte"
            block.save(update_fields=["details", "assignment_reason", "updated_at"])
            IntegratedScheduleConflict.objects.create(
                scenario=scenario, conflict_type=IntegratedScheduleConflict.ConflictType.CAPACITY_OVERLOAD,
                severity=IntegratedScheduleConflict.Severity.CRITICAL, work_center=block.work_center,
                production_block=block, overlap_hours=_required_hours(block),
                message=f"{block.source_number} não encontrou janela útil suficiente no calendário industrial do horizonte.",
                details={"calendar_unscheduled": True, "required_hours": str(_required_hours(block))},
            )
            continue
        _, center, machine, label, segments, transition, block_family, neighbour_family = min(candidates, key=lambda x: x[0])
        old_center_id = block.work_center_id
        details = dict(block.details)
        details.update({
            "alternate_resource": center.id != old_center_id,
            "resource_label": label,
            "scheduled_machine_code": machine.code if machine else None,
            "calendar_aware": True,
            "segment_count": len(segments),
            "overtime_hours": str(sum((seg[2] for seg in segments if seg[4] == "OVERTIME"), Decimal("0"))),
            "product_family": block_family.code if block_family else None,
            "previous_family": neighbour_family.code if neighbour_family else None,
            "sequence_setup_hours": str(transition),
            "dispatch_rule": scenario.dispatch_rule,
        })
        block.work_center, block.machine = center, machine
        block.simulated_start, block.simulated_end = segments[0][0], segments[-1][1]
        block.sequence_setup_hours = transition
        block.sequence_position = len(assigned) + 1
        block.assignment_reason = f"Calendar finite {scenario.scheduling_direction.lower()} · {label} · {machine.code if machine else center.code}"
        block.details = details
        block.save(update_fields=["work_center", "machine", "simulated_start", "simulated_end", "sequence_setup_hours", "sequence_position", "assignment_reason", "details", "updated_at"])
        for start, end, eff, rate, kind in segments:
            IntegratedScheduleSegment.objects.create(block=block, segment_type=kind, start=start, end=end, effective_hours=eff, capacity_factor=rate)
        assigned.append(block)

    _rebuild_dynamic_conflicts(scenario)
    # calendar-specific summary
    _refresh_summary(scenario)
    segs = IntegratedScheduleSegment.objects.filter(block__scenario=scenario)
    scenario.simulated_summary = {
        **scenario.simulated_summary,
        "calendar_aware": True,
        "segments": segs.count(),
        "overtime_effective_hours": str(sum((s.effective_hours for s in segs.filter(segment_type="OVERTIME")), Decimal("0"))),
        "unscheduled_operations": unscheduled,
        "dispatch_rule": scenario.dispatch_rule,
        "sequence_setup_hours": str(sum((b.sequence_setup_hours for b in prod), Decimal("0"))),
        "campaign_mode": scenario.campaign_mode,
    }
    scenario.save(update_fields=["simulated_summary", "updated_at"])
    append_domain_event(
        event_type="CALENDAR_AWARE_SCHEDULE_SIMULATED", aggregate_type="IntegratedScheduleScenario",
        aggregate_id=str(scenario.pk), actor=actor, payload=scenario.simulated_summary,
        idempotency_key=f"calendar-sim:{scenario.pk}:{scenario.updated_at.isoformat()}",
    )
    return scenario
