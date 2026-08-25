from decimal import Decimal

from django.core.exceptions import ValidationError as DjangoValidationError
from rest_framework import serializers, status, viewsets
from rest_framework.decorators import action
from rest_framework.response import Response

from apps.common.models import Plant
from apps.inventory.models import Location

from . import serializers as s
from .models import AssetMeterReading, FailureEvent, MaintenanceAsset, MaintenancePart, MaintenancePlan, MaintenanceWorkOrder
from .services import complete_work_order, generate_preventive_orders, issue_maintenance_part, report_failure, start_work_order


class BaseViewSet(viewsets.ModelViewSet):
    pass


class MaintenanceAssetViewSet(BaseViewSet):
    queryset = MaintenanceAsset.objects.select_related("plant", "machine", "work_center")
    serializer_class = s.MaintenanceAssetSerializer
    filterset_fields = ["plant", "asset_type", "criticality", "is_active"]
    search_fields = ["code", "name", "serial_number"]

    @action(detail=True, methods=["post"], url_path="report-failure")
    def report_failure_action(self, request, pk=None):
        asset = self.get_object()
        failure, wo = report_failure(asset=asset, symptom=request.data.get("symptom", ""), failure_class=request.data.get("failure_class", FailureEvent.FailureClass.OTHER), actor=request.user)
        return Response({"failure": s.FailureEventSerializer(failure).data, "work_order": s.MaintenanceWorkOrderSerializer(wo).data}, status=status.HTTP_201_CREATED)


class AssetMeterReadingViewSet(BaseViewSet):
    queryset = AssetMeterReading.objects.select_related("asset", "recorded_by")
    serializer_class = s.AssetMeterReadingSerializer
    filterset_fields = ["asset"]


class MaintenancePlanViewSet(BaseViewSet):
    queryset = MaintenancePlan.objects.select_related("asset", "asset__plant")
    serializer_class = s.MaintenancePlanSerializer
    filterset_fields = ["asset", "strategy", "is_active"]

    @action(detail=False, methods=["post"], url_path="generate-orders")
    def generate_orders(self, request):
        plant = Plant.objects.get(pk=request.data.get("plant"))
        created = generate_preventive_orders(plant=plant, actor=request.user)
        return Response({"created": len(created), "orders": s.MaintenanceWorkOrderSerializer(created, many=True).data})


class MaintenanceWorkOrderViewSet(BaseViewSet):
    queryset = MaintenanceWorkOrder.objects.select_related("plant", "asset", "asset__machine", "plan", "assigned_to")
    serializer_class = s.MaintenanceWorkOrderSerializer
    filterset_fields = ["plant", "asset", "plan", "order_type", "priority", "status"]
    search_fields = ["number", "title", "asset__code"]

    @action(detail=True, methods=["post"])
    def start(self, request, pk=None):
        try: wo = start_work_order(work_order=self.get_object(), actor=request.user)
        except DjangoValidationError as exc: raise serializers.ValidationError(exc.messages)
        return Response(self.get_serializer(wo).data)

    @action(detail=True, methods=["post"])
    def complete(self, request, pk=None):
        try: wo = complete_work_order(work_order=self.get_object(), completion_notes=request.data.get("completion_notes", ""), meter_value=request.data.get("meter_value"), actor=request.user)
        except DjangoValidationError as exc: raise serializers.ValidationError(exc.messages)
        return Response(self.get_serializer(wo).data)


class MaintenancePartViewSet(BaseViewSet):
    queryset = MaintenancePart.objects.select_related("work_order", "item", "source_location")
    serializer_class = s.MaintenancePartSerializer
    filterset_fields = ["work_order", "item"]

    @action(detail=True, methods=["post"])
    def issue(self, request, pk=None):
        location = Location.objects.get(pk=request.data.get("location"))
        try: part = issue_maintenance_part(part=self.get_object(), location=location, quantity=Decimal(str(request.data.get("quantity", "0"))), actor=request.user, idempotency_key=request.data.get("idempotency_key"))
        except DjangoValidationError as exc: raise serializers.ValidationError(exc.messages)
        return Response(self.get_serializer(part).data)


class FailureEventViewSet(BaseViewSet):
    queryset = FailureEvent.objects.select_related("asset", "work_order", "downtime_event", "reported_by")
    serializer_class = s.FailureEventSerializer
    filterset_fields = ["asset", "work_order", "failure_class"]


from .models import TechnicianSkill, TechnicianProfile, TechnicianSkillAssignment, WorkOrderAssignment, MaintenanceSLA, ConditionReading, ConditionRule
from .services import evaluate_condition_reading, release_work_order, maintenance_part_availability

class TechnicianSkillViewSet(BaseViewSet):
    queryset = TechnicianSkill.objects.all()
    serializer_class = s.TechnicianSkillSerializer
    filterset_fields = ["is_active"]
    search_fields = ["code", "name"]

class TechnicianProfileViewSet(BaseViewSet):
    queryset = TechnicianProfile.objects.select_related("plant", "user")
    serializer_class = s.TechnicianProfileSerializer
    filterset_fields = ["plant", "is_active"]
    search_fields = ["employee_code", "user__username"]

class TechnicianSkillAssignmentViewSet(BaseViewSet):
    queryset = TechnicianSkillAssignment.objects.select_related("technician", "skill")
    serializer_class = s.TechnicianSkillAssignmentSerializer
    filterset_fields = ["technician", "skill"]

