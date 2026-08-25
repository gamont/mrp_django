from __future__ import annotations

from decimal import Decimal, InvalidOperation
from uuid import uuid4

from django.contrib import messages
from django.contrib.auth.decorators import login_required, permission_required
from django.core.exceptions import ValidationError
from django.db import transaction
from django.http import HttpRequest, HttpResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_POST

from apps.common.models import Plant
from apps.costing.models import AccountingPeriod, ItemCost
from apps.costing.services.period_close import final_close_period
from apps.inventory.models import Location
from apps.planning.models import PlannedOrder
from apps.planning.services import convert_planned_order
from apps.masterdata.models import Item
from apps.production.models import WorkOrder, WorkOrderMaterial, WorkOrderOperation
from apps.production.services import (
    advance_work_order_operation,
    complete_work_order,
    issue_work_order_material,
    release_work_order,
    report_work_order_operation,
)
from apps.purchasing.models import PurchaseOrder, PurchaseOrderLine
from apps.purchasing.services import receive_purchase_order_line
from apps.quality.models import InspectionCharacteristic, InspectionOrder
from apps.quality.services import complete_inspection, record_result, start_inspection

from .detail_services import (
    inspection_detail_context,
    item_cost_detail_context,
    planned_order_detail_context,
    purchase_order_detail_context,
    work_order_detail_context,
)

from .services import (
    costing_dashboard,
    inventory_dashboard,
    planner_dashboard,
    production_dashboard,
    purchasing_dashboard,
    quality_dashboard,
    selected_plant,
)


def _render_dashboard(request: HttpRequest, template: str, service, *, feedback=None) -> HttpResponse:
    context = service(selected_plant(request))
    payload = {"plant": context.plant, **context.data}
    if feedback:
        payload["action_feedback"] = feedback
    if request.headers.get("HX-Request") == "true":
        return render(request, f"ui/partials/{template}_content.html", payload)
    return render(request, f"ui/{template}.html", payload)


def _feedback_from_exception(exc: Exception) -> str:
    if isinstance(exc, ValidationError):
        if hasattr(exc, "message_dict"):
            parts = []
            for key, values in exc.message_dict.items():
                if not isinstance(values, (list, tuple)):
                    values = [values]
                parts.append(f"{key}: {'; '.join(str(v) for v in values)}")
            return " | ".join(parts)
        if hasattr(exc, "messages"):
            return "; ".join(exc.messages)
    return str(exc)


def _finish_action(request, template, service, success_message, *, error=None):
    if request.headers.get("HX-Request") == "true":
        feedback = {
            "level": "error" if error else "success",
            "message": _feedback_from_exception(error) if error else success_message,
        }
        return _render_dashboard(request, template, service, feedback=feedback)
    if error:
        messages.error(request, _feedback_from_exception(error))
    else:
        messages.success(request, success_message)
    return redirect(f"ui:{template}")


def _decimal(value, field_name):
    try:
        return Decimal(str(value))
    except (InvalidOperation, TypeError, ValueError):
        raise ValidationError({field_name: "Informe um número válido."})


@login_required
def home(request: HttpRequest) -> HttpResponse:
    return _render_dashboard(request, "planner", planner_dashboard)


@login_required
def planner(request: HttpRequest) -> HttpResponse:
    return _render_dashboard(request, "planner", planner_dashboard)


@login_required
def production(request: HttpRequest) -> HttpResponse:
    return _render_dashboard(request, "production", production_dashboard)


@login_required
def purchasing(request: HttpRequest) -> HttpResponse:
    return _render_dashboard(request, "purchasing", purchasing_dashboard)


@login_required
def inventory(request: HttpRequest) -> HttpResponse:
    return _render_dashboard(request, "inventory", inventory_dashboard)


@login_required
def quality(request: HttpRequest) -> HttpResponse:
    return _render_dashboard(request, "quality", quality_dashboard)


@login_required
def costing(request: HttpRequest) -> HttpResponse:
    return _render_dashboard(request, "costing", costing_dashboard)


