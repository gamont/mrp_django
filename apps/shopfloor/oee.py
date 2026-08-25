from __future__ import annotations

from collections import defaultdict
from datetime import date, datetime, time, timedelta
from decimal import Decimal, ROUND_HALF_UP

from django.db import transaction
from django.db.models import Q, Sum
from django.utils import timezone

from apps.masterdata.models import WorkCenterShift

from .models import (
    DowntimeEvent,
    DowntimeReason,
    Machine,
    MachineProductionRecord,
    OEEPeriodSnapshot,
    OEEShiftSnapshot,
    OEETarget,
)

D0 = Decimal("0")
D1 = Decimal("1")
Q4 = Decimal("0.0001")
Q2 = Decimal("0.01")


def _ratio(numerator: Decimal, denominator: Decimal) -> Decimal:
    if denominator <= 0:
        return D0
    return min(D1, max(D0, numerator / denominator)).quantize(Q4, rounding=ROUND_HALF_UP)


def _aware(dt: datetime):
    if timezone.is_aware(dt):
        return dt
    return timezone.make_aware(dt, timezone.get_current_timezone())


def _day_window(metric_date: date):
    tz = timezone.get_current_timezone()
    start = timezone.make_aware(datetime.combine(metric_date, time.min), tz)
    end = start + timedelta(days=1)
    return start, end


def _shift_window(shift: WorkCenterShift, metric_date: date):
    """Return the actual timestamp interval for a shift.

    Overnight shifts are supported: when end <= start the ending timestamp is
    on the following calendar day. ``metric_date`` always identifies the day on
    which the shift starts.
    """
    tz = timezone.get_current_timezone()
    start = timezone.make_aware(datetime.combine(metric_date, shift.start_time), tz)
    end_date = metric_date if shift.end_time > shift.start_time else metric_date + timedelta(days=1)
    end = timezone.make_aware(datetime.combine(end_date, shift.end_time), tz)
    return start, end


def _clipped_minutes(event: DowntimeEvent, start, end) -> Decimal:
    event_start = max(event.started_at, start)
    event_end = min(event.ended_at or timezone.now(), end)
    if event_end <= event_start:
        return D0
    return (Decimal(str((event_end - event_start).total_seconds())) / Decimal("60")).quantize(Q2)


def _metrics_for_window(*, machine: Machine, start, end, planned_minutes: Decimal) -> dict:
    downtime_events = list(
        DowntimeEvent.objects.filter(machine=machine, started_at__lt=end)
        .filter(Q(ended_at__isnull=True) | Q(ended_at__gt=start))
        .select_related("reason")
    )
    downtime_minutes = sum((_clipped_minutes(e, start, end) for e in downtime_events), D0)
    planned_minutes = max(D0, Decimal(planned_minutes or 0)).quantize(Q2)
    # Planned downtime can exceed the planned production window when bad source
    # data exists. Clamp to preserve physical meaning of availability.
    downtime_minutes = min(planned_minutes, downtime_minutes).quantize(Q2)
    run_minutes = max(D0, planned_minutes - downtime_minutes).quantize(Q2)

    totals = MachineProductionRecord.objects.filter(
        machine=machine,
        reported_at__gte=start,
        reported_at__lt=end,
    ).aggregate(good=Sum("report__good_quantity"), scrap=Sum("report__scrap_quantity"))
    good = Decimal(totals["good"] or 0)
    scrap = Decimal(totals["scrap"] or 0)
    total = good + scrap

    ideal_cycle_seconds = Decimal(machine.ideal_cycle_seconds or 0)
    ideal_total_minutes = (ideal_cycle_seconds * total / Decimal("60")) if ideal_cycle_seconds > 0 else D0
    ideal_good_minutes = (ideal_cycle_seconds * good / Decimal("60")) if ideal_cycle_seconds > 0 else D0

    availability = _ratio(run_minutes, planned_minutes)
    performance = _ratio(ideal_total_minutes, run_minutes)
    quality = _ratio(good, total)
    oee = (availability * performance * quality).quantize(Q4, rounding=ROUND_HALF_UP)

    availability_loss = downtime_minutes.quantize(Q2)
    performance_loss = max(D0, run_minutes - min(run_minutes, ideal_total_minutes)).quantize(Q2)
    # Equivalent ideal-cycle minutes lost because units became scrap.
    quality_loss = max(D0, ideal_total_minutes - ideal_good_minutes).quantize(Q2)

    unplanned = [e for e in downtime_events if e.reason.category == DowntimeReason.Category.UNPLANNED]
    failures = len(unplanned)
    unplanned_minutes = sum((_clipped_minutes(e, start, end) for e in unplanned), D0)
    mttr = (unplanned_minutes / failures).quantize(Q2) if failures else D0
    mtbf = (run_minutes / failures).quantize(Q2) if failures else run_minutes

    return {
        "planned_minutes": planned_minutes,
        "downtime_minutes": downtime_minutes,
        "run_minutes": run_minutes,
        "ideal_cycle_seconds": ideal_cycle_seconds,
        "good_quantity": good,
        "scrap_quantity": scrap,
        "availability": availability,
        "performance": performance,
        "quality": quality,
        "oee": oee,
        "availability_loss_minutes": availability_loss,
        "performance_loss_minutes": performance_loss,
        "quality_loss_minutes": quality_loss,
        "failures": failures,
        "mtbf_minutes": mtbf,
        "mttr_minutes": mttr,
        "calculated_at": timezone.now(),
    }


