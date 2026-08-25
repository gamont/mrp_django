from __future__ import annotations

from collections import defaultdict
from datetime import datetime, time, timedelta
from decimal import Decimal

from django.core.exceptions import ValidationError
from django.db import transaction
from django.utils import timezone

from apps.common.services import append_domain_event
from apps.maintenance.models import MaintenanceWorkOrder
from apps.masterdata.models import WorkCenter, WorkCenterShift
from apps.production.models import WorkOrder, WorkOrderOperation

from .models import IntegratedScheduleBlock, IntegratedScheduleConflict, IntegratedScheduleScenario, PublishedOperationSchedule

ZERO = Decimal("0")


def hours_between(start, end):
    return max(ZERO, Decimal(str((end - start).total_seconds() / 3600)).quantize(Decimal("0.0001")))


def overlap_hours(a_start, a_end, b_start, b_end):
    start = max(a_start, b_start)
    end = min(a_end, b_end)
    return hours_between(start, end) if end > start else ZERO


def _aware_day(day, at=time.min):
    value = datetime.combine(day, at)
    return timezone.make_aware(value) if timezone.is_naive(value) else value


def _production_window(operation):
    start = operation.planned_start or _aware_day(operation.work_order.release_date, time(hour=8))
    if operation.planned_end:
        end = operation.planned_end
    else:
        duration = Decimal(operation.setup_hours or 0) + Decimal(operation.run_hours or 0)
        if duration <= 0:
            duration = Decimal("1")
        end = start + timedelta(hours=float(duration))
    return start, end


def _capacity_per_day(work_center, day):
    shifts = WorkCenterShift.objects.filter(work_center=work_center, weekday=day.weekday(), is_active=True)
    if shifts.exists():
        return sum((s.capacity_hours * s.efficiency_percent / Decimal("100") for s in shifts), ZERO)
    return work_center.capacity_hours_per_day * work_center.efficiency_percent / Decimal("100")


def _summary(blocks, conflicts):
    prod = [b for b in blocks if b.block_type == IntegratedScheduleBlock.BlockType.PRODUCTION]
    maint = [b for b in blocks if b.block_type == IntegratedScheduleBlock.BlockType.MAINTENANCE]
    return {
        "production_blocks": len(prod),
        "maintenance_blocks": len(maint),
        "production_hours": str(sum((b.required_hours for b in prod), ZERO)),
        "maintenance_hours": str(sum((b.required_hours for b in maint), ZERO)),
        "lost_capacity_hours": str(sum((b.lost_capacity_hours for b in maint), ZERO)),
        "late_hours": str(sum((b.late_hours for b in prod), ZERO)),
        "conflicts": len(conflicts),
        "critical_conflicts": sum(1 for c in conflicts if c.severity == IntegratedScheduleConflict.Severity.CRITICAL),
        "affected_work_orders": len({b.details.get("work_order_id") for b in prod if b.late_hours > 0}),
        "shifted_operations": sum(1 for b in prod if b.simulated_start != b.original_start or b.simulated_end != b.original_end),
        "max_late_hours": str(max((b.late_hours for b in prod), default=ZERO)),
        "mrp_supply_dates_shifted": len({b.details.get("work_order_id") for b in prod if b.simulated_end != b.original_end}),
    }


