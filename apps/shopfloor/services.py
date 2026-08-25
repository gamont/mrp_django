from __future__ import annotations

from datetime import timedelta
from decimal import Decimal

from django.core.exceptions import ValidationError
from django.db import transaction
from django.db.models import Case, IntegerField, Q, Value, When
from django.utils import timezone

from apps.common.services import append_domain_event
from apps.production.models import WorkOrder, WorkOrderOperation
from apps.production.services import advance_work_order_operation, report_work_order_operation

from .models import DowntimeEvent, DowntimeReason, Machine, MachineProductionRecord, OperatorProfile, TerminalStation
from .oee import calculate_machine_oee

MAX_PIN_FAILURES = 5
LOCK_MINUTES = 10


def authenticate_operator(*, badge_code: str, pin: str) -> OperatorProfile:
    badge_code = (badge_code or "").strip()
    if not badge_code or not pin:
        raise ValidationError("Informe crachá e PIN.")
    try:
        profile = OperatorProfile.objects.select_related("user").get(badge_code=badge_code, is_active=True)
    except OperatorProfile.DoesNotExist as exc:
        raise ValidationError("Crachá ou PIN inválido.") from exc
    if profile.is_locked:
        raise ValidationError("Acesso temporariamente bloqueado. Tente novamente mais tarde.")
    if not profile.user.is_active or not profile.check_pin(pin):
        profile.failed_attempts += 1
        fields = ["failed_attempts", "updated_at"]
        if profile.failed_attempts >= MAX_PIN_FAILURES:
            profile.locked_until = timezone.now() + timedelta(minutes=LOCK_MINUTES)
            profile.failed_attempts = 0
            fields += ["locked_until"]
        profile.save(update_fields=fields)
        raise ValidationError("Crachá ou PIN inválido.")
    if profile.failed_attempts or profile.locked_until:
        profile.failed_attempts = 0
        profile.locked_until = None
        profile.save(update_fields=["failed_attempts", "locked_until", "updated_at"])
    return profile


def queue_for_station(station: TerminalStation):
    work_center = station.machine.work_center if station.machine_id else station.work_center
    if not work_center:
        return WorkOrderOperation.objects.none()
    status_priority = Case(
        When(status=WorkOrderOperation.Status.RUNNING, then=Value(0)),
        When(status=WorkOrderOperation.Status.INTERRUPTED, then=Value(1)),
        When(status=WorkOrderOperation.Status.SETUP, then=Value(2)),
        When(status=WorkOrderOperation.Status.READY, then=Value(3)),
        default=Value(9),
        output_field=IntegerField(),
    )
    return (
        WorkOrderOperation.objects.filter(
            work_center=work_center,
            work_order__plant=station.plant,
            work_order__status__in=[WorkOrder.Status.RELEASED, WorkOrder.Status.IN_PROGRESS],
            status__in=[
                WorkOrderOperation.Status.READY,
                WorkOrderOperation.Status.SETUP,
                WorkOrderOperation.Status.RUNNING,
                WorkOrderOperation.Status.INTERRUPTED,
            ],
        )
        .select_related("work_order", "work_order__item", "work_center")
        .annotate(status_priority=status_priority)
        .order_by("status_priority", "work_order__due_date", "work_order__number", "sequence")
    )


@transaction.atomic
def dispatch_next(*, station: TerminalStation, actor=None) -> WorkOrderOperation:
    station = TerminalStation.objects.select_for_update(of=("self",)).select_related("machine", "work_center").get(pk=station.pk)
    machine = None
    if station.machine_id:
        machine = Machine.objects.select_for_update().get(pk=station.machine_id)
        if machine.current_operation_id:
            current = WorkOrderOperation.objects.get(pk=machine.current_operation_id)
            if current.status != WorkOrderOperation.Status.COMPLETED:
                return current
    operation = queue_for_station(station).select_for_update().first()
    if not operation:
        raise ValidationError("Não há operação disponível para despacho neste centro de trabalho.")
    if operation.status == WorkOrderOperation.Status.READY:
        pass
    elif operation.status == WorkOrderOperation.Status.INTERRUPTED:
        advance_work_order_operation(operation=operation, action="READY", actor=actor)
        operation.refresh_from_db()
    if machine:
        machine.current_operation = operation
        machine.status = Machine.Status.IDLE
        machine.status_since = timezone.now()
        machine.save(update_fields=["current_operation", "status", "status_since", "updated_at"])
    append_domain_event(
        idempotency_key=f"shopfloor:dispatch:{station.pk}:{operation.pk}:{timezone.now().isoformat()}",
        event_type="SHOPFLOOR_OPERATION_DISPATCHED",
        aggregate_type="WORK_ORDER_OPERATION",
        aggregate_id=operation.pk,
        payload={"station": station.code, "machine": machine.code if machine else None},
        actor=actor,
    )
    return operation


@transaction.atomic
def machine_operation_action(*, machine: Machine, operation: WorkOrderOperation, action: str, actor=None):
    machine = Machine.objects.select_for_update().get(pk=machine.pk)
    operation = WorkOrderOperation.objects.select_for_update().select_related("work_order", "work_center").get(pk=operation.pk)
    if machine.work_center_id != operation.work_center_id:
        raise ValidationError("A operação não pertence ao centro de trabalho da máquina.")
    if machine.current_operation_id and machine.current_operation_id != operation.pk:
        raise ValidationError("A máquina já está associada a outra operação.")
    action = (action or "").upper()
    if action not in {"SETUP", "RUN", "INTERRUPT", "READY"}:
        raise ValidationError("Ação de máquina inválida.")
    operation = advance_work_order_operation(operation=operation, action=action, actor=actor)
    mapping = {
        "SETUP": Machine.Status.SETUP,
        "RUN": Machine.Status.RUNNING,
        "INTERRUPT": Machine.Status.IDLE,
        "READY": Machine.Status.IDLE,
    }
    machine.current_operation = operation
    machine.status = mapping[action]
    machine.status_since = timezone.now()
    machine.save(update_fields=["current_operation", "status", "status_since", "updated_at"])
    return operation


