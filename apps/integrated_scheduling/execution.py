from datetime import timedelta
from decimal import Decimal

from django.db import transaction
from django.db.models import Max
from django.utils import timezone

from apps.common.models import DomainEvent
from apps.production.models import WorkOrderOperation
from .models import (
    IntegratedScheduleScenario, PublishedOperationSchedule,
    ProductionSchedulePublication, PublishedExecutionSlot,
    ScheduleExecutionDeviation, ReschedulingTrigger, ScheduleSolverRun,
)


def _event(*, key, event_type, aggregate_type, aggregate_id, payload, actor=None):
    DomainEvent.objects.get_or_create(
        idempotency_key=key,
        defaults=dict(event_type=event_type, aggregate_type=aggregate_type,
                      aggregate_id=str(aggregate_id), payload=payload, actor=actor),
    )


@transaction.atomic
def publish_solver_run(*, run: ScheduleSolverRun, actor=None, frozen_hours=24, notes=""):
    if run.status not in {ScheduleSolverRun.Status.OPTIMAL, ScheduleSolverRun.Status.FEASIBLE}:
        raise ValueError("Somente execução CP-SAT OPTIMAL/FEASIBLE pode ser publicada.")
    if not run.assignments.exists():
        raise ValueError("Execução do solver não possui atribuições.")
    plant = run.scenario.plant
    ProductionSchedulePublication.objects.select_for_update().filter(plant=plant, status=ProductionSchedulePublication.Status.PUBLISHED).update(status=ProductionSchedulePublication.Status.SUPERSEDED)
    version = (ProductionSchedulePublication.objects.filter(plant=plant).aggregate(v=Max("version"))["v"] or 0) + 1
    freeze_until = timezone.now() + timedelta(hours=max(0, int(frozen_hours or 0)))
    pub = ProductionSchedulePublication.objects.create(
        plant=plant, scenario=run.scenario, solver_run=run, version=version,
        frozen_until=freeze_until, published_by=actor, notes=notes,
    )
    count = 0
    for assignment in run.assignments.select_related("operation", "work_center", "machine").prefetch_related("labor_assignments__labor_resource"):
        operation = assignment.operation
        team = [
            {"labor_resource_id": la.labor_resource_id, "employee_code": la.labor_resource.employee_code,
             "name": la.labor_resource.name, "start": la.start.isoformat(), "end": la.end.isoformat(),
             "shift_name": la.shift_name}
            for la in assignment.labor_assignments.all()
        ]
        frozen = assignment.start < freeze_until
        PublishedExecutionSlot.objects.create(
            publication=pub, operation=operation, work_center=assignment.work_center, machine=assignment.machine,
            planned_start=assignment.start, planned_end=assignment.end, frozen=frozen,
            team_snapshot=team, source_assignment=assignment,
            details={"solver_run": run.pk, "tardiness_minutes": assignment.tardiness_minutes},
        )
        WorkOrderOperation.objects.filter(pk=operation.pk).update(
            work_center=assignment.work_center, planned_start=assignment.start, planned_end=assignment.end
        )
        PublishedOperationSchedule.objects.update_or_create(
            operation=operation,
            defaults=dict(scenario=run.scenario, work_center=assignment.work_center, machine=assignment.machine,
                          planned_start=assignment.start, planned_end=assignment.end, published_by=actor),
        )
        count += 1
    run.scenario.status = IntegratedScheduleScenario.Status.APPLIED
    run.scenario.applied_by = actor
    run.scenario.applied_at = timezone.now()
    run.scenario.save(update_fields=["status", "applied_by", "applied_at", "updated_at"])
    pub.metrics = {"slots": count, "frozen_slots": pub.slots.filter(frozen=True).count()}
    pub.save(update_fields=["metrics", "updated_at"])
    _event(key=f"schedule-publication:{pub.pk}", event_type="PRODUCTION_SCHEDULE_PUBLISHED",
           aggregate_type="ProductionSchedulePublication", aggregate_id=pub.pk,
           payload={"plant": plant.code, "version": version, "solver_run": run.pk, "slots": count,
                    "frozen_until": freeze_until.isoformat()}, actor=actor)
    return pub


