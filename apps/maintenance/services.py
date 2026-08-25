from __future__ import annotations

from datetime import datetime, time, timedelta
from decimal import Decimal

from django.core.exceptions import ValidationError
from django.db import models, transaction
from django.db.models import Max
from django.utils import timezone

from apps.common.services import append_domain_event
from apps.inventory.models import InventoryTransaction, Location
from apps.inventory.services import post_inventory_transaction
from apps.shopfloor.models import DowntimeEvent, DowntimeReason, Machine

from .models import (
    AssetMeterReading,
    FailureEvent,
    MaintenanceAsset,
    MaintenancePart,
    MaintenancePlan,
    MaintenanceWorkOrder,
)


def _event(*, event_type, aggregate_type, aggregate_id, actor=None, payload=None, key=None):
    append_domain_event(
        event_type=event_type,
        aggregate_type=aggregate_type,
        aggregate_id=str(aggregate_id),
        actor=actor,
        payload=payload or {},
        idempotency_key=key or f"{event_type}:{aggregate_type}:{aggregate_id}:{timezone.now().isoformat()}",
    )


def _next_order_number(plant) -> str:
    prefix = f"OM-{timezone.localdate():%Y}-"
    last = (
        MaintenanceWorkOrder.objects.filter(plant=plant, number__startswith=prefix)
        .order_by("-number")
        .values_list("number", flat=True)
        .first()
    )
    seq = int(last.rsplit("-", 1)[-1]) + 1 if last else 1
    return f"{prefix}{seq:05d}"


def latest_meter(asset: MaintenanceAsset) -> Decimal:
    value = asset.meter_readings.aggregate(v=Max("meter_value"))["v"]
    return value if value is not None else Decimal("0")


def plan_is_due(plan: MaintenancePlan, *, on_date=None) -> bool:
    on_date = on_date or timezone.localdate()
    due_date = plan.next_due_date is not None and plan.next_due_date <= on_date
    due_meter = plan.next_due_meter is not None and latest_meter(plan.asset) >= plan.next_due_meter
    if plan.strategy == MaintenancePlan.Strategy.CALENDAR:
        return due_date
    if plan.strategy == MaintenancePlan.Strategy.METER:
        return due_meter
    return due_date or due_meter


@transaction.atomic
def generate_preventive_orders(*, plant, through_date=None, actor=None):
    through_date = through_date or timezone.localdate()
    created = []
    plans = (
        MaintenancePlan.objects.select_for_update(of=("self",))
        .select_related("asset", "asset__machine")
        .filter(asset__plant=plant, asset__is_active=True, is_active=True)
    )
    for plan in plans:
        if not plan_is_due(plan, on_date=through_date):
            continue
        open_existing = plan.work_orders.filter(
            status__in=[
                MaintenanceWorkOrder.Status.PLANNED,
                MaintenanceWorkOrder.Status.RELEASED,
                MaintenanceWorkOrder.Status.IN_PROGRESS,
                MaintenanceWorkOrder.Status.WAITING_PARTS,
            ]
        ).first()
        if open_existing:
            continue
        due_date = plan.next_due_date or through_date
        scheduled_start = timezone.make_aware(datetime.combine(due_date, time(hour=8)))
        scheduled_end = scheduled_start + timedelta(hours=float(plan.planned_duration_hours or 0))
        wo = MaintenanceWorkOrder.objects.create(
            plant=plant,
            number=_next_order_number(plant),
            asset=plan.asset,
            plan=plan,
            order_type=MaintenanceWorkOrder.OrderType.PREVENTIVE,
            priority=MaintenanceWorkOrder.Priority.NORMAL,
            status=MaintenanceWorkOrder.Status.PLANNED,
            title=plan.title,
            description=plan.instructions,
            scheduled_start=scheduled_start,
            scheduled_end=scheduled_end,
            requested_by=actor,
        )
        created.append(wo)
        _event(
            event_type="MAINTENANCE_ORDER_GENERATED",
            aggregate_type="MaintenanceWorkOrder",
            aggregate_id=wo.pk,
            actor=actor,
            payload={"number": wo.number, "plan": plan.code, "asset": plan.asset.code},
            key=f"maint-generated:{wo.pk}",
        )
    return created