@login_required
@require_POST
def select_plant(request: HttpRequest) -> HttpResponse:
    plant = Plant.objects.filter(pk=request.POST.get("plant_id"), is_active=True).first()
    if plant:
        request.session["ui_plant_id"] = plant.pk
        messages.success(request, f"Planta alterada para {plant.code}.")
    target = request.POST.get("next") or request.META.get("HTTP_REFERER") or "ui:home"
    if request.headers.get("HX-Request") == "true":
        response = HttpResponse(status=204)
        response["HX-Refresh"] = "true"
        return response
    return redirect(target)


@login_required
@permission_required("planning.change_plannedorder", raise_exception=True)
@require_POST
def firm_planned_order(request: HttpRequest, pk: int) -> HttpResponse:
    try:
        with transaction.atomic():
            order = PlannedOrder.objects.select_for_update().select_related("planning_run").get(pk=pk)
            plant = selected_plant(request)
            if plant and order.planning_run.plant_id != plant.pk:
                raise ValidationError("A ordem não pertence à planta selecionada.")
            if order.status != PlannedOrder.Status.PLANNED:
                raise ValidationError("Somente ordens planejadas podem ser firmadas.")
            order.status = PlannedOrder.Status.FIRM
            order.save(update_fields=["status", "updated_at"])
        return _finish_action(request, "planner", planner_dashboard, f"Ordem {order.item.code} firmada.")
    except Exception as exc:
        return _finish_action(request, "planner", planner_dashboard, "", error=exc)


@login_required
@permission_required("planning.change_plannedorder", raise_exception=True)
@require_POST
def convert_planned_order_ui(request: HttpRequest, pk: int) -> HttpResponse:
    try:
        order = get_object_or_404(PlannedOrder.objects.select_related("planning_run", "item"), pk=pk)
        plant = selected_plant(request)
        if plant and order.planning_run.plant_id != plant.pk:
            raise ValidationError("A ordem não pertence à planta selecionada.")
        document = convert_planned_order(order)
        return _finish_action(request, "planner", planner_dashboard, f"Ordem convertida em {document}.")
    except Exception as exc:
        return _finish_action(request, "planner", planner_dashboard, "", error=exc)


@login_required
@permission_required("production.change_workorder", raise_exception=True)
@require_POST
def release_work_order_ui(request: HttpRequest, pk: int) -> HttpResponse:
    try:
        order = get_object_or_404(WorkOrder.objects.select_related("plant"), pk=pk)
        plant = selected_plant(request)
        if plant and order.plant_id != plant.pk:
            raise ValidationError("A OP não pertence à planta selecionada.")
        release_work_order(order)
        return _finish_action(request, "production", production_dashboard, f"OP {order.number} liberada.")
    except Exception as exc:
        return _finish_action(request, "production", production_dashboard, "", error=exc)


@login_required
@permission_required("production.change_workorder", raise_exception=True)
@require_POST
def complete_work_order_ui(request: HttpRequest, pk: int) -> HttpResponse:
    try:
        order = get_object_or_404(WorkOrder.objects.select_related("plant"), pk=pk)
        plant = selected_plant(request)
        if plant and order.plant_id != plant.pk:
            raise ValidationError("A OP não pertence à planta selecionada.")
        location = get_object_or_404(Location.objects.select_related("warehouse"), pk=request.POST.get("destination_location"))
        completion, created = complete_work_order(
            work_order=order,
            good_quantity=_decimal(request.POST.get("good_quantity"), "good_quantity"),
            scrap_quantity=_decimal(request.POST.get("scrap_quantity", "0"), "scrap_quantity"),
            destination_location=location,
            idempotency_key=request.POST.get("idempotency_key") or f"ui-wo-{pk}-{uuid4()}",
            backflush=request.POST.get("backflush") == "on",
            notes=request.POST.get("notes", ""),
            actor=request.user,
        )
        verb = "registrado" if created else "reutilizado"
        return _finish_action(request, "production", production_dashboard, f"Apontamento {verb} para {order.number}: {completion.good_quantity} boas.")
    except Exception as exc:
        return _finish_action(request, "production", production_dashboard, "", error=exc)


