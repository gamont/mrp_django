from __future__ import annotations

from datetime import date, timedelta
from decimal import Decimal, InvalidOperation

from django.contrib.auth import login, logout
from django.core.exceptions import ValidationError
from django.http import HttpRequest, HttpResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils import timezone
from django.views.decorators.http import require_POST

from apps.common.models import Plant
from apps.production.models import WorkOrderOperation

from .models import DowntimeReason, Machine, TerminalStation
from .oee import andon_context, history_context
from .services import (
    authenticate_operator,
    dispatch_next,
    end_downtime,
    machine_operation_action,
    report_and_complete,
    start_downtime,
    station_context,
)


def _decimal(raw, name):
    try:
        return Decimal(raw or "0")
    except (InvalidOperation, TypeError) as exc:
        raise ValidationError({name: "Valor numérico inválido."}) from exc


def _error_text(exc: Exception) -> str:
    if isinstance(exc, ValidationError):
        if hasattr(exc, "messages"):
            return " ".join(exc.messages)
    return str(exc)


def terminal_login(request: HttpRequest) -> HttpResponse:
    if request.user.is_authenticated:
        return redirect("shopfloor:stations")
    error = None
    if request.method == "POST":
        try:
            profile = authenticate_operator(badge_code=request.POST.get("badge_code"), pin=request.POST.get("pin"))
            login(request, profile.user, backend="django.contrib.auth.backends.ModelBackend")
            request.session["shopfloor_operator_profile_id"] = profile.pk
            return redirect(request.POST.get("next") or "shopfloor:stations")
        except Exception as exc:
            error = _error_text(exc)
    return render(request, "shopfloor/login.html", {"error": error})


@require_POST
def terminal_logout(request: HttpRequest) -> HttpResponse:
    request.session.pop("shopfloor_operator_profile_id", None)
    request.session.pop("shopfloor_station_id", None)
    logout(request)
    return redirect("shopfloor:login")


def _require_operator(request: HttpRequest):
    if not request.user.is_authenticated:
        return redirect(f"{reverse('shopfloor:login')}?next={request.path}")
    if not request.user.has_perm("shopfloor.use_shopfloor_terminal") and not request.user.is_superuser:
        return render(request, "shopfloor/error.html", {"message": "Usuário sem permissão para usar o terminal."}, status=403)
    return None


def stations(request: HttpRequest) -> HttpResponse:
    denied = _require_operator(request)
    if denied:
        return denied
    options = TerminalStation.objects.filter(is_active=True).select_related("plant", "work_center", "machine").order_by("plant__code", "code")
    return render(request, "shopfloor/stations.html", {"stations": options})


@require_POST
def select_station(request: HttpRequest) -> HttpResponse:
    denied = _require_operator(request)
    if denied:
        return denied
    station = get_object_or_404(TerminalStation, pk=request.POST.get("station_id"), is_active=True)
    request.session["shopfloor_station_id"] = station.pk
    return redirect("shopfloor:terminal", station_pk=station.pk)


def _terminal_response(request: HttpRequest, station: TerminalStation, *, feedback=None, status=200):
    context = {**station_context(station), "feedback": feedback}
    template = "shopfloor/partials/terminal_content.html" if request.headers.get("HX-Request") == "true" else "shopfloor/terminal.html"
    return render(request, template, context, status=status)


def terminal(request: HttpRequest, station_pk: int) -> HttpResponse:
    denied = _require_operator(request)
    if denied:
        return denied
    station = get_object_or_404(TerminalStation, pk=station_pk, is_active=True)
    request.session["shopfloor_station_id"] = station.pk
    return _terminal_response(request, station)


def _action(request, station_pk, callable_):
    denied = _require_operator(request)
    if denied:
        return denied
    station = get_object_or_404(TerminalStation.objects.select_related("machine"), pk=station_pk, is_active=True)
    try:
        message = callable_(station)
        return _terminal_response(request, station, feedback={"level": "success", "message": message})
    except Exception as exc:
        return _terminal_response(request, station, feedback={"level": "error", "message": _error_text(exc)}, status=422 if request.headers.get("HX-Request") == "true" else 200)


@require_POST
def dispatch_next_ui(request: HttpRequest, station_pk: int) -> HttpResponse:
    def run(station):
        op = dispatch_next(station=station, actor=request.user)
        return f"OP {op.work_order.number}, operação {op.sequence}, despachada."
    return _action(request, station_pk, run)


@require_POST
def operation_action_ui(request: HttpRequest, station_pk: int, operation_pk: int) -> HttpResponse:
    def run(station):
        if not station.machine_id:
            raise ValidationError("A estação precisa estar associada a uma máquina.")
        op = get_object_or_404(WorkOrderOperation, pk=operation_pk)
        updated = machine_operation_action(machine=station.machine, operation=op, action=request.POST.get("action"), actor=request.user)
        return f"Operação {updated.sequence}: {updated.get_status_display()}."
    return _action(request, station_pk, run)