def _maintenance_reason(plant, *, planned: bool):
    code = "MAINT-PREV" if planned else "MAINT-CORR"
    description = "Manutenção preventiva" if planned else "Manutenção corretiva"
    category = DowntimeReason.Category.PLANNED if planned else DowntimeReason.Category.UNPLANNED
    reason, _ = DowntimeReason.objects.get_or_create(
        plant=plant, code=code, defaults={"description": description, "category": category}
    )
    if reason.category != category:
        reason.category = category
        reason.description = description
        reason.save(update_fields=["category", "description", "updated_at"])
    return reason


@transaction.atomic
def start_work_order(*, work_order: MaintenanceWorkOrder, actor=None):
    wo = MaintenanceWorkOrder.objects.select_for_update(of=("self",)).select_related("asset__machine", "plant").get(pk=work_order.pk)
    if wo.status not in {MaintenanceWorkOrder.Status.PLANNED, MaintenanceWorkOrder.Status.RELEASED, MaintenanceWorkOrder.Status.WAITING_PARTS}:
        raise ValidationError("A ordem não pode ser iniciada no status atual.")
    now = timezone.now()
    wo.status = MaintenanceWorkOrder.Status.IN_PROGRESS
    wo.started_at = wo.started_at or now
    machine = wo.asset.machine
    if machine:
        machine = Machine.objects.select_for_update().get(pk=machine.pk)
        if DowntimeEvent.objects.filter(machine=machine, ended_at__isnull=True).exists():
            raise ValidationError("A máquina já possui uma parada aberta.")
        event = DowntimeEvent.objects.create(
            machine=machine,
            reason=_maintenance_reason(wo.plant, planned=wo.order_type == MaintenanceWorkOrder.OrderType.PREVENTIVE),
            started_at=now,
            notes=f"Manutenção {wo.number}",
            reported_by=actor,
        )
        wo.downtime_event = event
        wo.failure_events.filter(downtime_event__isnull=True).update(downtime_event=event)
        machine.status = Machine.Status.PREVENTIVE if wo.order_type == MaintenanceWorkOrder.OrderType.PREVENTIVE else Machine.Status.REPAIR
        machine.status_since = now
        machine.save(update_fields=["status", "status_since", "updated_at"])
    wo.save(update_fields=["status", "started_at", "downtime_event", "updated_at"])
    _event(event_type="MAINTENANCE_ORDER_STARTED", aggregate_type="MaintenanceWorkOrder", aggregate_id=wo.pk, actor=actor, payload={"number": wo.number}, key=f"maint-start:{wo.pk}:{wo.started_at.isoformat()}")
    return wo


@transaction.atomic
def complete_work_order(*, work_order: MaintenanceWorkOrder, completion_notes="", meter_value=None, actor=None):
    wo = MaintenanceWorkOrder.objects.select_for_update(of=("self",)).select_related("asset__machine", "plan").get(pk=work_order.pk)
    if wo.status != MaintenanceWorkOrder.Status.IN_PROGRESS:
        raise ValidationError("Somente ordens em execução podem ser concluídas.")
    now = timezone.now()
    wo.status = MaintenanceWorkOrder.Status.COMPLETED
    wo.completed_at = now
    wo.completion_notes = completion_notes or ""
    if meter_value is not None:
        meter_value = Decimal(str(meter_value))
        reading = AssetMeterReading.objects.create(asset=wo.asset, meter_value=meter_value, reading_at=now, recorded_by=actor, source="MAINTENANCE")
        wo.meter_at_completion = reading.meter_value
    if wo.downtime_event_id:
        event = DowntimeEvent.objects.select_for_update().get(pk=wo.downtime_event_id)
        if event.ended_at is None:
            event.ended_at = now
            event.save(update_fields=["ended_at", "updated_at"])
    if wo.asset.machine_id:
        machine = Machine.objects.select_for_update().get(pk=wo.asset.machine_id)
        machine.status = Machine.Status.IDLE
        machine.status_since = now
        machine.save(update_fields=["status", "status_since", "updated_at"])
    if wo.plan_id:
        plan = MaintenancePlan.objects.select_for_update(of=("self",)).get(pk=wo.plan_id)
        if plan.interval_days and plan.strategy in {MaintenancePlan.Strategy.CALENDAR, MaintenancePlan.Strategy.HYBRID}:
            plan.next_due_date = timezone.localdate() + timedelta(days=plan.interval_days)
        if plan.interval_meter and plan.strategy in {MaintenancePlan.Strategy.METER, MaintenancePlan.Strategy.HYBRID}:
            base = wo.meter_at_completion if wo.meter_at_completion is not None else latest_meter(wo.asset)
            plan.next_due_meter = base + plan.interval_meter
        plan.save(update_fields=["next_due_date", "next_due_meter", "updated_at"])
    wo.save(update_fields=["status", "completed_at", "completion_notes", "meter_at_completion", "updated_at"])
    for failure in wo.failure_events.filter(resolved_at__isnull=True):
        failure.resolved_at = now
        failure.corrective_action = failure.corrective_action or completion_notes
        failure.save(update_fields=["resolved_at", "corrective_action", "updated_at"])
    _event(event_type="MAINTENANCE_ORDER_COMPLETED", aggregate_type="MaintenanceWorkOrder", aggregate_id=wo.pk, actor=actor, payload={"number": wo.number}, key=f"maint-complete:{wo.pk}:{now.isoformat()}")
    return wo