@login_required
@permission_required("purchasing.change_purchaseorderline", raise_exception=True)
@require_POST
def receive_purchase_line_ui(request: HttpRequest, pk: int) -> HttpResponse:
    try:
        line = get_object_or_404(PurchaseOrderLine.objects.select_related("purchase_order__plant", "item"), pk=pk)
        plant = selected_plant(request)
        if plant and line.purchase_order.plant_id != plant.pk:
            raise ValidationError("A linha não pertence à planta selecionada.")
        location = get_object_or_404(Location.objects.select_related("warehouse"), pk=request.POST.get("destination_location"))
        receipt, created = receive_purchase_order_line(
            line=line,
            quantity=_decimal(request.POST.get("quantity"), "quantity"),
            destination_location=location,
            receipt_number=request.POST.get("receipt_number") or f"REC-{line.pk}-{uuid4().hex[:8]}",
            idempotency_key=request.POST.get("idempotency_key") or f"ui-po-{pk}-{uuid4()}",
            lot_number=request.POST.get("lot_number", ""),
            notes=request.POST.get("notes", ""),
            actor=request.user,
        )
        verb = "registrado" if created else "reutilizado"
        return _finish_action(request, "purchasing", purchasing_dashboard, f"Recebimento {verb}: {receipt.quantity} de {line.item.code}.")
    except Exception as exc:
        return _finish_action(request, "purchasing", purchasing_dashboard, "", error=exc)


@login_required
@permission_required("quality.change_inspectionorder", raise_exception=True)
@require_POST
def start_inspection_ui(request: HttpRequest, pk: int) -> HttpResponse:
    try:
        order = get_object_or_404(InspectionOrder.objects.select_related("plant", "item"), pk=pk)
        plant = selected_plant(request)
        if plant and order.plant_id != plant.pk:
            raise ValidationError("A inspeção não pertence à planta selecionada.")
        start_inspection(order=order, user=request.user)
        return _finish_action(request, "quality", quality_dashboard, f"Inspeção de {order.item.code} iniciada.")
    except Exception as exc:
        return _finish_action(request, "quality", quality_dashboard, "", error=exc)


@login_required
@permission_required("quality.change_inspectionorder", raise_exception=True)
@require_POST
def complete_inspection_ui(request: HttpRequest, pk: int) -> HttpResponse:
    try:
        order = get_object_or_404(InspectionOrder.objects.select_related("plant", "item"), pk=pk)
        plant = selected_plant(request)
        if plant and order.plant_id != plant.pk:
            raise ValidationError("A inspeção não pertence à planta selecionada.")
        complete_inspection(
            order=order,
            quantity_approved=_decimal(request.POST.get("quantity_approved"), "quantity_approved"),
            quantity_rejected=_decimal(request.POST.get("quantity_rejected", "0"), "quantity_rejected"),
            notes=request.POST.get("notes", ""),
            user=request.user,
        )
        return _finish_action(request, "quality", quality_dashboard, f"Inspeção de {order.item.code} concluída.")
    except Exception as exc:
        return _finish_action(request, "quality", quality_dashboard, "", error=exc)


@login_required
@permission_required("costing.change_accountingperiod", raise_exception=True)
@require_POST
def final_close_period_ui(request: HttpRequest, pk: int) -> HttpResponse:
    try:
        period = get_object_or_404(AccountingPeriod.objects.select_related("plant"), pk=pk)
        plant = selected_plant(request)
        if plant and period.plant_id != plant.pk:
            raise ValidationError("O período não pertence à planta selecionada.")
        run = final_close_period(
            period,
            user=request.user,
            strict_reconciliation=request.POST.get("strict_reconciliation") == "on",
        )
        return _finish_action(request, "costing", costing_dashboard, f"Período {period.code} fechado. Execução #{run.pk}.")
    except Exception as exc:
        return _finish_action(request, "costing", costing_dashboard, "", error=exc)


@login_required
def work_order_detail(request: HttpRequest, pk: int) -> HttpResponse:
    order = get_object_or_404(WorkOrder.objects.select_related("plant", "item", "routing"), pk=pk)
    plant = selected_plant(request)
    if plant and order.plant_id != plant.pk:
        raise ValidationError("A OP não pertence à planta selecionada.")
    return render(request, "ui/work_order_detail.html", {"plant": plant, **work_order_detail_context(order)})


