from __future__ import annotations

from decimal import Decimal, InvalidOperation

from django.contrib.auth.decorators import login_required, permission_required
from django.core.exceptions import ValidationError
from django.http import HttpRequest, HttpResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.views.decorators.http import require_POST

from apps.common.models import Plant
from apps.inventory.models import Location

from .models import AssetMeterReading, FailureEvent, MaintenanceAsset, MaintenancePart, MaintenancePlan, MaintenanceWorkOrder
from .services import complete_work_order, generate_preventive_orders, issue_maintenance_part, report_failure, start_work_order


def _error_text(exc):
    if isinstance(exc, ValidationError) and hasattr(exc, "messages"):
        return " ".join(exc.messages)
    return str(exc)


def _decimal(raw, field):
    try:
        return Decimal(str(raw or "0"))
    except (InvalidOperation, TypeError) as exc:
        raise ValidationError({field: "Valor numérico inválido."}) from exc


def _selected_plant(request):
    plant_id = request.GET.get("plant") or request.session.get("maintenance_plant_id")
    plant = Plant.objects.filter(pk=plant_id).first() if plant_id else Plant.objects.order_by("code").first()
    if plant:
        request.session["maintenance_plant_id"] = plant.pk
    return plant


def _dashboard_context(plant, feedback=None):
    today = timezone.localdate()
    orders = MaintenanceWorkOrder.objects.filter(plant=plant).select_related("asset", "assigned_to", "plan")
    due_plans = [p for p in MaintenancePlan.objects.filter(asset__plant=plant, asset__is_active=True, is_active=True).select_related("asset") if (p.next_due_date and p.next_due_date <= today)]
    assets = MaintenanceAsset.objects.filter(plant=plant, is_active=True).select_related("machine", "work_center")
    return {
        "plant": plant,
        "plants": Plant.objects.order_by("code"),
        "feedback": feedback,
        "assets": assets,
        "open_orders": orders.exclude(status__in=[MaintenanceWorkOrder.Status.COMPLETED, MaintenanceWorkOrder.Status.CANCELLED])[:30],
        "overdue_orders": orders.filter(scheduled_start__date__lt=today).exclude(status__in=[MaintenanceWorkOrder.Status.COMPLETED, MaintenanceWorkOrder.Status.CANCELLED]).count(),
        "in_progress": orders.filter(status=MaintenanceWorkOrder.Status.IN_PROGRESS).count(),
        "due_plans": due_plans[:20],
        "failures_open": FailureEvent.objects.filter(asset__plant=plant, resolved_at__isnull=True).count(),
    }


@login_required
def dashboard(request: HttpRequest) -> HttpResponse:
    plant = _selected_plant(request)
    if plant is None:
        return render(request, "maintenance/error.html", {"message": "Nenhuma planta cadastrada."}, status=404)
    template = "maintenance/partials/dashboard_content.html" if request.headers.get("HX-Request") == "true" else "maintenance/dashboard.html"
    return render(request, template, _dashboard_context(plant))


@login_required
def work_order_detail(request: HttpRequest, pk: int) -> HttpResponse:
    wo = get_object_or_404(MaintenanceWorkOrder.objects.select_related("plant", "asset", "asset__machine", "plan", "assigned_to", "downtime_event"), pk=pk)
    locations = Location.objects.filter(warehouse__plant=wo.plant, is_active=True).select_related("warehouse")
    context = {
        "work_order": wo,
        "parts": wo.parts.select_related("item", "source_location"),
        "failures": wo.failure_events.order_by("-occurred_at"),
        "locations": locations,
        "readings": wo.asset.meter_readings.order_by("-reading_at")[:10],
    }
    template = "maintenance/partials/work_order_detail_content.html" if request.headers.get("HX-Request") == "true" else "maintenance/work_order_detail.html"
    return render(request, template, context)


def _detail_response(request, wo, feedback=None, status=200):
    locations = Location.objects.filter(warehouse__plant=wo.plant, is_active=True).select_related("warehouse")
    context = {
        "work_order": wo,
        "parts": wo.parts.select_related("item", "source_location"),
        "failures": wo.failure_events.order_by("-occurred_at"),
        "locations": locations,
        "readings": wo.asset.meter_readings.order_by("-reading_at")[:10],
        "feedback": feedback,
    }
    template = "maintenance/partials/work_order_detail_content.html" if request.headers.get("HX-Request") == "true" else "maintenance/work_order_detail.html"
    return render(request, template, context, status=status)