@transaction.atomic
def sync_execution_actuals(*, publication: ProductionSchedulePublication, threshold_minutes=15):
    now = timezone.now()
    started = completed = late = 0
    for slot in publication.slots.select_related("operation").all():
        op = slot.operation
        slot.actual_start = op.actual_start
        slot.actual_end = op.actual_end
        if op.actual_end:
            slot.status = PublishedExecutionSlot.Status.COMPLETED
            completed += 1
        elif op.actual_start:
            slot.status = PublishedExecutionSlot.Status.RUNNING
            started += 1
        elif now > slot.planned_end:
            slot.status = PublishedExecutionSlot.Status.MISSED
        elif now >= slot.planned_start:
            slot.status = PublishedExecutionSlot.Status.READY
        else:
            slot.status = PublishedExecutionSlot.Status.PLANNED
        slot.save(update_fields=["actual_start", "actual_end", "status", "updated_at"])
        if op.actual_start:
            mins = int((op.actual_start - slot.planned_start).total_seconds() // 60)
            if mins > threshold_minutes:
                ScheduleExecutionDeviation.objects.update_or_create(
                    slot=slot, deviation_type=ScheduleExecutionDeviation.DeviationType.LATE_START,
                    defaults={"detected_at": op.actual_start, "deviation_minutes": mins,
                              "details": {"planned": slot.planned_start.isoformat(), "actual": op.actual_start.isoformat()}},
                )
                late += 1
        if op.actual_end:
            mins = int((op.actual_end - slot.planned_end).total_seconds() // 60)
            if mins > threshold_minutes:
                ScheduleExecutionDeviation.objects.update_or_create(
                    slot=slot, deviation_type=ScheduleExecutionDeviation.DeviationType.LATE_FINISH,
                    defaults={"detected_at": op.actual_end, "deviation_minutes": mins,
                              "details": {"planned": slot.planned_end.isoformat(), "actual": op.actual_end.isoformat()}},
                )
                late += 1
    publication.metrics = {**(publication.metrics or {}), "started": started, "completed": completed,
                           "deviations": publication.slots.filter(deviations__isnull=False).distinct().count(),
                           "late_detected": late, "synced_at": now.isoformat()}
    publication.save(update_fields=["metrics", "updated_at"])
    return publication.metrics


def planned_vs_actual(publication):
    rows = []
    total_start = total_finish = 0
    count_start = count_finish = 0
    for slot in publication.slots.select_related("operation__work_order", "machine", "work_center"):
        start_var = finish_var = None
        if slot.actual_start:
            start_var = int((slot.actual_start - slot.planned_start).total_seconds() // 60)
            total_start += start_var; count_start += 1
        if slot.actual_end:
            finish_var = int((slot.actual_end - slot.planned_end).total_seconds() // 60)
            total_finish += finish_var; count_finish += 1
        rows.append({"slot": slot, "start_variance_minutes": start_var, "finish_variance_minutes": finish_var})
    return {"rows": rows, "avg_start_variance_minutes": round(total_start/count_start, 1) if count_start else None,
            "avg_finish_variance_minutes": round(total_finish/count_finish, 1) if count_finish else None,
            "completed": sum(1 for r in rows if r["slot"].actual_end), "total": len(rows)}


@transaction.atomic
def create_rescheduling_trigger(*, plant, trigger_type, affected_from=None, source_type="", source_id="", payload=None,
                                actor=None, publication=None, idempotency_key=None, auto_reschedule=True):
    publication = publication or ProductionSchedulePublication.objects.filter(plant=plant, status=ProductionSchedulePublication.Status.PUBLISHED).first()
    affected_from = affected_from or timezone.now()
    key = idempotency_key or f"replan:{plant.pk}:{trigger_type}:{source_type}:{source_id}:{affected_from.isoformat()}"
    trigger, _ = ReschedulingTrigger.objects.get_or_create(
        idempotency_key=key,
        defaults=dict(plant=plant, publication=publication, trigger_type=trigger_type, source_type=source_type,
                      source_id=str(source_id or ""), affected_from=affected_from, payload=payload or {}, created_by=actor,
                      auto_reschedule=auto_reschedule),
    )
    _event(key=f"reschedule-trigger:{trigger.pk}", event_type="RESCHEDULING_TRIGGERED",
           aggregate_type="ReschedulingTrigger", aggregate_id=trigger.pk,
           payload={"type": trigger.trigger_type, "source_type": source_type, "source_id": str(source_id or "")}, actor=actor)
    return trigger


@transaction.atomic
def prepare_rescheduling_scenario(*, trigger: ReschedulingTrigger, actor=None, horizon_days=14):
    trigger.status = ReschedulingTrigger.Status.PROCESSING
    trigger.save(update_fields=["status", "updated_at"])
    start = timezone.localdate(trigger.affected_from)
    scenario = IntegratedScheduleScenario.objects.create(
        name=f"Replan #{trigger.pk} · {trigger.get_trigger_type_display()}", plant=trigger.plant,
        horizon_start=start, horizon_end=start + timedelta(days=max(1, int(horizon_days))-1),
        scheduling_direction="FORWARD", finite_by_machine=True, allow_alternate_resources=True,
        respect_industrial_calendar=True, dispatch_rule="PRIORITY", minimize_setups=True,
        parameters={"rescheduling_trigger_id": trigger.pk, "freeze_publication_id": trigger.publication_id,
                    "affected_from": trigger.affected_from.isoformat(), "event_payload": trigger.payload},
        created_by=actor or trigger.created_by,
    )
    trigger.resulting_scenario = scenario
    trigger.processed_at = timezone.now()
    trigger.status = ReschedulingTrigger.Status.RESCHEDULED
    trigger.save(update_fields=["resulting_scenario", "processed_at", "status", "updated_at"])
    return scenario