@transaction.atomic
def issue_maintenance_part(*, part: MaintenancePart, location: Location, quantity, actor=None, idempotency_key=None):
    part = MaintenancePart.objects.select_for_update().select_related("work_order", "item").get(pk=part.pk)
    quantity = Decimal(str(quantity))
    if quantity <= 0:
        raise ValidationError("A quantidade deve ser positiva.")
    if location.warehouse.plant_id != part.work_order.plant_id:
        raise ValidationError("O local deve pertencer à planta da ordem de manutenção.")
    # Consome primeiro as reservas da própria OM para liberar o saldo alocado
    # antes da baixa física genérica. Toda a operação permanece atômica.
    from apps.inventory.models import Reservation, StockBalance
    reserved_to_release = quantity
    links = part.reservations.select_related("reservation").filter(
        reservation__location=location, reservation__status=Reservation.Status.OPEN
    ).order_by("reservation_id")
    for link in links:
        if reserved_to_release <= 0:
            break
        reservation = Reservation.objects.select_for_update().get(pk=link.reservation_id)
        take = min(reservation.remaining_quantity, reserved_to_release)
        if take <= 0:
            continue
        balance = StockBalance.objects.select_for_update().get(item=part.item, location=location)
        balance.allocated = max(Decimal("0"), balance.allocated - take)
        balance.save(update_fields=["allocated", "updated_at"])
        reservation.consumed_quantity += take
        reservation.consumed_requested_quantity += take
        if reservation.consumed_quantity >= reservation.quantity:
            reservation.status = Reservation.Status.CONSUMED
        reservation.save(update_fields=["consumed_quantity", "consumed_requested_quantity", "status", "updated_at"])
        reserved_to_release -= take

    tx = InventoryTransaction(
        transaction_type=InventoryTransaction.TransactionType.ISSUE,
        item=part.item,
        from_location=location,
        quantity=quantity,
        reference_type="MAINTENANCE_WORK_ORDER",
        reference_id=part.work_order.number,
        posted_by=actor,
        notes=f"Peça para manutenção {part.work_order.number}",
        idempotency_key=idempotency_key or f"maint-part:{part.pk}:{part.issued_quantity}:{quantity}",
    )
    posted = post_inventory_transaction(tx)
    if part.issue_transaction_id != posted.pk:
        part.issued_quantity += quantity
        part.source_location = location
        part.issue_transaction = posted
        part.save(update_fields=["issued_quantity", "source_location", "issue_transaction", "updated_at"])
    _event(event_type="MAINTENANCE_PART_ISSUED", aggregate_type="MaintenanceWorkOrder", aggregate_id=part.work_order_id, actor=actor, payload={"item": part.item.code, "quantity": str(quantity)}, key=f"maint-part-event:{posted.pk}")
    return part