@require_POST
@login_required
@permission_required("maintenance.change_maintenanceworkorder", raise_exception=True)
def generate_orders_ui(request):
    plant = get_object_or_404(Plant, pk=request.POST.get("plant"))
    created = generate_preventive_orders(plant=plant, actor=request.user)
    return render(request, "maintenance/partials/dashboard_content.html", _dashboard_context(plant, {"level": "success", "message": f"{len(created)} ordem(ns) preventiva(s) gerada(s)."}))


@require_POST
@login_required
@permission_required("maintenance.change_maintenanceworkorder", raise_exception=True)
def start_work_order_ui(request, pk):
    wo = get_object_or_404(MaintenanceWorkOrder, pk=pk)
    try:
        wo = start_work_order(work_order=wo, actor=request.user)
        return _detail_response(request, wo, {"level": "success", "message": "Ordem de manutenção iniciada."})
    except Exception as exc:
        wo.refresh_from_db()
        return _detail_response(request, wo, {"level": "error", "message": _error_text(exc)}, status=422 if request.headers.get("HX-Request") == "true" else 200)


@require_POST
@login_required
@permission_required("maintenance.change_maintenanceworkorder", raise_exception=True)
def complete_work_order_ui(request, pk):
    wo = get_object_or_404(MaintenanceWorkOrder, pk=pk)
    meter_raw = request.POST.get("meter_value")
    meter = _decimal(meter_raw, "meter_value") if meter_raw not in (None, "") else None
    try:
        wo = complete_work_order(work_order=wo, completion_notes=request.POST.get("completion_notes", ""), meter_value=meter, actor=request.user)
        return _detail_response(request, wo, {"level": "success", "message": "Ordem de manutenção concluída."})
    except Exception as exc:
        wo.refresh_from_db()
        return _detail_response(request, wo, {"level": "error", "message": _error_text(exc)}, status=422 if request.headers.get("HX-Request") == "true" else 200)


@require_POST
@login_required
@permission_required("maintenance.change_maintenancepart", raise_exception=True)
def issue_part_ui(request, pk, part_pk):
    wo = get_object_or_404(MaintenanceWorkOrder, pk=pk)
    part = get_object_or_404(MaintenancePart, pk=part_pk, work_order=wo)
    location = get_object_or_404(Location, pk=request.POST.get("location"), warehouse__plant=wo.plant)
    try:
        issue_maintenance_part(part=part, location=location, quantity=_decimal(request.POST.get("quantity"), "quantity"), actor=request.user, idempotency_key=request.POST.get("idempotency_key") or None)
        wo.refresh_from_db()
        return _detail_response(request, wo, {"level": "success", "message": f"Peça {part.item.code} baixada para a manutenção."})
    except Exception as exc:
        return _detail_response(request, wo, {"level": "error", "message": _error_text(exc)}, status=422 if request.headers.get("HX-Request") == "true" else 200)


@require_POST
@login_required
@permission_required("maintenance.add_assetmeterreading", raise_exception=True)
def meter_reading_ui(request, pk):
    asset = get_object_or_404(MaintenanceAsset, pk=pk)
    reading = AssetMeterReading.objects.create(asset=asset, reading_at=timezone.now(), meter_value=_decimal(request.POST.get("meter_value"), "meter_value"), recorded_by=request.user, source="MANUAL", notes=request.POST.get("notes", ""))
    next_url = request.POST.get("next")
    if next_url:
        return redirect(next_url)
    return redirect("maintenance:dashboard")


@require_POST
@login_required
@permission_required("maintenance.add_failureevent", raise_exception=True)
def report_failure_ui(request, pk):
    asset = get_object_or_404(MaintenanceAsset, pk=pk)
    failure, wo = report_failure(asset=asset, symptom=request.POST.get("symptom", ""), failure_class=request.POST.get("failure_class", FailureEvent.FailureClass.OTHER), actor=request.user)
    return redirect("maintenance:work-order-detail", pk=wo.pk)


