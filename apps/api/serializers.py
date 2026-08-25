from decimal import Decimal

from rest_framework import serializers

from apps.common.models import DomainEvent

from apps.common.models import Plant, ShopCalendarDay
from apps.engineering.models import (
    BOMRevision, BOMRevisionLine, EngineeringChange, EngineeringChangeApproval,
    EngineeringChangeItem, EngineeringImpact, RoutingRevision,
)
from apps.demand.models import Forecast, MasterProductionSchedule, SalesOrder, SalesOrderLine
from apps.inventory.models import InventoryTransaction, Location, Reservation, StockBalance, Warehouse
from apps.masterdata.models import (
    BOMLine,
    Item,
    ItemPlantPolicy,
    ItemSubstitute,
    ItemSupplier,
    Routing,
    RoutingOperation,
    Supplier,
    WorkCenter,
    WorkCenterShift,
)
from apps.planning.models import (
    CapacityAllocation,
    CapacityScenario,
    DemandPeggingAllocation,
    PeggingRecord,
    PlannedOrder,
    PlanningBucket,
    PlanningChange,
    PlanningMessage,
    PlanningRun,
)
from apps.production.models import (
    ProductionReport,
    WorkOrder,
    WorkOrderCompletion,
    WorkOrderMaterial,
    WorkOrderOperation,
)
from apps.purchasing.models import GoodsReceipt, PurchaseOrder, PurchaseOrderLine
from apps.traceability.models import (InventoryLot, LotBalance, LotReservation, LotTransaction, SerialComponent, SerialNumber, SerialTransaction)


class DynamicModelSerializer(serializers.ModelSerializer):
    class Meta:
        fields = "__all__"


class PlantSerializer(DynamicModelSerializer):
    class Meta(DynamicModelSerializer.Meta):
        model = Plant


class ShopCalendarDaySerializer(DynamicModelSerializer):
    class Meta(DynamicModelSerializer.Meta):
        model = ShopCalendarDay


class DomainEventSerializer(DynamicModelSerializer):
    class Meta(DynamicModelSerializer.Meta):
        model = DomainEvent


class ItemSerializer(DynamicModelSerializer):
    class Meta(DynamicModelSerializer.Meta):
        model = Item


class ItemPlantPolicySerializer(DynamicModelSerializer):
    class Meta(DynamicModelSerializer.Meta):
        model = ItemPlantPolicy


class BOMLineSerializer(DynamicModelSerializer):
    class Meta(DynamicModelSerializer.Meta):
        model = BOMLine

    def validate(self, attrs):
        parent = attrs.get("parent", getattr(self.instance, "parent", None))
        component = attrs.get("component", getattr(self.instance, "component", None))
        if parent and component and parent.pk == component.pk:
            raise serializers.ValidationError("Um item não pode ser componente de si mesmo.")
        return attrs


class WorkCenterSerializer(DynamicModelSerializer):
    class Meta(DynamicModelSerializer.Meta):
        model = WorkCenter


class WorkCenterShiftSerializer(DynamicModelSerializer):
    class Meta(DynamicModelSerializer.Meta):
        model = WorkCenterShift


class RoutingSerializer(DynamicModelSerializer):
    class Meta(DynamicModelSerializer.Meta):
        model = Routing


class RoutingOperationSerializer(DynamicModelSerializer):
    class Meta(DynamicModelSerializer.Meta):
        model = RoutingOperation


class SupplierSerializer(DynamicModelSerializer):
    class Meta(DynamicModelSerializer.Meta):
        model = Supplier


class ItemSupplierSerializer(DynamicModelSerializer):
    class Meta(DynamicModelSerializer.Meta):
        model = ItemSupplier


class ItemSubstituteSerializer(DynamicModelSerializer):
    class Meta(DynamicModelSerializer.Meta):
        model = ItemSubstitute


class WarehouseSerializer(DynamicModelSerializer):
    class Meta(DynamicModelSerializer.Meta):
        model = Warehouse


class LocationSerializer(DynamicModelSerializer):
    class Meta(DynamicModelSerializer.Meta):
        model = Location