@require_POST
def report_complete_ui(request: HttpRequest, station_pk: int, operation_pk: int) -> HttpResponse:
    def run(station):
        if not station.machine_id:
            raise ValidationError("A estação precisa estar associada a uma máquina.")
        op = get_object_or_404(WorkOrderOperation, pk=operation_pk)
        report = report_and_complete(
            machine=station.machine,
            operation=op,
            good_quantity=_decimal(request.POST.get("good_quantity"), "good_quantity"),
            scrap_quantity=_decimal(request.POST.get("scrap_quantity"), "scrap_quantity"),
            labor_hours=_decimal(request.POST.get("labor_hours"), "labor_hours"),
            machine_hours=_decimal(request.POST.get("machine_hours"), "machine_hours"),
            notes=request.POST.get("notes", ""),
            actor=request.user,
        )
        return f"Apontamento #{report.pk} registrado e operação concluída."
    return _action(request, station_pk, run)


@require_POST
def start_downtime_ui(request: HttpRequest, station_pk: int) -> HttpResponse:
    def run(station):
        if not station.machine_id:
            raise ValidationError("A estação precisa estar associada a uma máquina.")
        reason = get_object_or_404(DowntimeReason, pk=request.POST.get("reason"), plant=station.plant, is_active=True)
        event = start_downtime(machine=station.machine, reason=reason, notes=request.POST.get("notes", ""), actor=request.user)
        return f"Parada #{event.pk} iniciada: {reason.description}."
    return _action(request, station_pk, run)


@require_POST
def end_downtime_ui(request: HttpRequest, station_pk: int) -> HttpResponse:
    def run(station):
        if not station.machine_id:
            raise ValidationError("A estação precisa estar associada a uma máquina.")
        event = end_downtime(machine=station.machine, actor=request.user)
        return f"Parada #{event.pk} encerrada ({event.duration_seconds // 60} min)."
    return _action(request, station_pk, run)


def andon(request: HttpRequest) -> HttpResponse:
    denied = _require_operator(request)
    if denied:
        return denied
    plant_id = request.GET.get("plant") or request.session.get("shopfloor_andon_plant_id")
    plant = None
    if plant_id:
        plant = Plant.objects.filter(pk=plant_id).first()
    if plant is None:
        station_id = request.session.get("shopfloor_station_id")
        if station_id:
            station = TerminalStation.objects.filter(pk=station_id).select_related("plant").first()
            plant = station.plant if station else None
    if plant is None:
        plant = Plant.objects.order_by("code").first()
    if plant is None:
        return render(request, "shopfloor/error.html", {"message": "Nenhuma planta cadastrada."}, status=404)
    request.session["shopfloor_andon_plant_id"] = plant.pk
    context = andon_context(plant=plant)
    context["plants"] = Plant.objects.order_by("code")
    template = "shopfloor/partials/andon_content.html" if request.headers.get("HX-Request") == "true" else "shopfloor/andon.html"
    return render(request, template, context)


def _parse_date(raw, fallback):
    if not raw:
        return fallback
    try:
        return date.fromisoformat(raw)
    except ValueError:
        return fallback


def oee_history(request: HttpRequest) -> HttpResponse:
    denied = _require_operator(request)
    if denied:
        return denied
    plant_id = request.GET.get("plant") or request.session.get("shopfloor_andon_plant_id")
    plant = Plant.objects.filter(pk=plant_id).first() if plant_id else Plant.objects.order_by("code").first()
    if plant is None:
        return render(request, "shopfloor/error.html", {"message": "Nenhuma planta cadastrada."}, status=404)
    request.session["shopfloor_andon_plant_id"] = plant.pk

    today = timezone.localdate()
    date_to = _parse_date(request.GET.get("to"), today)
    date_from = _parse_date(request.GET.get("from"), date_to - timedelta(days=13))
    if date_from > date_to:
        date_from, date_to = date_to, date_from
    # Protect the online dashboard from accidentally requesting an unbounded range.
    if (date_to - date_from).days > 366:
        date_from = date_to - timedelta(days=366)

    machine = None
    machine_id = request.GET.get("machine")
    if machine_id:
        machine = Machine.objects.filter(pk=machine_id, plant=plant, is_active=True).first()

    context = history_context(plant=plant, date_from=date_from, date_to=date_to, machine=machine)
    context["plants"] = Plant.objects.order_by("code")
    context["machines"] = Machine.objects.filter(plant=plant, is_active=True).select_related("work_center").order_by("work_center__code", "code")
    template = "shopfloor/partials/oee_history_content.html" if request.headers.get("HX-Request") == "true" else "shopfloor/oee_history.html"
    return render(request, template, context)