@login_required
def weekly_planner(request: HttpRequest) -> HttpResponse:
    from datetime import datetime, timedelta
    from .services import weekly_maintenance_plan
    plant = _selected_plant(request)
    if plant is None:
        return render(request, "maintenance/error.html", {"message": "Nenhuma planta cadastrada."}, status=404)
    raw = request.GET.get("week")
    try:
        day = datetime.strptime(raw, "%Y-%m-%d").date() if raw else timezone.localdate()
    except ValueError:
        day = timezone.localdate()
    week_start = day - timedelta(days=day.weekday())
    ctx = weekly_maintenance_plan(plant=plant, week_start=week_start)
    ctx.update({"plant": plant, "plants": Plant.objects.order_by("code")})
    return render(request, "maintenance/weekly_planner.html", ctx)


@login_required
def reliability_dashboard(request: HttpRequest) -> HttpResponse:
    from datetime import datetime, timedelta
    from .services import failure_pareto
    plant = _selected_plant(request)
    if plant is None:
        return render(request, "maintenance/error.html", {"message": "Nenhuma planta cadastrada."}, status=404)
    today = timezone.localdate()
    try:
        start = datetime.strptime(request.GET.get("from", ""), "%Y-%m-%d").date()
    except ValueError:
        start = today - timedelta(days=90)
    try:
        end = datetime.strptime(request.GET.get("to", ""), "%Y-%m-%d").date()
    except ValueError:
        end = today
    failures = FailureEvent.objects.filter(asset__plant=plant, occurred_at__date__gte=start, occurred_at__date__lte=end)
    resolved = failures.exclude(resolved_at__isnull=True)
    durations = [(f.resolved_at - f.occurred_at).total_seconds()/3600 for f in resolved if f.resolved_at]
    ctx = {"plant": plant, "plants": Plant.objects.order_by("code"), "start": start, "end": end, "pareto": failure_pareto(plant=plant, start_date=start, end_date=end), "failure_count": failures.count(), "open_failures": failures.filter(resolved_at__isnull=True).count(), "avg_repair_hours": round(sum(durations)/len(durations), 2) if durations else 0}
    return render(request, "maintenance/reliability.html", ctx)


@require_POST
@login_required
@permission_required("maintenance.change_maintenanceworkorder", raise_exception=True)
def release_work_order_ui(request, pk):
    from .services import release_work_order
    wo = get_object_or_404(MaintenanceWorkOrder, pk=pk)
    try:
        wo = release_work_order(work_order=wo, actor=request.user, require_parts=request.POST.get("require_parts", "1") != "0")
        if wo.status == MaintenanceWorkOrder.Status.WAITING_PARTS:
            return _detail_response(request, wo, {"level":"warning", "message":"OM aguardando peças; liberação bloqueada."})
        return _detail_response(request, wo, {"level":"success", "message":"Ordem liberada; disponibilidade de peças validada."})
    except Exception as exc:
        wo.refresh_from_db()
        return _detail_response(request, wo, {"level":"error", "message":_error_text(exc)}, status=422 if request.headers.get("HX-Request") == "true" else 200)


@require_POST
@login_required
@permission_required("maintenance.add_conditionreading", raise_exception=True)
def condition_reading_ui(request, pk):
    from .models import ConditionReading
    from .services import evaluate_condition_reading
    asset = get_object_or_404(MaintenanceAsset, pk=pk)
    reading = ConditionReading.objects.create(asset=asset, metric=request.POST.get("metric", ConditionReading.Metric.VIBRATION), metric_name=request.POST.get("metric_name", ""), value=_decimal(request.POST.get("value"), "value"), unit=request.POST.get("unit", ""), source="MANUAL", recorded_by=request.user)
    orders = evaluate_condition_reading(reading=reading, actor=request.user)
    if orders:
        return redirect("maintenance:work-order-detail", pk=orders[0].pk)
    return redirect("maintenance:dashboard")


@login_required
def kanban_board(request: HttpRequest) -> HttpResponse:
    from .services import maintenance_kanban
    plant = _selected_plant(request)
    if plant is None:
        return render(request, "maintenance/error.html", {"message": "Nenhuma planta cadastrada."}, status=404)
    context = {"plant": plant, "plants": Plant.objects.order_by("code"), "columns": maintenance_kanban(plant=plant)}
    return render(request, "maintenance/kanban.html", context)