@transaction.atomic
def report_and_complete(*, machine: Machine, operation: WorkOrderOperation, good_quantity=Decimal("0"), scrap_quantity=Decimal("0"), labor_hours=Decimal("0"), machine_hours=Decimal("0"), notes="", actor=None):
    machine = Machine.objects.select_for_update().get(pk=machine.pk)
    if machine.current_operation_id != operation.pk:
        raise ValidationError("A operação informada não é a operação atual da máquina.")
    report = report_work_order_operation(
        operation=operation,
        good_quantity=good_quantity,
        scrap_quantity=scrap_quantity,
        labor_hours=labor_hours,
        machine_hours=machine_hours,
        notes=notes,
        actor=actor,
    )
    MachineProductionRecord.objects.get_or_create(
        report=report,
        defaults={"machine": machine, "operation": operation, "reported_at": report.reported_at},
    )
    machine.current_operation = None
    machine.status = Machine.Status.IDLE
    machine.status_since = timezone.now()
    machine.save(update_fields=["current_operation", "status", "status_since", "updated_at"])
    calculate_machine_oee(machine=machine, metric_date=timezone.localdate(report.reported_at))
    return report


@transaction.atomic
def start_downtime(*, machine: Machine, reason: DowntimeReason, notes: str = "", actor=None) -> DowntimeEvent:
    machine = Machine.objects.select_for_update().get(pk=machine.pk)
    if reason.plant_id != machine.plant_id:
        raise ValidationError("O motivo de parada não pertence à planta da máquina.")
    if DowntimeEvent.objects.select_for_update().filter(machine=machine, ended_at__isnull=True).exists():
        raise ValidationError("A máquina já possui uma parada aberta.")
    operation = machine.current_operation
    if operation and operation.status in {WorkOrderOperation.Status.SETUP, WorkOrderOperation.Status.RUNNING}:
        advance_work_order_operation(operation=operation, action="INTERRUPT", actor=actor)
    event = DowntimeEvent.objects.create(
        machine=machine,
        operation=operation,
        reason=reason,
        started_at=timezone.now(),
        notes=notes,
        reported_by=actor if getattr(actor, "is_authenticated", False) else None,
    )
    machine.status = Machine.Status.DOWN
    machine.status_since = event.started_at
    machine.save(update_fields=["status", "status_since", "updated_at"])
    append_domain_event(
        idempotency_key=f"shopfloor:downtime:start:{event.pk}",
        event_type="MACHINE_DOWNTIME_STARTED",
        aggregate_type="MACHINE",
        aggregate_id=machine.pk,
        payload={"reason": reason.code, "operation": operation.pk if operation else None},
        actor=actor,
    )
    return event


@transaction.atomic
def end_downtime(*, machine: Machine, actor=None) -> DowntimeEvent:
    machine = Machine.objects.select_for_update().get(pk=machine.pk)
    try:
        event = DowntimeEvent.objects.select_for_update().get(machine=machine, ended_at__isnull=True)
    except DowntimeEvent.DoesNotExist as exc:
        raise ValidationError("A máquina não possui parada aberta.") from exc
    event.ended_at = timezone.now()
    event.save(update_fields=["ended_at", "updated_at"])
    machine.status = Machine.Status.IDLE
    machine.status_since = event.ended_at
    machine.save(update_fields=["status", "status_since", "updated_at"])
    append_domain_event(
        idempotency_key=f"shopfloor:downtime:end:{event.pk}",
        event_type="MACHINE_DOWNTIME_ENDED",
        aggregate_type="MACHINE",
        aggregate_id=machine.pk,
        payload={"duration_seconds": event.duration_seconds},
        actor=actor,
    )
    calculate_machine_oee(machine=machine, metric_date=timezone.localdate(event.started_at))
    if timezone.localdate(event.ended_at) != timezone.localdate(event.started_at):
        calculate_machine_oee(machine=machine, metric_date=timezone.localdate(event.ended_at))
    return event


def station_context(station: TerminalStation) -> dict:
    station = TerminalStation.objects.select_related("plant", "work_center", "machine", "machine__work_center", "machine__current_operation", "machine__current_operation__work_order", "machine__current_operation__work_order__item").get(pk=station.pk)
    queue = list(queue_for_station(station)[:20])
    machine = station.machine
    open_downtime = None
    oee_snapshot = None
    if machine:
        open_downtime = machine.downtime_events.filter(ended_at__isnull=True).select_related("reason").first()
        oee_snapshot = calculate_machine_oee(machine=machine, metric_date=timezone.localdate())
    return {
        "station": station,
        "machine": machine,
        "current_operation": machine.current_operation if machine else None,
        "queue": queue,
        "downtime_reasons": DowntimeReason.objects.filter(plant=station.plant, is_active=True).order_by("code"),
        "open_downtime": open_downtime,
        "oee_snapshot": oee_snapshot,
    }