@transaction.atomic
def run_integrated_scenario(*, scenario: IntegratedScheduleScenario, actor=None):
    scenario = IntegratedScheduleScenario.objects.select_for_update().get(pk=scenario.pk)
    scenario.status = IntegratedScheduleScenario.Status.RUNNING
    scenario.error_message = ""
    scenario.save(update_fields=["status", "error_message", "updated_at"])
    scenario.blocks.all().delete()
    scenario.conflicts.all().delete()
    horizon_start = _aware_day(scenario.horizon_start)
    horizon_end = _aware_day(scenario.horizon_end + timedelta(days=1))
    blocks = []

    operations = WorkOrderOperation.objects.select_related("work_order", "work_order__item", "work_center").filter(
        work_order__plant=scenario.plant,
        work_order__status__in=[WorkOrder.Status.PLANNED, WorkOrder.Status.RELEASED, WorkOrder.Status.IN_PROGRESS],
    )
    if not scenario.include_planned_production:
        operations = operations.exclude(work_order__status=WorkOrder.Status.PLANNED)
    for op in operations:
        start, end = _production_window(op)
        if end <= horizon_start or start >= horizon_end:
            continue
        blocks.append(IntegratedScheduleBlock.objects.create(
            scenario=scenario,
            block_type=IntegratedScheduleBlock.BlockType.PRODUCTION,
            work_center=op.work_center,
            source_type="WORK_ORDER_OPERATION",
            source_id=str(op.pk),
            source_number=op.work_order.number,
            description=f"{op.sequence:03d} · {op.description}",
            original_start=start,
            original_end=end,
            simulated_start=start,
            simulated_end=end,
            required_hours=hours_between(start, end),
            details={"work_order_id": op.work_order_id, "item": op.work_order.item.code, "due_date": op.work_order.due_date.isoformat(), "planned_order_id": op.work_order.planned_order_id},
        ))

    if scenario.include_maintenance:
        maintenance = MaintenanceWorkOrder.objects.select_related("asset", "asset__machine", "asset__machine__work_center").filter(
            plant=scenario.plant,
            status__in=[MaintenanceWorkOrder.Status.PLANNED, MaintenanceWorkOrder.Status.RELEASED, MaintenanceWorkOrder.Status.IN_PROGRESS],
            scheduled_start__isnull=False,
            scheduled_end__isnull=False,
            scheduled_end__gt=horizon_start,
            scheduled_start__lt=horizon_end,
        )
        for wo in maintenance:
            machine = wo.asset.machine
            center = machine.work_center if machine else None
            if not center:
                continue
            duration = hours_between(wo.scheduled_start, wo.scheduled_end)
            blocks.append(IntegratedScheduleBlock.objects.create(
                scenario=scenario,
                block_type=IntegratedScheduleBlock.BlockType.MAINTENANCE,
                work_center=center,
                machine=machine,
                source_type="MAINTENANCE_WORK_ORDER",
                source_id=str(wo.pk),
                source_number=wo.number,
                description=wo.title,
                original_start=wo.scheduled_start,
                original_end=wo.scheduled_end,
                simulated_start=wo.scheduled_start,
                simulated_end=wo.scheduled_end,
                required_hours=duration,
                lost_capacity_hours=duration,
                details={"priority": wo.priority, "order_type": wo.order_type, "asset": wo.asset.code},
            ))

    prod = [b for b in blocks if b.block_type == IntegratedScheduleBlock.BlockType.PRODUCTION]
    maint = [b for b in blocks if b.block_type == IntegratedScheduleBlock.BlockType.MAINTENANCE]
    baseline_conflicts = []
    for p in prod:
        for m in maint:
            if p.work_center_id != m.work_center_id:
                continue
            overlap = overlap_hours(p.original_start, p.original_end, m.original_start, m.original_end)
            if overlap <= 0:
                continue
            severity = IntegratedScheduleConflict.Severity.CRITICAL if m.details.get("priority") == MaintenanceWorkOrder.Priority.EMERGENCY else IntegratedScheduleConflict.Severity.WARNING
            baseline_conflicts.append(IntegratedScheduleConflict.objects.create(
                scenario=scenario,
                conflict_type=IntegratedScheduleConflict.ConflictType.MAINTENANCE_PRODUCTION,
                severity=severity,
                work_center=p.work_center,
                production_block=p,
                maintenance_block=m,
                overlap_hours=overlap,
                message=f"{m.source_number} sobrepõe {p.source_number} em {overlap} h no centro {p.work_center.code}.",
            ))

    scenario.baseline_summary = _summary(blocks, baseline_conflicts)

    # Simulação conservadora: toda sobreposição de manutenção desloca a operação e as operações posteriores
    # do mesmo centro. Não altera dados de produção até o cenário ser aplicado.
    by_center = defaultdict(list)
    for p in prod:
        by_center[p.work_center_id].append(p)
    for center_id, center_blocks in by_center.items():
        center_blocks.sort(key=lambda b: (b.simulated_start, b.pk))
        maintenance_blocks = sorted([m for m in maint if m.work_center_id == center_id], key=lambda b: b.simulated_start)
        cursor = None
        for p in center_blocks:
            start = p.original_start
            end = p.original_end
            duration = end - start
            if cursor and start < cursor:
                start = cursor
                end = start + duration
            changed = True
            while changed:
                changed = False
                for m in maintenance_blocks:
                    if overlap_hours(start, end, m.simulated_start, m.simulated_end) > 0:
                        start = max(start, m.simulated_end)
                        end = start + duration
                        changed = True
            p.simulated_start = start
            p.simulated_end = end
            due_date = datetime.fromisoformat(p.details["due_date"]).date()
            due_end = _aware_day(due_date, time.max)
            p.late_hours = hours_between(due_end, end) if end > due_end else ZERO
            p.save(update_fields=["simulated_start", "simulated_end", "late_hours", "updated_at"])
            cursor = end

    conflicts = list(baseline_conflicts)
    for p in prod:
        if p.late_hours > 0:
            conflicts.append(IntegratedScheduleConflict.objects.create(
                scenario=scenario,
                conflict_type=IntegratedScheduleConflict.ConflictType.DUE_DATE,
                severity=IntegratedScheduleConflict.Severity.CRITICAL,
                work_center=p.work_center,
                production_block=p,
                overlap_hours=ZERO,
                message=f"{p.source_number} projeta atraso de {p.late_hours} h após incluir manutenção.",
                details={"simulated_end": p.simulated_end.isoformat()},
            ))

    # Checagem diária agregada: carga produtiva simulada + manutenção contra capacidade nominal.
    day = scenario.horizon_start
    while day <= scenario.horizon_end:
        for center in WorkCenter.objects.filter(plant=scenario.plant):
            day_start, day_end = _aware_day(day), _aware_day(day + timedelta(days=1))
            prod_hours = sum((overlap_hours(b.simulated_start, b.simulated_end, day_start, day_end) for b in prod if b.work_center_id == center.id), ZERO)
            maint_hours = sum((overlap_hours(b.simulated_start, b.simulated_end, day_start, day_end) for b in maint if b.work_center_id == center.id), ZERO)
            capacity = _capacity_per_day(center, day)
            available_after_maintenance = max(ZERO, capacity - maint_hours)
            if prod_hours > available_after_maintenance:
                overload = prod_hours - available_after_maintenance
                conflicts.append(IntegratedScheduleConflict.objects.create(
                    scenario=scenario,
                    conflict_type=IntegratedScheduleConflict.ConflictType.CAPACITY_OVERLOAD,
                    severity=IntegratedScheduleConflict.Severity.CRITICAL if overload >= Decimal("4") else IntegratedScheduleConflict.Severity.WARNING,
                    work_center=center,
                    overlap_hours=overload,
                    message=f"Sobrecarga de {overload} h em {center.code} em {day:%d/%m/%Y} após manutenção.",
                    details={"capacity_hours": str(capacity), "maintenance_hours": str(maint_hours), "production_hours": str(prod_hours), "available_after_maintenance": str(available_after_maintenance)},
                ))
        day += timedelta(days=1)

    scenario.simulated_summary = _summary(blocks, conflicts)
    scenario.status = IntegratedScheduleScenario.Status.COMPLETED
    scenario.save(update_fields=["baseline_summary", "simulated_summary", "status", "updated_at"])
    append_domain_event(event_type="INTEGRATED_SCHEDULE_SIMULATED", aggregate_type="IntegratedScheduleScenario", aggregate_id=str(scenario.pk), actor=actor, payload=scenario.simulated_summary, idempotency_key=f"integrated-sim:{scenario.pk}:{scenario.updated_at.isoformat()}")
    return scenario