class StockBalanceSerializer(DynamicModelSerializer):
    available = serializers.DecimalField(max_digits=18, decimal_places=4, read_only=True)

    class Meta(DynamicModelSerializer.Meta):
        model = StockBalance


class InventoryTransactionSerializer(DynamicModelSerializer):
    class Meta(DynamicModelSerializer.Meta):
        model = InventoryTransaction
        read_only_fields = ["posted_at", "posted_by"]


class ReservationSerializer(DynamicModelSerializer):
    class Meta(DynamicModelSerializer.Meta):
        model = Reservation


class ForecastSerializer(DynamicModelSerializer):
    class Meta(DynamicModelSerializer.Meta):
        model = Forecast


class SalesOrderLineSerializer(DynamicModelSerializer):
    class Meta(DynamicModelSerializer.Meta):
        model = SalesOrderLine


class SalesOrderSerializer(DynamicModelSerializer):
    lines = SalesOrderLineSerializer(many=True, read_only=True)

    class Meta(DynamicModelSerializer.Meta):
        model = SalesOrder


class MasterProductionScheduleSerializer(DynamicModelSerializer):
    class Meta(DynamicModelSerializer.Meta):
        model = MasterProductionSchedule


class WorkOrderMaterialSerializer(DynamicModelSerializer):
    class Meta(DynamicModelSerializer.Meta):
        model = WorkOrderMaterial


class WorkOrderOperationSerializer(DynamicModelSerializer):
    class Meta(DynamicModelSerializer.Meta):
        model = WorkOrderOperation


class WorkOrderSerializer(DynamicModelSerializer):
    materials = WorkOrderMaterialSerializer(many=True, read_only=True)
    operations = WorkOrderOperationSerializer(many=True, read_only=True)

    class Meta(DynamicModelSerializer.Meta):
        model = WorkOrder


class ProductionReportSerializer(DynamicModelSerializer):
    class Meta(DynamicModelSerializer.Meta):
        model = ProductionReport


class WorkOrderCompletionSerializer(DynamicModelSerializer):
    class Meta(DynamicModelSerializer.Meta):
        model = WorkOrderCompletion


class PurchaseOrderLineSerializer(DynamicModelSerializer):
    class Meta(DynamicModelSerializer.Meta):
        model = PurchaseOrderLine


class PurchaseOrderSerializer(DynamicModelSerializer):
    lines = PurchaseOrderLineSerializer(many=True, read_only=True)

    class Meta(DynamicModelSerializer.Meta):
        model = PurchaseOrder


class GoodsReceiptSerializer(DynamicModelSerializer):
    class Meta(DynamicModelSerializer.Meta):
        model = GoodsReceipt


class PlanningRunSerializer(DynamicModelSerializer):
    class Meta(DynamicModelSerializer.Meta):
        model = PlanningRun
        read_only_fields = ["status", "started_at", "completed_at", "error_message"]


class PlanningBucketSerializer(DynamicModelSerializer):
    class Meta(DynamicModelSerializer.Meta):
        model = PlanningBucket


class PlannedOrderSerializer(DynamicModelSerializer):
    class Meta(DynamicModelSerializer.Meta):
        model = PlannedOrder


class DemandPeggingAllocationSerializer(DynamicModelSerializer):
    class Meta(DynamicModelSerializer.Meta):
        model = DemandPeggingAllocation


class PeggingRecordSerializer(DynamicModelSerializer):
    class Meta(DynamicModelSerializer.Meta):
        model = PeggingRecord


class PlanningMessageSerializer(DynamicModelSerializer):
    class Meta(DynamicModelSerializer.Meta):
        model = PlanningMessage


class PlanningChangeSerializer(DynamicModelSerializer):
    class Meta(DynamicModelSerializer.Meta):
        model = PlanningChange


class CapacityAllocationSerializer(DynamicModelSerializer):
    utilization_percent = serializers.SerializerMethodField()

    class Meta(DynamicModelSerializer.Meta):
        model = CapacityAllocation

    def get_utilization_percent(self, obj) -> str | None:
        value = obj.utilization_percent
        return str(value.quantize(Decimal("0.01"))) if value is not None else None