@transaction.atomic
def report_failure(*, asset: MaintenanceAsset, symptom: str, failure_class=FailureEvent.FailureClass.OTHER, actor=None, priority=MaintenanceWorkOrder.Priority.EMERGENCY):
    if not (symptom or "").strip():
        raise ValidationError("Informe o sintoma da falha.")
    now = timezone.now()
    wo = MaintenanceWorkOrder.objects.create(
        plant=asset.plant,
        number=_next_order_number(asset.plant),
        asset=asset,
        order_type=MaintenanceWorkOrder.OrderType.CORRECTIVE,
        priority=priority,
        status=MaintenanceWorkOrder.Status.RELEASED,
        title=f"Corretiva - {asset.code}",
        description=symptom,
        requested_at=now,
        requested_by=actor,
    )
    failure = FailureEvent.objects.create(
        asset=asset,
        work_order=wo,
        failure_class=failure_class,
        occurred_at=now,
        symptom=symptom,
        reported_by=actor,
    )
    _event(event_type="MAINTENANCE_FAILURE_REPORTED", aggregate_type="MaintenanceAsset", aggregate_id=asset.pk, actor=actor, payload={"work_order": wo.number, "failure": failure.pk}, key=f"maint-failure:{failure.pk}")
    return failure, wo


def maintenance_part_availability(work_order: MaintenanceWorkOrder):
    """Return available quantities, counting reservations already committed to this OM."""
    from django.db.models import Sum
    from apps.inventory.models import Reservation, StockBalance
    rows = []
    all_available = True
    for part in work_order.parts.select_related("item"):
        remaining = part.remaining_quantity
        aggregate = StockBalance.objects.filter(
            item=part.item, location__warehouse__plant=work_order.plant
        ).aggregate(on_hand=Sum("on_hand"), allocated=Sum("allocated"))
        globally_free = (aggregate["on_hand"] or Decimal("0")) - (aggregate["allocated"] or Decimal("0"))
        own_reserved = sum((
            link.reservation.remaining_quantity
            for link in part.reservations.select_related("reservation").filter(reservation__status=Reservation.Status.OPEN)
        ), Decimal("0"))
        effective_available = globally_free + own_reserved
        sufficient = effective_available >= remaining
        all_available = all_available and sufficient
        rows.append({"part": part, "remaining": remaining, "available": effective_available, "reserved": own_reserved, "sufficient": sufficient})
    return all_available, rows


@transaction.atomic
def release_work_order(*, work_order: MaintenanceWorkOrder, actor=None, require_parts=True):
    wo = MaintenanceWorkOrder.objects.select_for_update().get(pk=work_order.pk)
    if wo.status != MaintenanceWorkOrder.Status.PLANNED:
        raise ValidationError("Somente ordens planejadas podem ser liberadas.")
    available, rows = maintenance_part_availability(wo)
    if require_parts and not available:
        wo.status = MaintenanceWorkOrder.Status.WAITING_PARTS
        wo.save(update_fields=["status", "updated_at"])
        missing = ", ".join(f"{r['part'].item.code}: falta {r['remaining'] - r['available']}" for r in rows if not r["sufficient"])
        _event(event_type="MAINTENANCE_ORDER_WAITING_PARTS", aggregate_type="MaintenanceWorkOrder", aggregate_id=wo.pk, actor=actor, payload={"number": wo.number, "missing": missing}, key=f"maint-waiting-parts:{wo.pk}:{wo.updated_at.isoformat()}")
        return wo
    wo.status = MaintenanceWorkOrder.Status.RELEASED
    wo.save(update_fields=["status", "updated_at"])
    _event(event_type="MAINTENANCE_ORDER_RELEASED", aggregate_type="MaintenanceWorkOrder", aggregate_id=wo.pk, actor=actor, payload={"number": wo.number}, key=f"maint-release:{wo.pk}")
    return wo


def _rule_triggered(rule, value):
    value = Decimal(str(value))
    threshold = rule.threshold
    return {
        "GT": value > threshold,
        "GTE": value >= threshold,
        "LT": value < threshold,
        "LTE": value <= threshold,
    }[rule.comparator]