def resolve_oee_target(*, machine: Machine, metric_date: date) -> OEETarget | None:
    base = OEETarget.objects.filter(
        plant=machine.plant,
        is_active=True,
        effective_from__lte=metric_date,
    ).filter(Q(effective_to__isnull=True) | Q(effective_to__gte=metric_date))
    # Most specific target wins; within the same scope the newest effective
    # definition wins. This gives predictable historical comparisons.
    target = base.filter(machine=machine).order_by("-effective_from", "-pk").first()
    if target:
        return target
    target = base.filter(machine__isnull=True, work_center=machine.work_center).order_by("-effective_from", "-pk").first()
    if target:
        return target
    return base.filter(machine__isnull=True, work_center__isnull=True).order_by("-effective_from", "-pk").first()


@transaction.atomic
def calculate_machine_oee(*, machine: Machine, metric_date=None) -> OEEPeriodSnapshot:
    metric_date = metric_date or timezone.localdate()
    machine = Machine.objects.select_for_update().get(pk=machine.pk)
    start, end = _day_window(metric_date)
    metrics = _metrics_for_window(
        machine=machine,
        start=start,
        end=end,
        planned_minutes=Decimal(machine.planned_minutes_per_day or 0),
    )
    snapshot, _ = OEEPeriodSnapshot.objects.update_or_create(
        machine=machine,
        metric_date=metric_date,
        defaults=metrics,
    )
    return snapshot


@transaction.atomic
def calculate_machine_shift_oee(*, machine: Machine, shift: WorkCenterShift, metric_date=None) -> OEEShiftSnapshot:
    metric_date = metric_date or timezone.localdate()
    machine = Machine.objects.select_for_update().get(pk=machine.pk)
    if shift.work_center_id != machine.work_center_id:
        raise ValueError("O turno informado não pertence ao centro de trabalho da máquina.")
    if shift.weekday != metric_date.weekday():
        raise ValueError("O turno não está cadastrado para o dia da semana informado.")
    start, end = _shift_window(shift, metric_date)
    planned_minutes = Decimal(shift.capacity_hours or 0) * Decimal("60")
    metrics = _metrics_for_window(machine=machine, start=start, end=end, planned_minutes=planned_minutes)
    snapshot, _ = OEEShiftSnapshot.objects.update_or_create(
        machine=machine,
        shift=shift,
        metric_date=metric_date,
        defaults={"window_start": start, "window_end": end, **metrics},
    )
    return snapshot