class WorkOrderAssignmentViewSet(BaseViewSet):
    queryset = WorkOrderAssignment.objects.select_related("work_order", "technician", "technician__user")
    serializer_class = s.WorkOrderAssignmentSerializer
    filterset_fields = ["work_order", "technician", "is_lead"]

class MaintenanceSLAViewSet(BaseViewSet):
    queryset = MaintenanceSLA.objects.select_related("plant")
    serializer_class = s.MaintenanceSLASerializer
    filterset_fields = ["plant", "priority", "is_active"]

class ConditionRuleViewSet(BaseViewSet):
    queryset = ConditionRule.objects.select_related("asset")
    serializer_class = s.ConditionRuleSerializer
    filterset_fields = ["asset", "metric", "is_active"]

class ConditionReadingViewSet(BaseViewSet):
    queryset = ConditionReading.objects.select_related("asset", "recorded_by")
    serializer_class = s.ConditionReadingSerializer
    filterset_fields = ["asset", "metric", "source"]

    def perform_create(self, serializer):
        reading = serializer.save(recorded_by=self.request.user if self.request.user.is_authenticated else None)
        evaluate_condition_reading(reading=reading, actor=self.request.user if self.request.user.is_authenticated else None)

# Add maintenance release/parts actions without changing the legacy serializer contract.
def release(self, request, pk=None):
    try:
        wo = release_work_order(work_order=self.get_object(), actor=request.user, require_parts=request.data.get("require_parts", True))
    except DjangoValidationError as exc:
        raise serializers.ValidationError(exc.messages)
    return Response(self.get_serializer(wo).data)

MaintenanceWorkOrderViewSet.release = action(detail=True, methods=["post"])(release)

@action(detail=True, methods=["get"], url_path="part-availability")
def part_availability(self, request, pk=None):
    ok, rows = maintenance_part_availability(self.get_object())
    return Response({"all_available": ok, "parts": [{"part": r["part"].pk, "item": r["part"].item.code, "remaining": str(r["remaining"]), "available": str(r["available"]), "sufficient": r["sufficient"]} for r in rows]})
MaintenanceWorkOrderViewSet.part_availability = part_availability

from .models import MaintenanceRequiredSkill, MaintenancePartReservation, MaintenanceScheduleConflict
from .services import auto_assign_technicians, reserve_maintenance_parts, schedule_maintenance_work_order, refresh_priority_scores

class MaintenanceRequiredSkillViewSet(BaseViewSet):
    queryset = MaintenanceRequiredSkill.objects.select_related("work_order", "skill")
    serializer_class = s.MaintenanceRequiredSkillSerializer
    filterset_fields = ["work_order", "skill", "min_proficiency"]

class MaintenancePartReservationViewSet(viewsets.ReadOnlyModelViewSet):
    queryset = MaintenancePartReservation.objects.select_related("part", "reservation", "reservation__location")
    serializer_class = s.MaintenancePartReservationSerializer
    filterset_fields = ["part", "part__work_order"]

class MaintenanceScheduleConflictViewSet(viewsets.ReadOnlyModelViewSet):
    queryset = MaintenanceScheduleConflict.objects.select_related("work_order", "related_operation")
    serializer_class = s.MaintenanceScheduleConflictSerializer
    filterset_fields = ["work_order", "conflict_type", "severity"]

@action(detail=True, methods=["post"], url_path="auto-assign")
def auto_assign(self, request, pk=None):
    try:
        assignments = auto_assign_technicians(work_order=self.get_object(), actor=request.user, replace=bool(request.data.get("replace", False)))
    except DjangoValidationError as exc:
        raise serializers.ValidationError(exc.messages)
    return Response({"assigned": [a.technician.employee_code for a in assignments]})
MaintenanceWorkOrderViewSet.auto_assign = auto_assign

@action(detail=True, methods=["post"], url_path="reserve-parts")
def reserve_parts(self, request, pk=None):
    try:
        reservations = reserve_maintenance_parts(work_order=self.get_object(), actor=request.user)
    except DjangoValidationError as exc:
        raise serializers.ValidationError(exc.messages)
    return Response({"reservations": [r.pk for r in reservations]})
MaintenanceWorkOrderViewSet.reserve_parts = reserve_parts

@action(detail=True, methods=["post"], url_path="schedule")
def schedule(self, request, pk=None):
    from django.utils.dateparse import parse_datetime
    start = parse_datetime(request.data.get("start") or "")
    end = parse_datetime(request.data.get("end") or "")
    if not start or not end:
        raise serializers.ValidationError("start/end devem ser datetime ISO-8601.")
    try:
        wo, conflicts = schedule_maintenance_work_order(work_order=self.get_object(), start=start, end=end, actor=request.user, force=bool(request.data.get("force", False)))
    except DjangoValidationError as exc:
        raise serializers.ValidationError(exc.messages)
    return Response({"work_order": s.MaintenanceWorkOrderSerializer(wo).data, "conflicts": len(conflicts)})
MaintenanceWorkOrderViewSet.schedule = schedule

@action(detail=False, methods=["post"], url_path="refresh-priority")
def refresh_priority(self, request):
    plant = Plant.objects.get(pk=request.data.get("plant"))
    rows = refresh_priority_scores(plant=plant)
    return Response({"updated": len(rows)})
MaintenanceWorkOrderViewSet.refresh_priority = refresh_priority