class CapacityScenarioSerializer(DynamicModelSerializer):
    class Meta(DynamicModelSerializer.Meta):
        model = CapacityScenario
        read_only_fields = [
            "status",
            "started_at",
            "completed_at",
            "promised_date",
            "feasible",
            "summary",
            "error_message",
        ]


class PurchaseReceiptCommandSerializer(serializers.Serializer):
    quantity = serializers.DecimalField(max_digits=18, decimal_places=4)
    destination_location = serializers.PrimaryKeyRelatedField(queryset=Location.objects.all())
    receipt_number = serializers.CharField(max_length=40)
    idempotency_key = serializers.CharField(max_length=160)
    received_at = serializers.DateTimeField(required=False)
    lot_number = serializers.CharField(max_length=60, required=False, allow_blank=True, default="")
    notes = serializers.CharField(required=False, allow_blank=True, default="")


class WorkOrderCompletionCommandSerializer(serializers.Serializer):
    good_quantity = serializers.DecimalField(max_digits=18, decimal_places=4)
    scrap_quantity = serializers.DecimalField(
        max_digits=18, decimal_places=4, required=False, default=Decimal("0")
    )
    destination_location = serializers.PrimaryKeyRelatedField(queryset=Location.objects.all())
    idempotency_key = serializers.CharField(max_length=160)
    backflush = serializers.BooleanField(required=False, default=True)
    reported_at = serializers.DateTimeField(required=False)
    notes = serializers.CharField(required=False, allow_blank=True, default="")


class CTPRequestSerializer(serializers.Serializer):
    plant = serializers.PrimaryKeyRelatedField(queryset=Plant.objects.all())
    quantity = serializers.DecimalField(max_digits=18, decimal_places=4)
    release_date = serializers.DateField()
    due_date = serializers.DateField()
    name = serializers.CharField(max_length=160, required=False, allow_blank=True)
    include_open_orders = serializers.BooleanField(required=False, default=True)
    capacity_overrides = serializers.JSONField(required=False, default=dict)

    def validate(self, attrs):
        if attrs["due_date"] < attrs["release_date"]:
            raise serializers.ValidationError("due_date deve ser igual ou posterior a release_date.")
        return attrs


class WhatIfRequestSerializer(CTPRequestSerializer):
    item = serializers.PrimaryKeyRelatedField(queryset=Item.objects.all())


class NetChangeRequestSerializer(serializers.Serializer):
    plant = serializers.PrimaryKeyRelatedField(queryset=Plant.objects.all())
    horizon_start = serializers.DateField()
    horizon_end = serializers.DateField()
    name = serializers.CharField(max_length=160, required=False, allow_blank=True)
    include_sales_orders = serializers.BooleanField(required=False, default=False)
    include_forecasts = serializers.BooleanField(required=False, default=False)

    def validate(self, attrs):
        if attrs["horizon_end"] < attrs["horizon_start"]:
            raise serializers.ValidationError("horizon_end deve ser posterior a horizon_start.")
        return attrs


class ATPRequestSerializer(serializers.Serializer):
    plant = serializers.PrimaryKeyRelatedField(queryset=Plant.objects.all())
    quantity = serializers.DecimalField(max_digits=18, decimal_places=4)
    requested_date = serializers.DateField()
    horizon_days = serializers.IntegerField(required=False, default=365, min_value=1, max_value=1095)


class EngineeringChangeItemSerializer(DynamicModelSerializer):
    class Meta(DynamicModelSerializer.Meta): model = EngineeringChangeItem
class EngineeringChangeApprovalSerializer(DynamicModelSerializer):
    class Meta(DynamicModelSerializer.Meta): model = EngineeringChangeApproval
class EngineeringImpactSerializer(DynamicModelSerializer):
    class Meta(DynamicModelSerializer.Meta): model = EngineeringImpact
class BOMRevisionLineSerializer(DynamicModelSerializer):
    class Meta(DynamicModelSerializer.Meta): model = BOMRevisionLine