def calculate_machine_shifts(*, machine: Machine, metric_date=None):
    metric_date = metric_date or timezone.localdate()
    shifts = WorkCenterShift.objects.filter(
        work_center=machine.work_center,
        weekday=metric_date.weekday(),
        is_active=True,
    ).order_by("start_time", "name")
    return [calculate_machine_shift_oee(machine=machine, shift=shift, metric_date=metric_date) for shift in shifts]


def calculate_plant_oee(*, plant, metric_date=None, include_shifts=False):
    metric_date = metric_date or timezone.localdate()
    snapshots = []
    for machine in Machine.objects.filter(plant=plant, is_active=True).order_by("work_center__code", "code"):
        snapshots.append(calculate_machine_oee(machine=machine, metric_date=metric_date))
        if include_shifts:
            calculate_machine_shifts(machine=machine, metric_date=metric_date)
    return snapshots


def downtime_pareto(*, plant, date_from: date, date_to: date, machine=None, limit=10):
    start, _ = _day_window(date_from)
    _, end = _day_window(date_to)
    qs = DowntimeEvent.objects.filter(
        machine__plant=plant,
        started_at__lt=end,
    ).filter(Q(ended_at__isnull=True) | Q(ended_at__gt=start)).select_related("reason", "machine")
    if machine is not None:
        qs = qs.filter(machine=machine)

    by_reason = defaultdict(lambda: {"minutes": D0, "events": 0, "reason": None})
    total_minutes = D0
    for event in qs:
        minutes = _clipped_minutes(event, start, end)
        bucket = by_reason[event.reason_id]
        bucket["reason"] = event.reason
        bucket["minutes"] += minutes
        bucket["events"] += 1
        total_minutes += minutes

    rows = sorted(by_reason.values(), key=lambda row: (row["minutes"], row["events"]), reverse=True)[:limit]
    cumulative = D0
    result = []
    for row in rows:
        share = _ratio(row["minutes"], total_minutes) if total_minutes else D0
        cumulative += share
        result.append({**row, "share": share, "share_pct": share * 100, "cumulative_share": min(D1, cumulative), "cumulative_pct": min(D1, cumulative) * 100})
    return {"rows": result, "total_minutes": total_minutes.quantize(Q2)}


def _aggregate_snapshots(snapshots):
    rows = list(snapshots)
    if not rows:
        return {
            "planned_minutes": D0,
            "run_minutes": D0,
            "downtime_minutes": D0,
            "good_quantity": D0,
            "scrap_quantity": D0,
            "availability": D0,
            "performance": D0,
            "quality": D0,
            "oee": D0,
            "availability_loss_minutes": D0,
            "performance_loss_minutes": D0,
            "quality_loss_minutes": D0,
        }
    planned = sum((Decimal(r.planned_minutes) for r in rows), D0)
    run = sum((Decimal(r.run_minutes) for r in rows), D0)
    downtime = sum((Decimal(r.downtime_minutes) for r in rows), D0)
    good = sum((Decimal(r.good_quantity) for r in rows), D0)
    scrap = sum((Decimal(r.scrap_quantity) for r in rows), D0)
    ideal = sum((Decimal(r.ideal_cycle_seconds) * (Decimal(r.good_quantity) + Decimal(r.scrap_quantity)) / Decimal("60") for r in rows), D0)
    total = good + scrap
    availability = _ratio(run, planned)
    performance = _ratio(ideal, run)
    quality = _ratio(good, total)
    return {
        "planned_minutes": planned,
        "run_minutes": run,
        "downtime_minutes": downtime,
        "good_quantity": good,
        "scrap_quantity": scrap,
        "availability": availability,
        "performance": performance,
        "quality": quality,
        "oee": (availability * performance * quality).quantize(Q4),
        "availability_loss_minutes": sum((Decimal(r.availability_loss_minutes) for r in rows), D0),
        "performance_loss_minutes": sum((Decimal(r.performance_loss_minutes) for r in rows), D0),
        "quality_loss_minutes": sum((Decimal(r.quality_loss_minutes) for r in rows), D0),
    }