@login_required
def advanced_planner(request: HttpRequest) -> HttpResponse:
    from datetime import datetime, timedelta
    from .services import weekly_maintenance_plan, maintenance_kanban

    plant = _selected_plant(request)
    if plant is None:
        return render(
            request,
            "maintenance/error.html",
            {"message": "Nenhuma planta cadastrada."},
            status=404,
        )

    raw = request.GET.get("week")
    try:
        day = (
            datetime.strptime(raw, "%Y-%m-%d").date()
            if raw
            else timezone.localdate()
        )
    except ValueError:
        day = timezone.localdate()

    week_start = day - timedelta(days=day.weekday())
    ctx = weekly_maintenance_plan(
        plant=plant,
        week_start=week_start,
    )

    days = [week_start + timedelta(days=i) for i in range(7)]

    orders_by_day = {day: [] for day in days}

    for wo in ctx["orders"]:
        if wo.scheduled_start:
            scheduled_day = timezone.localtime(
                wo.scheduled_start
            ).date()
            if scheduled_day in orders_by_day:
                orders_by_day[scheduled_day].append(wo)

    calendar_days = [
        {
            "date": day,
            "orders": orders_by_day[day],
        }
        for day in days
    ]

    ctx.update({
        "plant": plant,
        "plants": Plant.objects.order_by("code"),
        "backlog": maintenance_kanban(plant=plant),
        "calendar_days": calendar_days,
    })

    return render(
        request,
        "maintenance/advanced_planner.html",
        ctx,
    )

@require_POST
@login_required
@permission_required("maintenance.change_maintenanceworkorder", raise_exception=True)
def schedule_work_order_ui(request, pk):
    from datetime import datetime, timedelta
    from .services import schedule_maintenance_work_order
    wo = get_object_or_404(MaintenanceWorkOrder, pk=pk)
    try:
        start_raw = request.POST.get("start")
        end_raw = request.POST.get("end")
        day_raw = request.POST.get("day")
        if day_raw and not start_raw:
            start_raw = f"{day_raw}T08:00"
            duration = wo.plan.planned_duration_hours if wo.plan_id else Decimal("2")
            start = timezone.make_aware(datetime.fromisoformat(start_raw))
            end = start + timedelta(hours=float(duration or 2))
        else:
            start = timezone.make_aware(datetime.fromisoformat(start_raw)) if start_raw else None
            end = timezone.make_aware(datetime.fromisoformat(end_raw)) if end_raw else None
        if not start or not end:
            raise ValidationError("Informe início e fim da programação.")
        wo, conflicts = schedule_maintenance_work_order(work_order=wo, start=start, end=end, actor=request.user, force=request.POST.get("force") == "1")
        if request.headers.get("HX-Request") == "true":
            return HttpResponse(f'<div class="m-alert success">{wo.number} programada. Conflitos: {len(conflicts)}</div>')
        return redirect("maintenance:advanced-planner")
    except Exception as exc:
        if request.headers.get("HX-Request") == "true":
            return HttpResponse(f'<div class="m-alert error">{_error_text(exc)}</div>', status=422)
        return redirect("maintenance:advanced-planner")


@require_POST
@login_required
@permission_required("maintenance.change_maintenanceworkorder", raise_exception=True)
def auto_assign_ui(request, pk):
    from .services import auto_assign_technicians
    wo = get_object_or_404(MaintenanceWorkOrder, pk=pk)
    try:
        assignments = auto_assign_technicians(work_order=wo, actor=request.user, replace=request.POST.get("replace") == "1")
        wo.refresh_from_db()
        return _detail_response(request, wo, {"level": "success", "message": f"{len(assignments)} técnico(s) alocado(s) automaticamente."})
    except Exception as exc:
        return _detail_response(request, wo, {"level": "error", "message": _error_text(exc)}, status=422 if request.headers.get("HX-Request") == "true" else 200)


@require_POST
@login_required
@permission_required("maintenance.change_maintenanceworkorder", raise_exception=True)
def reserve_parts_ui(request, pk):
    from .services import reserve_maintenance_parts
    wo = get_object_or_404(MaintenanceWorkOrder, pk=pk)
    try:
        reservations = reserve_maintenance_parts(work_order=wo, actor=request.user)
        wo.refresh_from_db()
        return _detail_response(request, wo, {"level": "success", "message": f"{len(reservations)} reserva(s) de peça criada(s)."})
    except Exception as exc:
        return _detail_response(request, wo, {"level": "error", "message": _error_text(exc)}, status=422 if request.headers.get("HX-Request") == "true" else 200)