@transaction.atomic
def evaluate_condition_reading(*, reading, actor=None):
    from .models import ConditionRule
    triggered = []
    rules = ConditionRule.objects.filter(asset=reading.asset, metric=reading.metric, is_active=True)
    if reading.metric_name:
        rules = rules.filter(metric_name=reading.metric_name)
    for rule in rules.select_for_update():
        if not _rule_triggered(rule, reading.value):
            continue
        existing = MaintenanceWorkOrder.objects.filter(
            asset=reading.asset,
            order_type=MaintenanceWorkOrder.OrderType.PREDICTIVE,
            title=rule.title,
            status__in=[MaintenanceWorkOrder.Status.PLANNED, MaintenanceWorkOrder.Status.RELEASED, MaintenanceWorkOrder.Status.IN_PROGRESS, MaintenanceWorkOrder.Status.WAITING_PARTS],
        ).first()
        if existing:
            triggered.append(existing)
            continue
        wo = MaintenanceWorkOrder.objects.create(
            plant=reading.asset.plant,
            number=_next_order_number(reading.asset.plant),
            asset=reading.asset,
            order_type=MaintenanceWorkOrder.OrderType.PREDICTIVE,
            priority=rule.priority,
            status=MaintenanceWorkOrder.Status.PLANNED,
            title=rule.title,
            description=f"Condição {reading.get_metric_display()}: {reading.value} {reading.unit}; limite {rule.get_comparator_display()} {rule.threshold}.",
            requested_by=actor,
        )
        triggered.append(wo)
        _event(event_type="MAINTENANCE_CONDITION_TRIGGERED", aggregate_type="MaintenanceAsset", aggregate_id=reading.asset_id, actor=actor, payload={"reading": reading.pk, "rule": rule.pk, "work_order": wo.number}, key=f"maint-condition:{reading.pk}:{rule.pk}")
    return triggered


def sla_status(work_order: MaintenanceWorkOrder, *, now=None):
    from .models import MaintenanceSLA
    now = now or timezone.now()
    sla = MaintenanceSLA.objects.filter(plant=work_order.plant, priority=work_order.priority, is_active=True).first()
    if not sla:
        return {"sla": None, "response_due": None, "resolution_due": None, "response_breached": False, "resolution_breached": False}
    response_due = work_order.requested_at + timedelta(hours=float(sla.response_hours))
    resolution_due = work_order.requested_at + timedelta(hours=float(sla.resolution_hours))
    response_breached = work_order.started_at is None and now > response_due
    resolution_breached = work_order.completed_at is None and now > resolution_due
    return {"sla": sla, "response_due": response_due, "resolution_due": resolution_due, "response_breached": response_breached, "resolution_breached": resolution_breached}


def weekly_maintenance_plan(*, plant, week_start):
    from django.db.models import Sum
    from .models import TechnicianProfile, WorkOrderAssignment
    week_end = week_start + timedelta(days=7)
    orders = MaintenanceWorkOrder.objects.filter(plant=plant, scheduled_start__date__gte=week_start, scheduled_start__date__lt=week_end).select_related("asset", "assigned_to").order_by("scheduled_start")
    technicians = TechnicianProfile.objects.filter(plant=plant, is_active=True).select_related("user")
    load = {t.pk: Decimal("0") for t in technicians}
    assignments = WorkOrderAssignment.objects.filter(technician__in=technicians, work_order__scheduled_start__date__gte=week_start, work_order__scheduled_start__date__lt=week_end).values("technician_id").annotate(hours=Sum("planned_hours"))
    for row in assignments:
        load[row["technician_id"]] = row["hours"] or Decimal("0")
    tech_rows = [{"technician": t, "load_hours": load[t.pk], "capacity_hours": t.daily_capacity_hours * Decimal("5"), "utilization": (load[t.pk] / (t.daily_capacity_hours * Decimal("5")) * 100) if t.daily_capacity_hours else Decimal("0")} for t in technicians]
    return {"week_start": week_start, "week_end": week_end - timedelta(days=1), "orders": orders, "technicians": tech_rows}