def history_context(*, plant, date_from: date, date_to: date, machine=None) -> dict:
    qs = OEEPeriodSnapshot.objects.filter(
        machine__plant=plant,
        metric_date__gte=date_from,
        metric_date__lte=date_to,
    ).select_related("machine", "machine__work_center").order_by("metric_date", "machine__code")
    if machine is not None:
        qs = qs.filter(machine=machine)
    snapshots = list(qs)

    by_date = defaultdict(list)
    by_machine = defaultdict(list)
    for snapshot in snapshots:
        by_date[snapshot.metric_date].append(snapshot)
        by_machine[snapshot.machine_id].append(snapshot)

    trend = []
    current = date_from
    while current <= date_to:
        agg = _aggregate_snapshots(by_date.get(current, []))
        trend.append({"date": current, **agg, "oee_pct": agg["oee"] * 100, "availability_pct": agg["availability"] * 100, "performance_pct": agg["performance"] * 100, "quality_pct": agg["quality"] * 100})
        current += timedelta(days=1)

    machines_summary = []
    for machine_id, machine_rows in by_machine.items():
        machine_obj = machine_rows[0].machine
        agg = _aggregate_snapshots(machine_rows)
        target = resolve_oee_target(machine=machine_obj, metric_date=date_to)
        machines_summary.append({"machine": machine_obj, "target": target, **agg, "oee_pct": agg["oee"] * 100, "availability_pct": agg["availability"] * 100, "performance_pct": agg["performance"] * 100, "quality_pct": agg["quality"] * 100, "target_oee_pct": (target.oee_target * 100 if target else None)})
    machines_summary.sort(key=lambda row: row["oee"])

    shift_qs = OEEShiftSnapshot.objects.filter(
        machine__plant=plant,
        metric_date__gte=date_from,
        metric_date__lte=date_to,
    ).select_related("machine", "shift", "machine__work_center")
    if machine is not None:
        shift_qs = shift_qs.filter(machine=machine)
    shift_rows = list(shift_qs.order_by("-metric_date", "shift__start_time", "machine__code"))

    pareto = downtime_pareto(plant=plant, date_from=date_from, date_to=date_to, machine=machine)
    overall = _aggregate_snapshots(snapshots)
    overall = {**overall, "oee_pct": overall["oee"] * 100, "availability_pct": overall["availability"] * 100, "performance_pct": overall["performance"] * 100, "quality_pct": overall["quality"] * 100}
    return {
        "plant": plant,
        "date_from": date_from,
        "date_to": date_to,
        "selected_machine": machine,
        "overall": overall,
        "trend": trend,
        "machines_summary": machines_summary,
        "shift_rows": shift_rows,
        "pareto": pareto,
    }


def andon_context(*, plant, metric_date=None) -> dict:
    metric_date = metric_date or timezone.localdate()
    snapshots = {s.machine_id: s for s in calculate_plant_oee(plant=plant, metric_date=metric_date)}
    machines = list(
        Machine.objects.filter(plant=plant, is_active=True)
        .select_related("work_center", "current_operation", "current_operation__work_order", "current_operation__work_order__item")
        .order_by("work_center__code", "code")
    )
    rows = []
    for machine in machines:
        snapshot = snapshots.get(machine.pk)
        target = resolve_oee_target(machine=machine, metric_date=metric_date)
        rows.append({
            "machine": machine,
            "snapshot": snapshot,
            "target": target,
            "target_oee_pct": (target.oee_target * 100 if target else None),
            "target_met": bool(target and snapshot and snapshot.oee >= target.oee_target),
            "open_downtime": machine.downtime_events.filter(ended_at__isnull=True).select_related("reason").first(),
        })
    return {"plant": plant, "metric_date": metric_date, "rows": rows}