class BOMRevisionSerializer(DynamicModelSerializer):
    lines = BOMRevisionLineSerializer(many=True, read_only=True)
    class Meta(DynamicModelSerializer.Meta): model = BOMRevision
class RoutingRevisionSerializer(DynamicModelSerializer):
    class Meta(DynamicModelSerializer.Meta): model = RoutingRevision
class EngineeringChangeSerializer(DynamicModelSerializer):
    items = EngineeringChangeItemSerializer(many=True, read_only=True)
    approvals = EngineeringChangeApprovalSerializer(many=True, read_only=True)
    impacts = EngineeringImpactSerializer(many=True, read_only=True)
    class Meta(DynamicModelSerializer.Meta): model = EngineeringChange
class DecisionSerializer(serializers.Serializer):
    comment = serializers.CharField(required=False, allow_blank=True)


class InventoryLotSerializer(DynamicModelSerializer):
    class Meta(DynamicModelSerializer.Meta): model = InventoryLot

class LotBalanceSerializer(DynamicModelSerializer):
    available = serializers.SerializerMethodField()
    class Meta(DynamicModelSerializer.Meta): model = LotBalance
    def get_available(self, obj) -> str: return str(obj.available)

class LotTransactionSerializer(DynamicModelSerializer):
    class Meta(DynamicModelSerializer.Meta): model = LotTransaction

class LotReservationSerializer(DynamicModelSerializer):
    remaining_quantity = serializers.SerializerMethodField()
    class Meta(DynamicModelSerializer.Meta): model = LotReservation
    def get_remaining_quantity(self, obj) -> str: return str(obj.remaining_quantity)

class SerialNumberSerializer(DynamicModelSerializer):
    class Meta(DynamicModelSerializer.Meta): model = SerialNumber

class SerialTransactionSerializer(DynamicModelSerializer):
    class Meta(DynamicModelSerializer.Meta): model = SerialTransaction

class SerialComponentSerializer(DynamicModelSerializer):
    class Meta(DynamicModelSerializer.Meta): model = SerialComponent

class LotPostCommandSerializer(serializers.Serializer):
    transaction_type = serializers.ChoiceField(choices=LotTransaction.TransactionType.choices)
    quantity = serializers.DecimalField(max_digits=18, decimal_places=4)
    from_location = serializers.PrimaryKeyRelatedField(queryset=Location.objects.all(), required=False, allow_null=True)
    to_location = serializers.PrimaryKeyRelatedField(queryset=Location.objects.all(), required=False, allow_null=True)
    reference_type = serializers.CharField(max_length=40, required=False, allow_blank=True, default="")
    reference_id = serializers.CharField(max_length=64, required=False, allow_blank=True, default="")
    idempotency_key = serializers.CharField(max_length=160)
    notes = serializers.CharField(required=False, allow_blank=True, default="")

class LotStatusCommandSerializer(serializers.Serializer):
    status = serializers.ChoiceField(choices=InventoryLot.Status.choices)
    reason = serializers.CharField(required=False, allow_blank=True, default="")

class SerialPostCommandSerializer(serializers.Serializer):
    transaction_type = serializers.ChoiceField(choices=SerialTransaction.TransactionType.choices)
    from_location = serializers.PrimaryKeyRelatedField(queryset=Location.objects.all(), required=False, allow_null=True)
    to_location = serializers.PrimaryKeyRelatedField(queryset=Location.objects.all(), required=False, allow_null=True)
    reference_type = serializers.CharField(max_length=40, required=False, allow_blank=True, default="")
    reference_id = serializers.CharField(max_length=64, required=False, allow_blank=True, default="")
    idempotency_key = serializers.CharField(max_length=160)
    notes = serializers.CharField(required=False, allow_blank=True, default="")

class InstallComponentCommandSerializer(serializers.Serializer):
    component_serial = serializers.PrimaryKeyRelatedField(queryset=SerialNumber.objects.all())
    installed_at = serializers.DateTimeField(required=False)
    work_order_id = serializers.CharField(max_length=64, required=False, allow_blank=True, default="")
    operation_sequence = serializers.IntegerField(required=False, allow_null=True, min_value=1)
    notes = serializers.CharField(required=False, allow_blank=True, default="")