def failure_pareto(*, plant, start_date, end_date):
    from django.db.models import Count
    qs = FailureEvent.objects.filter(asset__plant=plant, occurred_at__date__gte=start_date, occurred_at__date__lte=end_date)
    rows = list(qs.values("failure_class").annotate(count=Count("id")).order_by("-count"))
    total = sum(r["count"] for r in rows) or 1
    cumulative = 0
    labels = dict(FailureEvent.FailureClass.choices)
    for row in rows:
        cumulative += row["count"]
        row["label"] = labels.get(row["failure_class"], row["failure_class"])
        row["percentage"] = round(row["count"] * 100 / total, 1)
        row["cumulative_percentage"] = round(cumulative * 100 / total, 1)
    return rows


def maintenance_priority_score(work_order: MaintenanceWorkOrder, *, now=None):
    """Score 0..100+ combining criticality, priority, SLA urgency and recent OEE loss."""
    from apps.shopfloor.models import OEEPeriodSnapshot
    now = now or timezone.now()
    priority_weight = {
        MaintenanceWorkOrder.Priority.LOW: Decimal("5"),
        MaintenanceWorkOrder.Priority.NORMAL: Decimal("15"),
        MaintenanceWorkOrder.Priority.HIGH: Decimal("30"),
        MaintenanceWorkOrder.Priority.EMERGENCY: Decimal("45"),
    }[work_order.priority]
    criticality_weight = {
        MaintenanceAsset.Criticality.LOW: Decimal("5"),
        MaintenanceAsset.Criticality.MEDIUM: Decimal("10"),
        MaintenanceAsset.Criticality.HIGH: Decimal("20"),
        MaintenanceAsset.Criticality.CRITICAL: Decimal("30"),
    }[work_order.asset.criticality]
    sla = sla_status(work_order, now=now)
    sla_weight = Decimal("0")
    if sla["response_breached"]:
        sla_weight += Decimal("15")
    if sla["resolution_breached"]:
        sla_weight += Decimal("20")
    oee_weight = Decimal("0")
    oee_pct = None
    if work_order.asset.machine_id:
        snap = OEEPeriodSnapshot.objects.filter(machine_id=work_order.asset.machine_id).order_by("-metric_date").first()
        if snap:
            oee_pct = snap.oee * Decimal("100")
            if snap.oee < Decimal("0.60"):
                oee_weight = Decimal("20")
            elif snap.oee < Decimal("0.75"):
                oee_weight = Decimal("12")
            elif snap.oee < Decimal("0.85"):
                oee_weight = Decimal("6")
    age_days = max(0, (now.date() - work_order.requested_at.date()).days)
    age_weight = min(Decimal("10"), Decimal(age_days) / Decimal("2"))
    total = priority_weight + criticality_weight + sla_weight + oee_weight + age_weight
    reason = {
        "priority": str(priority_weight),
        "criticality": str(criticality_weight),
        "sla": str(sla_weight),
        "oee": str(oee_weight),
        "age": str(age_weight),
        "recent_oee_pct": str(oee_pct.quantize(Decimal("0.1"))) if oee_pct is not None else None,
    }
    return total.quantize(Decimal("0.01")), reason


@transaction.atomic
def refresh_priority_scores(*, plant):
    rows = []
    qs = MaintenanceWorkOrder.objects.select_for_update().select_related("asset").filter(
        plant=plant,
        status__in=[MaintenanceWorkOrder.Status.PLANNED, MaintenanceWorkOrder.Status.RELEASED, MaintenanceWorkOrder.Status.WAITING_PARTS, MaintenanceWorkOrder.Status.IN_PROGRESS],
    )
    for wo in qs:
        score, reason = maintenance_priority_score(wo)
        wo.priority_score = score
        wo.priority_reason = reason
        wo.save(update_fields=["priority_score", "priority_reason", "updated_at"])
        rows.append(wo)
    return rows


