from __future__ import annotations

from datetime import datetime, time, timedelta
from decimal import Decimal

from django.utils import timezone

from apps.common.models import ShopCalendarDay
from apps.masterdata.models import WorkCenterShift
from .models import IndustrialCalendarWindow, IndustrialShiftBreak

ZERO = Decimal("0")
ONE = Decimal("1")


def _aware(day, at):
    dt = datetime.combine(day, at)
    return timezone.make_aware(dt) if timezone.is_naive(dt) else dt


def _subtract_interval(windows, cut_start, cut_end):
    out = []
    for start, end, factor, kind in windows:
        if cut_end <= start or cut_start >= end:
            out.append((start, end, factor, kind))
            continue
        if cut_start > start:
            out.append((start, min(cut_start, end), factor, kind))
        if cut_end < end:
            out.append((max(cut_end, start), end, factor, kind))
    return [w for w in out if w[1] > w[0]]


def _merge_adjacent(windows):
    rows = sorted(windows, key=lambda x: x[0])
    out = []
    for row in rows:
        if out and out[-1][1] == row[0] and out[-1][2:] == row[2:]:
            out[-1] = (out[-1][0], row[1], row[2], row[3])
        else:
            out.append(row)
    return out


def resource_windows(*, scenario, work_center, machine=None, start_date=None, end_date=None):
    """Retorna janelas (start,end,rate,type) já descontando feriados, pausas e closures.

    `rate` converte hora de relógio em hora efetiva de capacidade.
    """
    start_date = start_date or scenario.horizon_start
    end_date = end_date or scenario.horizon_end
    cal = {x.date: x for x in ShopCalendarDay.objects.filter(plant=scenario.plant, date__range=(start_date, end_date))}
    exceptions = list(IndustrialCalendarWindow.objects.filter(
        plant=scenario.plant, date__range=(start_date, end_date)
    ).select_related("work_center", "machine"))
    shifts = list(WorkCenterShift.objects.filter(work_center=work_center, is_active=True).prefetch_related("industrial_breaks"))
    by_weekday = {}
    for shift in shifts:
        by_weekday.setdefault(shift.weekday, []).append(shift)

    windows = []
    day = start_date
    while day <= end_date:
        calday = cal.get(day)
        working = calday.is_working_day if calday else (day.weekday() < 5 or bool(by_weekday.get(day.weekday())))
        day_factor = Decimal(calday.capacity_factor if calday else ONE)
        day_windows = []
        if working:
            day_shifts = by_weekday.get(day.weekday(), [])
            if day_shifts:
                for shift in day_shifts:
                    start = _aware(day, shift.start_time)
                    # cross-midnight shift
                    end_day = day + timedelta(days=1) if shift.end_time <= shift.start_time else day
                    end = _aware(end_day, shift.end_time)
                    pieces = [(start, end, ONE, "REGULAR")]
                    for brk in shift.industrial_breaks.all():
                        if not brk.is_active:
                            continue
                        bs = _aware(day, brk.start_time)
                        be_day = day + timedelta(days=1) if brk.end_time <= brk.start_time else day
                        be = _aware(be_day, brk.end_time)
                        pieces = _subtract_interval(pieces, bs, be)
                    net_elapsed = sum((Decimal(str((pe - ps).total_seconds() / 3600)) for ps, pe, _, _ in pieces), ZERO)
                    declared = Decimal(shift.capacity_hours) * (Decimal(shift.efficiency_percent) / Decimal("100")) * day_factor
                    rate = (declared / net_elapsed) if net_elapsed > 0 else ZERO
                    day_windows.extend((ps, pe, rate, kind) for ps, pe, _, kind in pieces if rate > 0)
            elif day.weekday() < 5:
                # compatibilidade: centro sem turnos usa capacidade diária a partir de 08:00.
                hours = float(Decimal(work_center.capacity_hours_per_day or 0))
                if hours > 0:
                    start = _aware(day, time(8, 0))
                    day_windows.append((start, start + timedelta(hours=hours), Decimal(work_center.efficiency_percent or 100) / Decimal("100") * day_factor, "REGULAR"))

        relevant = [e for e in exceptions if e.date == day and (e.work_center_id in (None, work_center.id)) and (e.machine_id in (None, getattr(machine, "id", None)))]
        # fechamento remove capacidade existente
        for exc in [e for e in relevant if e.window_type == IndustrialCalendarWindow.WindowType.CLOSURE]:
            day_windows = _subtract_interval(day_windows, _aware(day, exc.start_time), _aware(day, exc.end_time))
        # hora extra adiciona capacidade mesmo em feriado/fim de semana
        for exc in [e for e in relevant if e.window_type == IndustrialCalendarWindow.WindowType.OVERTIME]:
            day_windows.append((_aware(day, exc.start_time), _aware(day, exc.end_time), Decimal(exc.capacity_factor), "OVERTIME"))
        windows.extend(day_windows)
        day += timedelta(days=1)
    return _merge_adjacent(windows)


def _subtract_busy(window, busy_intervals):
    pieces = [window]
    for bs, be in busy_intervals:
        pieces = _subtract_interval(pieces, bs, be)
    return pieces


def schedule_forward(*, windows, busy_intervals, required_hours, earliest):
    remaining = Decimal(required_hours)
    segments = []
    for window in windows:
        ws, we, rate, kind = window
        if we <= earliest:
            continue
        ws = max(ws, earliest)
        for start, end, rate, kind in _subtract_busy((ws, we, rate, kind), busy_intervals):
            if remaining <= 0:
                break
            elapsed_hours = Decimal(str((end - start).total_seconds() / 3600))
            effective = elapsed_hours * rate
            if effective <= 0:
                continue
            if effective >= remaining:
                used_elapsed = remaining / rate
                end = start + timedelta(hours=float(used_elapsed))
                effective = remaining
            segments.append((start, end, effective, rate, kind))
            remaining -= effective
        if remaining <= 0:
            break
    return segments if remaining <= Decimal("0.0001") else []


def schedule_backward(*, windows, busy_intervals, required_hours, latest):
    remaining = Decimal(required_hours)
    segments = []
    for window in sorted(windows, key=lambda x: x[1], reverse=True):
        ws, we, rate, kind = window
        if ws >= latest:
            continue
        we = min(we, latest)
        free = _subtract_busy((ws, we, rate, kind), busy_intervals)
        for start, end, rate, kind in sorted(free, key=lambda x: x[1], reverse=True):
            if remaining <= 0:
                break
            elapsed_hours = Decimal(str((end - start).total_seconds() / 3600))
            effective = elapsed_hours * rate
            if effective <= 0:
                continue
            if effective >= remaining:
                used_elapsed = remaining / rate
                start = end - timedelta(hours=float(used_elapsed))
                effective = remaining
            segments.append((start, end, effective, rate, kind))
            remaining -= effective
        if remaining <= 0:
            break
    segments.sort(key=lambda x: x[0])
    return segments if remaining <= Decimal("0.0001") else []