from apps.quality.models import Disposition, InspectionCharacteristic, InspectionOrder, InspectionPlan, InspectionResult, NonConformance

class InspectionPlanSerializer(DynamicModelSerializer):
    class Meta(DynamicModelSerializer.Meta): model = InspectionPlan

class InspectionCharacteristicSerializer(DynamicModelSerializer):
    class Meta(DynamicModelSerializer.Meta): model = InspectionCharacteristic

class InspectionResultSerializer(DynamicModelSerializer):
    class Meta(DynamicModelSerializer.Meta): model = InspectionResult

class InspectionOrderSerializer(DynamicModelSerializer):
    results = InspectionResultSerializer(many=True, read_only=True)
    class Meta(DynamicModelSerializer.Meta): model = InspectionOrder

class NonConformanceSerializer(DynamicModelSerializer):
    class Meta(DynamicModelSerializer.Meta): model = NonConformance

class DispositionSerializer(DynamicModelSerializer):
    class Meta(DynamicModelSerializer.Meta): model = Disposition

class InspectionResultCommandSerializer(serializers.Serializer):
    characteristic = serializers.PrimaryKeyRelatedField(queryset=InspectionCharacteristic.objects.all())
    sample_number = serializers.IntegerField(min_value=1, default=1)
    numeric_value = serializers.DecimalField(max_digits=18, decimal_places=6, required=False, allow_null=True)
    boolean_value = serializers.BooleanField(required=False, allow_null=True)
    text_value = serializers.CharField(required=False, allow_blank=True, default="")
    notes = serializers.CharField(required=False, allow_blank=True, default="")

class InspectionCompleteCommandSerializer(serializers.Serializer):
    quantity_approved = serializers.DecimalField(max_digits=18, decimal_places=4, min_value=Decimal("0"))
    quantity_rejected = serializers.DecimalField(max_digits=18, decimal_places=4, min_value=Decimal("0"))
    notes = serializers.CharField(required=False, allow_blank=True, default="")

class DispositionCommandSerializer(serializers.Serializer):
    decision = serializers.ChoiceField(choices=Disposition.Decision.choices)
    quantity = serializers.DecimalField(max_digits=18, decimal_places=4, min_value=Decimal("0.0001"))
    instructions = serializers.CharField(required=False, allow_blank=True, default="")

from apps.recall.models import RecallAction, RecallAffectedUnit, RecallCase, RecallCriterion

class RecallCriterionSerializer(DynamicModelSerializer):
    class Meta(DynamicModelSerializer.Meta): model = RecallCriterion

class RecallAffectedUnitSerializer(DynamicModelSerializer):
    class Meta(DynamicModelSerializer.Meta): model = RecallAffectedUnit

class RecallActionSerializer(DynamicModelSerializer):
    class Meta(DynamicModelSerializer.Meta): model = RecallAction

class RecallCaseSerializer(DynamicModelSerializer):
    criteria = RecallCriterionSerializer(many=True, read_only=True)
    affected_units = RecallAffectedUnitSerializer(many=True, read_only=True)
    class Meta(DynamicModelSerializer.Meta):
        model = RecallCase
        read_only_fields = ["status", "approved_by", "approved_at", "completed_at", "opened_by"]

class RecallAnalyzeCommandSerializer(serializers.Serializer):
    include_components = serializers.BooleanField(default=True)
    include_where_used = serializers.BooleanField(default=True)


from apps.demand.models import SalesDelivery, SalesDeliveryLine
class SalesDeliveryLineSerializer(serializers.ModelSerializer):
    class Meta:
        model=SalesDeliveryLine; fields="__all__"
class SalesDeliverySerializer(serializers.ModelSerializer):
    lines=SalesDeliveryLineSerializer(many=True,read_only=True)
    class Meta:
        model=SalesDelivery; fields="__all__"