def detect_schedule_conflicts(work_order: MaintenanceWorkOrder, *, persist=True):
    from apps.production.models import WorkOrderOperation
    from .models import MaintenanceScheduleConflict
    if not work_order.scheduled_start or not work_order.scheduled_end:
        return []
    conflicts = []
    wc = work_order.asset.work_center or (work_order.asset.machine.work_center if work_order.asset.machine_id else None)
    if wc:
        operations = WorkOrderOperation.objects.select_related("work_order").filter(
            work_center=wc,
            status__in=[WorkOrderOperation.Status.PENDING, WorkOrderOperation.Status.READY, WorkOrderOperation.Status.SETUP, WorkOrderOperation.Status.RUNNING, WorkOrderOperation.Status.INTERRUPTED],
            planned_start__lt=work_order.scheduled_end,
            planned_end__gt=work_order.scheduled_start,
        )
        for op in operations:
            conflicts.append({
                "type": MaintenanceScheduleConflict.ConflictType.PRODUCTION,
                "severity": MaintenanceScheduleConflict.Severity.CRITICAL if work_order.asset.criticality == MaintenanceAsset.Criticality.CRITICAL else MaintenanceScheduleConflict.Severity.WARNING,
                "message": f"Conflito com {op.work_order.number} / operação {op.sequence} ({wc.code}).",
                "operation": op,
            })
    if persist:
        now = timezone.now()
        MaintenanceScheduleConflict.objects.filter(work_order=work_order, resolved_at__isnull=True).update(resolved_at=now)
        for row in conflicts:
            MaintenanceScheduleConflict.objects.create(
                work_order=work_order,
                conflict_type=row["type"], severity=row["severity"], message=row["message"], related_operation=row["operation"]
            )
    return conflicts


def _technician_week_load(technician, week_start, exclude_work_order=None):
    from django.db.models import Sum
    from .models import WorkOrderAssignment
    week_end = week_start + timedelta(days=7)
    qs = WorkOrderAssignment.objects.filter(
        technician=technician,
        work_order__scheduled_start__date__gte=week_start,
        work_order__scheduled_start__date__lt=week_end,
    )
    if exclude_work_order:
        qs = qs.exclude(work_order=exclude_work_order)
    return qs.aggregate(v=Sum("planned_hours"))["v"] or Decimal("0")


@transaction.atomic
def auto_assign_technicians(*, work_order: MaintenanceWorkOrder, actor=None, replace=False):
    from .models import TechnicianProfile, TechnicianSkillAssignment, WorkOrderAssignment
    wo = MaintenanceWorkOrder.objects.select_for_update().get(pk=work_order.pk)
    if not wo.scheduled_start:
        raise ValidationError("Programe a OM antes da alocação automática.")
    requirements = list(wo.required_skills.select_related("skill"))
    technicians = list(TechnicianProfile.objects.filter(plant=wo.plant, is_active=True).select_related("user"))
    week_start = wo.scheduled_start.date() - timedelta(days=wo.scheduled_start.date().weekday())
    candidates = []
    for tech in technicians:
        valid = True
        skill_score = Decimal("0")
        for req in requirements:
            assignment = TechnicianSkillAssignment.objects.filter(technician=tech, skill=req.skill, proficiency__gte=req.min_proficiency).filter(models.Q(valid_until__isnull=True) | models.Q(valid_until__gte=wo.scheduled_start.date())).first()
            if not assignment:
                valid = False
                break
            skill_score += Decimal(assignment.proficiency)
        if not valid:
            continue
        load = _technician_week_load(tech, week_start, wo)
        capacity = tech.daily_capacity_hours * Decimal("5")
        free = max(Decimal("0"), capacity - load)
        candidates.append((free, skill_score, tech))
    candidates.sort(key=lambda row: (row[0], row[1]), reverse=True)
    needed = max([r.technicians_required for r in requirements], default=1)
    if len(candidates) < needed:
        raise ValidationError(f"Não há técnicos suficientes com os skills requeridos ({needed} necessário(s)).")
    if replace:
        wo.technician_assignments.all().delete()
    duration = Decimal("0")
    if wo.scheduled_start and wo.scheduled_end:
        duration = Decimal(str((wo.scheduled_end - wo.scheduled_start).total_seconds() / 3600)).quantize(Decimal("0.01"))
    if not duration and wo.plan_id:
        duration = wo.plan.planned_duration_hours
    selected = []
    for idx, (_, _, tech) in enumerate(candidates[:needed]):
        assignment, _ = WorkOrderAssignment.objects.update_or_create(
            work_order=wo, technician=tech,
            defaults={"planned_hours": duration, "is_lead": idx == 0},
        )
        selected.append(assignment)
    if selected:
        wo.assigned_to = selected[0].technician.user
        wo.save(update_fields=["assigned_to", "updated_at"])
    _event(event_type="MAINTENANCE_TECHNICIANS_AUTO_ASSIGNED", aggregate_type="MaintenanceWorkOrder", aggregate_id=wo.pk, actor=actor, payload={"technicians": [a.technician.employee_code for a in selected]})
    return selected