@transaction.atomic
def apply_integrated_scenario(*, scenario: IntegratedScheduleScenario, actor=None):
    scenario = IntegratedScheduleScenario.objects.select_for_update().get(pk=scenario.pk)
    if scenario.status != IntegratedScheduleScenario.Status.COMPLETED:
        raise ValidationError("Somente cenários concluídos podem ser aplicados.")
    if scenario.conflicts.filter(severity=IntegratedScheduleConflict.Severity.CRITICAL).exists() and not scenario.parameters.get("allow_critical_conflicts"):
        raise ValidationError("O cenário possui conflitos críticos. Resolva-os ou habilite allow_critical_conflicts.")
    # Aplica somente datas de operações produtivas. O agendamento de manutenção já é a entrada do cenário.
    for block in scenario.blocks.filter(block_type=IntegratedScheduleBlock.BlockType.PRODUCTION, source_type="WORK_ORDER_OPERATION"):
        operation = WorkOrderOperation.objects.get(pk=int(block.source_id))
        operation.work_center = block.work_center
        operation.planned_start = block.simulated_start
        operation.planned_end = block.simulated_end
        operation.save(update_fields=["work_center", "planned_start", "planned_end", "updated_at"])
        PublishedOperationSchedule.objects.update_or_create(
            operation=operation,
            defaults={
                "scenario": scenario, "work_center": block.work_center, "machine": block.machine,
                "planned_start": block.simulated_start, "planned_end": block.simulated_end,
                "published_by": actor,
            },
        )
    scenario.status = IntegratedScheduleScenario.Status.APPLIED
    scenario.applied_by = actor
    scenario.applied_at = timezone.now()
    scenario.save(update_fields=["status", "applied_by", "applied_at", "updated_at"])
    append_domain_event(event_type="INTEGRATED_SCHEDULE_APPLIED", aggregate_type="IntegratedScheduleScenario", aggregate_id=str(scenario.pk), actor=actor, payload={"blocks": scenario.blocks.count(), "published_operations": scenario.published_operations.count()}, idempotency_key=f"integrated-apply:{scenario.pk}")
    return scenario