@login_required
def purchase_order_detail(request: HttpRequest, pk: int) -> HttpResponse:
    order = get_object_or_404(PurchaseOrder.objects.select_related("plant", "supplier"), pk=pk)
    plant = selected_plant(request)
    if plant and order.plant_id != plant.pk:
        raise ValidationError("A OC não pertence à planta selecionada.")
    return render(request, "ui/purchase_order_detail.html", {"plant": plant, **purchase_order_detail_context(order)})


@login_required
def inspection_detail(request: HttpRequest, pk: int) -> HttpResponse:
    order = get_object_or_404(InspectionOrder.objects.select_related("plant", "item", "plan", "supplier", "lot", "serial", "inspector"), pk=pk)
    plant = selected_plant(request)
    if plant and order.plant_id != plant.pk:
        raise ValidationError("A inspeção não pertence à planta selecionada.")
    return render(request, "ui/inspection_detail.html", {"plant": plant, **inspection_detail_context(order)})


@login_required
def planned_order_detail(request: HttpRequest, pk: int) -> HttpResponse:
    order = get_object_or_404(PlannedOrder.objects.select_related("planning_run__plant", "item"), pk=pk)
    plant = selected_plant(request)
    if plant and order.planning_run.plant_id != plant.pk:
        raise ValidationError("A ordem planejada não pertence à planta selecionada.")
    return render(request, "ui/planned_order_detail.html", {"plant": plant, **planned_order_detail_context(order)})


@login_required
def item_cost_detail(request: HttpRequest, pk: int) -> HttpResponse:
    item_cost = get_object_or_404(ItemCost.objects.select_related("item", "cost_version__plant"), pk=pk)
    plant = selected_plant(request)
    if plant and item_cost.cost_version.plant_id != plant.pk:
        raise ValidationError("O custo não pertence à planta selecionada.")
    return render(request, "ui/item_cost_detail.html", {"plant": plant, **item_cost_detail_context(item_cost)})


def _render_work_order_detail(request: HttpRequest, order: WorkOrder, *, feedback=None) -> HttpResponse:
    payload = {"plant": selected_plant(request), **work_order_detail_context(order)}
    if feedback:
        payload["action_feedback"] = feedback
    template = "ui/partials/work_order_detail_content.html" if request.headers.get("HX-Request") == "true" else "ui/work_order_detail.html"
    return render(request, template, payload)


def _render_inspection_detail(request: HttpRequest, order: InspectionOrder, *, feedback=None) -> HttpResponse:
    payload = {"plant": selected_plant(request), **inspection_detail_context(order)}
    if feedback:
        payload["action_feedback"] = feedback
    template = "ui/partials/inspection_detail_content.html" if request.headers.get("HX-Request") == "true" else "ui/inspection_detail.html"
    return render(request, template, payload)


def _detail_feedback(request, *, kind: str, obj, success: str, error=None):
    feedback = {
        "level": "error" if error else "success",
        "message": _feedback_from_exception(error) if error else success,
    }
    if request.headers.get("HX-Request") == "true":
        if kind == "work_order":
            obj.refresh_from_db()
            return _render_work_order_detail(request, obj, feedback=feedback)
        obj.refresh_from_db()
        return _render_inspection_detail(request, obj, feedback=feedback)
    if error:
        messages.error(request, feedback["message"])
    else:
        messages.success(request, success)
    return redirect("ui:work-order-detail" if kind == "work_order" else "ui:inspection-detail", pk=obj.pk)


@login_required
@permission_required("production.change_workorderoperation", raise_exception=True)
@require_POST
def work_order_operation_action_ui(request: HttpRequest, pk: int, operation_pk: int) -> HttpResponse:
    order = get_object_or_404(WorkOrder.objects.select_related("plant"), pk=pk)
    try:
        operation = get_object_or_404(WorkOrderOperation.objects.select_related("work_order"), pk=operation_pk, work_order=order)
        plant = selected_plant(request)
        if plant and order.plant_id != plant.pk:
            raise ValidationError("A OP não pertence à planta selecionada.")
        advance_work_order_operation(operation=operation, action=request.POST.get("action"), actor=request.user)
        return _detail_feedback(request, kind="work_order", obj=order, success=f"Operação {operation.sequence} atualizada.")
    except Exception as exc:
        return _detail_feedback(request, kind="work_order", obj=order, success="", error=exc)