@transaction.atomic
def reserve_maintenance_parts(*, work_order: MaintenanceWorkOrder, actor=None):
    from apps.inventory.models import Reservation, StockBalance
    from .models import MaintenancePartReservation
    wo = MaintenanceWorkOrder.objects.select_for_update().get(pk=work_order.pk)
    results = []
    for part in wo.parts.select_related("item"):
        already = sum((link.reservation.remaining_quantity for link in part.reservations.select_related("reservation").filter(reservation__status=Reservation.Status.OPEN)), Decimal("0"))
        remaining = max(Decimal("0"), part.remaining_quantity - already)
        if remaining <= 0:
            continue
        balances = StockBalance.objects.select_for_update().filter(item=part.item, location__warehouse__plant=wo.plant).select_related("location").order_by("location_id")
        for balance in balances:
            available = balance.on_hand - balance.allocated
            if available <= 0:
                continue
            qty = min(available, remaining)
            balance.allocated += qty
            balance.save(update_fields=["allocated", "updated_at"])
            reservation = Reservation.objects.create(
                item=part.item, requested_item=part.item, location=balance.location,
                quantity=qty, requested_quantity=qty,
                demand_type="MAINTENANCE_WORK_ORDER", demand_id=str(wo.pk),
                required_date=(wo.scheduled_start.date() if wo.scheduled_start else timezone.localdate()),
            )
            MaintenancePartReservation.objects.create(part=part, reservation=reservation)
            results.append(reservation)
            remaining -= qty
            if remaining <= 0:
                break
        if remaining > 0:
            raise ValidationError(f"Estoque insuficiente para reservar {part.item.code}: falta {remaining}.")
    _event(event_type="MAINTENANCE_PARTS_RESERVED", aggregate_type="MaintenanceWorkOrder", aggregate_id=wo.pk, actor=actor, payload={"reservations": [r.pk for r in results]})
    return results


@transaction.atomic
def schedule_maintenance_work_order(*, work_order: MaintenanceWorkOrder, start, end, actor=None, force=False):
    wo = MaintenanceWorkOrder.objects.select_for_update().get(pk=work_order.pk)
    if wo.scheduling_locked:
        raise ValidationError("A programação desta OM está bloqueada.")
    if end <= start:
        raise ValidationError("O fim da programação deve ser posterior ao início.")
    wo.scheduled_start = start
    wo.scheduled_end = end
    score, reason = maintenance_priority_score(wo)
    wo.priority_score = score
    wo.priority_reason = reason
    wo.save(update_fields=["scheduled_start", "scheduled_end", "priority_score", "priority_reason", "updated_at"])
    conflicts = detect_schedule_conflicts(wo, persist=True)
    if conflicts and not force:
        raise ValidationError("Conflito manutenção × produção detectado. Reprograme ou use force=true.")
    _event(event_type="MAINTENANCE_ORDER_SCHEDULED", aggregate_type="MaintenanceWorkOrder", aggregate_id=wo.pk, actor=actor, payload={"start": start.isoformat(), "end": end.isoformat(), "forced": force})
    return wo, conflicts


def maintenance_kanban(*, plant):
    refresh_priority_scores(plant=plant)
    qs = MaintenanceWorkOrder.objects.filter(plant=plant).select_related("asset").order_by("-priority_score", "requested_at")
    columns = {}
    for status, label in MaintenanceWorkOrder.Status.choices:
        if status in {MaintenanceWorkOrder.Status.COMPLETED, MaintenanceWorkOrder.Status.CANCELLED}:
            continue
        columns[status] = {"label": label, "orders": list(qs.filter(status=status)[:50])}
    return columns