@login_required
@permission_required("production.add_productionreport", raise_exception=True)
@require_POST
def report_work_order_operation_ui(request: HttpRequest, pk: int, operation_pk: int) -> HttpResponse:
    order = get_object_or_404(WorkOrder.objects.select_related("plant"), pk=pk)
    try:
        operation = get_object_or_404(WorkOrderOperation.objects.select_related("work_order"), pk=operation_pk, work_order=order)
        plant = selected_plant(request)
        if plant and order.plant_id != plant.pk:
            raise ValidationError("A OP não pertence à planta selecionada.")
        report = report_work_order_operation(
            operation=operation,
            good_quantity=_decimal(request.POST.get("good_quantity", "0"), "good_quantity"),
            scrap_quantity=_decimal(request.POST.get("scrap_quantity", "0"), "scrap_quantity"),
            labor_hours=_decimal(request.POST.get("labor_hours", "0"), "labor_hours"),
            machine_hours=_decimal(request.POST.get("machine_hours", "0"), "machine_hours"),
            notes=request.POST.get("notes", ""),
            actor=request.user,
        )
        return _detail_feedback(request, kind="work_order", obj=order, success=f"Apontamento #{report.pk} registrado na operação {operation.sequence}.")
    except Exception as exc:
        return _detail_feedback(request, kind="work_order", obj=order, success="", error=exc)


@login_required
@permission_required("inventory.add_inventorytransaction", raise_exception=True)
@require_POST
def issue_work_order_material_ui(request: HttpRequest, pk: int, material_pk: int) -> HttpResponse:
    order = get_object_or_404(WorkOrder.objects.select_related("plant"), pk=pk)
    try:
        material = get_object_or_404(WorkOrderMaterial.objects.select_related("work_order", "item"), pk=material_pk, work_order=order)
        actual_item = get_object_or_404(Item, pk=request.POST.get("actual_item"))
        location = get_object_or_404(Location.objects.select_related("warehouse"), pk=request.POST.get("source_location"))
        issue_work_order_material(
            material=material,
            actual_item=actual_item,
            source_location=location,
            actual_quantity=_decimal(request.POST.get("actual_quantity"), "actual_quantity"),
            idempotency_key=request.POST.get("idempotency_key") or f"ui-manual-issue-{material.pk}-{uuid4()}",
            notes=request.POST.get("notes", ""),
            actor=request.user,
        )
        return _detail_feedback(request, kind="work_order", obj=order, success=f"Baixa de material registrada para {material.item.code}.")
    except Exception as exc:
        return _detail_feedback(request, kind="work_order", obj=order, success="", error=exc)


@login_required
@permission_required("quality.add_inspectionresult", raise_exception=True)
@require_POST
def record_inspection_result_ui(request: HttpRequest, pk: int, characteristic_pk: int) -> HttpResponse:
    order = get_object_or_404(InspectionOrder.objects.select_related("plant", "plan", "item"), pk=pk)
    try:
        characteristic = get_object_or_404(InspectionCharacteristic, pk=characteristic_pk, plan=order.plan)
        plant = selected_plant(request)
        if plant and order.plant_id != plant.pk:
            raise ValidationError("A inspeção não pertence à planta selecionada.")
        boolean_raw = request.POST.get("boolean_value")
        boolean_value = None
        if boolean_raw in {"true", "1", "yes", "on", "CONFORMING"}:
            boolean_value = True
        elif boolean_raw in {"false", "0", "no", "off", "NONCONFORMING"}:
            boolean_value = False
        numeric_raw = request.POST.get("numeric_value")
        result = record_result(
            order=order,
            characteristic=characteristic,
            sample_number=int(request.POST.get("sample_number") or 1),
            numeric_value=_decimal(numeric_raw, "numeric_value") if numeric_raw not in (None, "") else None,
            boolean_value=boolean_value,
            text_value=request.POST.get("text_value", ""),
            user=request.user,
            notes=request.POST.get("notes", ""),
        )
        state = "conforme" if result.is_conforming else "não conforme"
        return _detail_feedback(request, kind="inspection", obj=order, success=f"Resultado de {characteristic.name} registrado como {state}.")
    except Exception as exc:
        return _detail_feedback(request, kind="inspection", obj=order, success="", error=exc)
