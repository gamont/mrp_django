from django.core.exceptions import ValidationError as DjangoValidationError
from django.db.models import Prefetch
from rest_framework import status, viewsets
from rest_framework.decorators import action
from rest_framework.exceptions import ValidationError as DRFValidationError
from rest_framework.response import Response

from apps.common.models import DomainEvent, Plant, ShopCalendarDay
from apps.engineering.models import (BOMRevision, BOMRevisionLine, EngineeringChange, EngineeringChangeApproval, EngineeringChangeItem, EngineeringImpact, RoutingRevision)
from apps.engineering.services import activate_change, analyze_impact, approve_change, reject_change, submit_change
from apps.demand.models import Forecast, MasterProductionSchedule, SalesOrder, SalesOrderLine
from apps.inventory.models import InventoryTransaction, Location, Reservation, StockBalance, Warehouse
from apps.inventory.services import post_inventory_transaction
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
from apps.planning.atp import calculate_atp
from apps.planning.capacity import capacity_bottleneck_summary, execute_capacity_scenario
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
from apps.planning.net_change import execute_net_change_run
from apps.planning.services import convert_planned_order, execute_planning_run
from apps.production.models import (
    ProductionReport,
    WorkOrder,
    WorkOrderCompletion,
    WorkOrderMaterial,
    WorkOrderOperation,
)
from apps.production.services import complete_work_order, materialize_work_order, release_work_order
from apps.purchasing.models import GoodsReceipt, PurchaseOrder, PurchaseOrderLine
from apps.purchasing.services import receive_purchase_order_line
from apps.traceability.models import InventoryLot, LotBalance, LotReservation, LotTransaction, SerialComponent, SerialNumber, SerialTransaction
from apps.traceability.services import change_lot_status, install_component, post_lot_transaction, post_serial_transaction, serial_genealogy

from . import serializers as s


def _as_drf_validation(exc: DjangoValidationError):
    if hasattr(exc, "message_dict"):
        raise DRFValidationError(exc.message_dict)
    raise DRFValidationError(getattr(exc, "messages", [str(exc)]))


class BaseModelViewSet(viewsets.ModelViewSet):
    ordering_fields = "__all__"


class PlantViewSet(BaseModelViewSet):
    queryset = Plant.objects.all()
    serializer_class = s.PlantSerializer
    search_fields = ["code", "name"]


class ShopCalendarDayViewSet(BaseModelViewSet):
    queryset = ShopCalendarDay.objects.select_related("plant")
    serializer_class = s.ShopCalendarDaySerializer
    filterset_fields = ["plant", "date", "is_working_day"]


class DomainEventViewSet(viewsets.ReadOnlyModelViewSet):
    queryset = DomainEvent.objects.select_related("actor")
    serializer_class = s.DomainEventSerializer
    filterset_fields = ["event_type", "aggregate_type", "aggregate_id", "occurred_at"]
    search_fields = ["idempotency_key", "aggregate_id"]
    ordering_fields = ["occurred_at", "event_type", "aggregate_type"]


class ItemViewSet(BaseModelViewSet):
    queryset = Item.objects.all()
    permission_required_by_action = {
        "atp": "masterdata.view_item",
        "ctp": "planning.add_capacityscenario",
    }
    serializer_class = s.ItemSerializer
    search_fields = ["code", "description"]
    filterset_fields = ["item_type", "status", "is_active", "low_level_code"]

    @action(detail=True, methods=["get"], url_path="bom-tree")
    def bom_tree(self, request, pk=None):
        item = self.get_object()

        def build(node, visited):
            if node.id in visited:
                return {"item": node.code, "cycle": True, "components": []}
            children = []
            next_visited = visited | {node.id}
            for line in node.bom_components.filter(is_active=True).select_related("component"):
                children.append(
                    {
                        "sequence": line.sequence,
                        "quantity_per": str(line.quantity_per),
                        "scrap_percent": str(line.scrap_percent),
                        "component": build(line.component, next_visited),
                    }
                )
            return {"item": node.code, "description": node.description, "components": children}

        return Response(build(item, set()))

    @action(detail=True, methods=["get"], url_path="where-used")
    def where_used(self, request, pk=None):
        item = self.get_object()
        rows = item.where_used.filter(is_active=True).select_related("parent")
        return Response(s.BOMLineSerializer(rows, many=True).data)

    @action(detail=True, methods=["post"], url_path="atp")
    def atp(self, request, pk=None):
        payload = s.ATPRequestSerializer(data=request.data)
        payload.is_valid(raise_exception=True)
        return Response(calculate_atp(item=self.get_object(), **payload.validated_data))

    @action(detail=True, methods=["post"], url_path="ctp")
    def ctp(self, request, pk=None):
        item = self.get_object()
        payload = s.CTPRequestSerializer(data=request.data)
        payload.is_valid(raise_exception=True)
        data = payload.validated_data
        scenario = CapacityScenario.objects.create(
            name=data.get("name") or f"CTP {item.code}",
            scenario_type=CapacityScenario.ScenarioType.CTP,
            plant=data["plant"],
            item=item,
            quantity=data["quantity"],
            requested_release_date=data["release_date"],
            requested_due_date=data["due_date"],
            parameters={
                "include_open_orders": data["include_open_orders"],
                "capacity_overrides": data["capacity_overrides"],
            },
        )
        try:
            scenario = execute_capacity_scenario(scenario)
        except DjangoValidationError as exc:
            _as_drf_validation(exc)
        return Response(
            {
                "scenario": s.CapacityScenarioSerializer(scenario).data,
                "bottlenecks": capacity_bottleneck_summary(scenario),
            },
            status=status.HTTP_201_CREATED,
        )


class ItemPlantPolicyViewSet(BaseModelViewSet):
    queryset = ItemPlantPolicy.objects.select_related("plant", "item")
    serializer_class = s.ItemPlantPolicySerializer
    filterset_fields = ["plant", "item", "source_type", "lot_sizing_rule"]


class ItemSubstituteViewSet(BaseModelViewSet):
    queryset = ItemSubstitute.objects.select_related("plant", "item", "substitute_item")
    serializer_class = s.ItemSubstituteSerializer
    filterset_fields = ["plant", "item", "substitute_item", "is_active"]
    search_fields = ["item__code", "substitute_item__code", "notes"]


class BOMLineViewSet(BaseModelViewSet):
    queryset = BOMLine.objects.select_related("parent", "component")
    serializer_class = s.BOMLineSerializer
    filterset_fields = ["parent", "component", "bom_type", "is_active"]
    search_fields = ["parent__code", "component__code", "engineering_change"]


class WorkCenterViewSet(BaseModelViewSet):
    queryset = WorkCenter.objects.select_related("plant")
    serializer_class = s.WorkCenterSerializer
    filterset_fields = ["plant", "is_critical", "is_active"]
    search_fields = ["code", "name"]


class WorkCenterShiftViewSet(BaseModelViewSet):
    queryset = WorkCenterShift.objects.select_related("work_center", "work_center__plant")
    serializer_class = s.WorkCenterShiftSerializer
    filterset_fields = ["work_center", "weekday", "is_active"]
    search_fields = ["name", "work_center__code"]


class RoutingViewSet(BaseModelViewSet):
    queryset = Routing.objects.select_related("plant", "item")
    serializer_class = s.RoutingSerializer
    filterset_fields = ["plant", "item", "is_primary", "is_active"]


class RoutingOperationViewSet(BaseModelViewSet):
    queryset = RoutingOperation.objects.select_related("routing", "work_center", "alternate_work_center")
    serializer_class = s.RoutingOperationSerializer
    filterset_fields = ["routing", "work_center"]


class SupplierViewSet(BaseModelViewSet):
    queryset = Supplier.objects.all()
    serializer_class = s.SupplierSerializer
    search_fields = ["code", "name"]


class ItemSupplierViewSet(BaseModelViewSet):
    queryset = ItemSupplier.objects.select_related("plant", "item", "supplier")
    serializer_class = s.ItemSupplierSerializer
    filterset_fields = ["plant", "item", "supplier", "is_primary"]


class WarehouseViewSet(BaseModelViewSet):
    queryset = Warehouse.objects.select_related("plant")
    serializer_class = s.WarehouseSerializer
    filterset_fields = ["plant", "is_active"]
    search_fields = ["code", "name"]


class LocationViewSet(BaseModelViewSet):
    queryset = Location.objects.select_related("warehouse", "warehouse__plant")
    serializer_class = s.LocationSerializer
    filterset_fields = ["warehouse", "is_active"]
    search_fields = ["code", "description"]


class StockBalanceViewSet(viewsets.ReadOnlyModelViewSet):
    queryset = StockBalance.objects.select_related("item", "location", "location__warehouse")
    serializer_class = s.StockBalanceSerializer
    filterset_fields = ["item", "location", "location__warehouse", "location__warehouse__plant"]
    search_fields = ["item__code", "location__code"]


class InventoryTransactionViewSet(BaseModelViewSet):
    queryset = InventoryTransaction.objects.select_related("item", "from_location", "to_location")
    serializer_class = s.InventoryTransactionSerializer
    filterset_fields = ["transaction_type", "item", "from_location", "to_location", "idempotency_key"]
    http_method_names = ["get", "post", "head", "options"]

    def perform_create(self, serializer):
        tx = InventoryTransaction(**serializer.validated_data, posted_by=self.request.user)
        tx = post_inventory_transaction(tx)
        serializer.instance = tx


class ReservationViewSet(viewsets.ReadOnlyModelViewSet):
    queryset = Reservation.objects.select_related("item", "requested_item", "location")
    serializer_class = s.ReservationSerializer
    filterset_fields = ["item", "requested_item", "location", "status", "demand_type", "demand_id"]


class ForecastViewSet(BaseModelViewSet):
    queryset = Forecast.objects.select_related("plant", "item")
    serializer_class = s.ForecastSerializer
    filterset_fields = ["plant", "item", "status", "version"]


class SalesOrderViewSet(BaseModelViewSet):
    queryset = SalesOrder.objects.prefetch_related(
        Prefetch("lines", queryset=SalesOrderLine.objects.select_related("item"))
    )
    serializer_class = s.SalesOrderSerializer
    filterset_fields = ["plant", "status", "customer_code"]
    search_fields = ["number", "customer_code", "customer_name"]


class SalesOrderLineViewSet(BaseModelViewSet):
    queryset = SalesOrderLine.objects.select_related("sales_order", "item")
    serializer_class = s.SalesOrderLineSerializer
    filterset_fields = ["sales_order", "item", "requested_date"]


class MasterProductionScheduleViewSet(BaseModelViewSet):
    queryset = MasterProductionSchedule.objects.select_related("plant", "item")
    serializer_class = s.MasterProductionScheduleSerializer
    filterset_fields = ["plant", "item", "status", "due_date"]
    search_fields = ["item__code", "source"]


class WorkOrderViewSet(BaseModelViewSet):
    permission_required_by_action = {
        "materialize": "production.change_workorder",
        "release": "production.change_workorder",
        "complete": "production.add_workordercompletion",
    }
    queryset = WorkOrder.objects.select_related("plant", "item", "routing").prefetch_related(
        "materials", "operations", "completions"
    )
    serializer_class = s.WorkOrderSerializer
    filterset_fields = ["plant", "item", "status", "release_date", "due_date"]
    search_fields = ["number", "item__code"]

    @action(detail=True, methods=["post"])
    def materialize(self, request, pk=None):
        order = materialize_work_order(self.get_object())
        return Response(self.get_serializer(order).data)

    @action(detail=True, methods=["post"])
    def release(self, request, pk=None):
        try:
            order = release_work_order(self.get_object())
        except DjangoValidationError as exc:
            _as_drf_validation(exc)
        return Response(self.get_serializer(order).data)

    @action(detail=True, methods=["post"], url_path="complete")
    def complete(self, request, pk=None):
        payload = s.WorkOrderCompletionCommandSerializer(data=request.data)
        payload.is_valid(raise_exception=True)
        try:
            completion, created = complete_work_order(
                work_order=self.get_object(),
                actor=request.user,
                **payload.validated_data,
            )
        except DjangoValidationError as exc:
            _as_drf_validation(exc)
        completion.work_order.refresh_from_db()
        return Response(
            {
                "created": created,
                "completion": s.WorkOrderCompletionSerializer(completion).data,
                "work_order": self.get_serializer(completion.work_order).data,
            },
            status=status.HTTP_201_CREATED if created else status.HTTP_200_OK,
        )


class WorkOrderMaterialViewSet(viewsets.ReadOnlyModelViewSet):
    queryset = WorkOrderMaterial.objects.select_related("work_order", "item")
    serializer_class = s.WorkOrderMaterialSerializer
    filterset_fields = ["work_order", "item"]


class WorkOrderOperationViewSet(BaseModelViewSet):
    queryset = WorkOrderOperation.objects.select_related("work_order", "work_center")
    serializer_class = s.WorkOrderOperationSerializer
    filterset_fields = ["work_order", "work_center", "status"]


class ProductionReportViewSet(BaseModelViewSet):
    queryset = ProductionReport.objects.select_related("work_order", "operation")
    serializer_class = s.ProductionReportSerializer
    filterset_fields = ["work_order", "operation"]


class WorkOrderCompletionViewSet(viewsets.ReadOnlyModelViewSet):
    queryset = WorkOrderCompletion.objects.select_related(
        "work_order", "destination_location", "receipt_transaction"
    )
    serializer_class = s.WorkOrderCompletionSerializer
    filterset_fields = ["work_order", "idempotency_key", "closed_order"]


class PurchaseOrderViewSet(BaseModelViewSet):
    queryset = PurchaseOrder.objects.select_related("plant", "supplier").prefetch_related("lines")
    serializer_class = s.PurchaseOrderSerializer
    filterset_fields = ["plant", "supplier", "status", "expected_date"]
    search_fields = ["number", "supplier__code", "supplier__name"]


class PurchaseOrderLineViewSet(BaseModelViewSet):
    permission_required_by_action = {"receive": "purchasing.add_goodsreceipt"}
    queryset = PurchaseOrderLine.objects.select_related("purchase_order", "item")
    serializer_class = s.PurchaseOrderLineSerializer
    filterset_fields = ["purchase_order", "item", "expected_date"]

    @action(detail=True, methods=["post"], url_path="receive")
    def receive(self, request, pk=None):
        payload = s.PurchaseReceiptCommandSerializer(data=request.data)
        payload.is_valid(raise_exception=True)
        try:
            receipt, created = receive_purchase_order_line(
                line=self.get_object(),
                actor=request.user,
                **payload.validated_data,
            )
        except DjangoValidationError as exc:
            _as_drf_validation(exc)
        receipt.purchase_order_line.refresh_from_db()
        return Response(
            {
                "created": created,
                "receipt": s.GoodsReceiptSerializer(receipt).data,
                "purchase_order_line": self.get_serializer(receipt.purchase_order_line).data,
                "purchase_order_status": receipt.purchase_order_line.purchase_order.status,
            },
            status=status.HTTP_201_CREATED if created else status.HTTP_200_OK,
        )


class GoodsReceiptViewSet(viewsets.ReadOnlyModelViewSet):
    queryset = GoodsReceipt.objects.select_related(
        "purchase_order_line",
        "purchase_order_line__item",
        "destination_location",
        "inventory_transaction",
    )
    serializer_class = s.GoodsReceiptSerializer
    filterset_fields = ["purchase_order_line", "receipt_number", "idempotency_key"]


class PlanningRunViewSet(BaseModelViewSet):
    permission_required_by_action = {
        "net_change": "planning.add_planningrun",
        "execute": "planning.change_planningrun",
        "crp": "planning.add_capacityscenario",
        "summary": "planning.view_planningrun",
    }
    queryset = PlanningRun.objects.select_related("plant")
    serializer_class = s.PlanningRunSerializer
    filterset_fields = ["plant", "status"]

    @action(detail=False, methods=["post"], url_path="net-change")
    def net_change(self, request):
        payload = s.NetChangeRequestSerializer(data=request.data)
        payload.is_valid(raise_exception=True)
        data = payload.validated_data
        try:
            run = execute_net_change_run(
                plant=data["plant"],
                horizon_start=data["horizon_start"],
                horizon_end=data["horizon_end"],
                name=data.get("name") or "MRP net-change",
                parameters={
                    "include_sales_orders": data["include_sales_orders"],
                    "include_forecasts": data["include_forecasts"],
                },
            )
        except DjangoValidationError as exc:
            _as_drf_validation(exc)
        return Response(self.get_serializer(run).data, status=status.HTTP_201_CREATED)

    @action(detail=True, methods=["post"])
    def execute(self, request, pk=None):
        run = execute_planning_run(self.get_object())
        return Response(self.get_serializer(run).data)

    @action(detail=True, methods=["post"], url_path="crp")
    def crp(self, request, pk=None):
        run = self.get_object()
        scenario = CapacityScenario.objects.create(
            name=request.data.get("name") or f"CRP {run.name}",
            scenario_type=CapacityScenario.ScenarioType.CRP,
            plant=run.plant,
            planning_run=run,
            parameters={
                "include_open_orders": request.data.get("include_open_orders", True),
                "capacity_overrides": request.data.get("capacity_overrides", {}),
            },
        )
        try:
            scenario = execute_capacity_scenario(scenario)
        except DjangoValidationError as exc:
            _as_drf_validation(exc)
        return Response(
            {
                "scenario": s.CapacityScenarioSerializer(scenario).data,
                "bottlenecks": capacity_bottleneck_summary(scenario),
            },
            status=status.HTTP_201_CREATED,
        )

    @action(detail=True, methods=["get"])
    def summary(self, request, pk=None):
        run = self.get_object()
        return Response(
            {
                "run": self.get_serializer(run).data,
                "planned_orders": run.planned_orders.count(),
                "buckets": run.buckets.count(),
                "pegging_records": run.pegging_records.count(),
                "messages": run.messages.count(),
                "capacity_scenarios": run.capacity_scenarios.count(),
            }
        )


class PlanningBucketViewSet(viewsets.ReadOnlyModelViewSet):
    queryset = PlanningBucket.objects.select_related("planning_run", "item")
    serializer_class = s.PlanningBucketSerializer
    filterset_fields = ["planning_run", "item", "bucket_date"]
    search_fields = ["item__code"]


class PlannedOrderViewSet(viewsets.ReadOnlyModelViewSet):
    permission_required_by_action = {"convert": "planning.change_plannedorder"}
    queryset = PlannedOrder.objects.select_related("planning_run", "planning_run__plant", "item")
    serializer_class = s.PlannedOrderSerializer
    filterset_fields = ["planning_run", "item", "order_type", "status", "release_date", "due_date"]
    search_fields = ["item__code"]

    @action(detail=True, methods=["post"])
    def convert(self, request, pk=None):
        order = self.get_object()
        document = convert_planned_order(order)
        return Response(
            {
                "planned_order": self.get_serializer(order).data,
                "document_type": order.converted_document_type,
                "document_id": document.id,
            },
            status=status.HTTP_201_CREATED,
        )


class DemandPeggingAllocationViewSet(viewsets.ReadOnlyModelViewSet):
    queryset = DemandPeggingAllocation.objects.select_related("planned_order", "sales_order_line__sales_order", "top_level_item")
    serializer_class = s.DemandPeggingAllocationSerializer
    filterset_fields = ["planned_order", "source_type", "sales_order_line", "top_level_item"]
    search_fields = ["sales_order_line__sales_order__number", "top_level_item__code"]


class PeggingRecordViewSet(viewsets.ReadOnlyModelViewSet):
    queryset = PeggingRecord.objects.select_related(
        "planning_run", "component_item", "parent_item", "parent_planned_order", "top_level_item"
    )
    serializer_class = s.PeggingRecordSerializer
    filterset_fields = ["planning_run", "component_item", "parent_item", "top_level_item"]
    search_fields = ["component_item__code", "parent_item__code", "top_level_item__code"]


class PlanningMessageViewSet(viewsets.ReadOnlyModelViewSet):
    queryset = PlanningMessage.objects.select_related("planning_run", "item", "planned_order")
    serializer_class = s.PlanningMessageSerializer
    filterset_fields = [
        "planning_run",
        "item",
        "message_type",
        "severity",
        "action_date",
        "suggested_date",
        "reference_type",
        "reference_id",
    ]


class PlanningChangeViewSet(viewsets.ReadOnlyModelViewSet):
    queryset = PlanningChange.objects.select_related("plant", "item", "planning_run")
    serializer_class = s.PlanningChangeSerializer
    filterset_fields = ["plant", "item", "change_type", "status", "source_type", "source_id"]
    search_fields = ["source_type", "source_id", "idempotency_key", "item__code"]


class CapacityScenarioViewSet(BaseModelViewSet):
    permission_required_by_action = {
        "execute": "planning.change_capacityscenario",
        "bottlenecks": "planning.view_capacityscenario",
        "what_if": "planning.add_capacityscenario",
    }
    queryset = CapacityScenario.objects.select_related("plant", "planning_run", "item")
    serializer_class = s.CapacityScenarioSerializer
    filterset_fields = ["plant", "planning_run", "item", "scenario_type", "status", "feasible"]
    search_fields = ["name", "item__code"]

    @action(detail=True, methods=["post"])
    def execute(self, request, pk=None):
        try:
            scenario = execute_capacity_scenario(self.get_object())
        except DjangoValidationError as exc:
            _as_drf_validation(exc)
        return Response(self.get_serializer(scenario).data)

    @action(detail=True, methods=["get"])
    def bottlenecks(self, request, pk=None):
        return Response(capacity_bottleneck_summary(self.get_object()))

    @action(detail=False, methods=["post"], url_path="what-if")
    def what_if(self, request):
        payload = s.WhatIfRequestSerializer(data=request.data)
        payload.is_valid(raise_exception=True)
        data = payload.validated_data
        item = data.pop("item")
        scenario = CapacityScenario.objects.create(
            name=data.get("name") or f"What-if {item.code}",
            scenario_type=CapacityScenario.ScenarioType.WHAT_IF,
            plant=data["plant"],
            item=item,
            quantity=data["quantity"],
            requested_release_date=data["release_date"],
            requested_due_date=data["due_date"],
            parameters={
                "include_open_orders": data["include_open_orders"],
                "capacity_overrides": data["capacity_overrides"],
            },
        )
        try:
            scenario = execute_capacity_scenario(scenario)
        except DjangoValidationError as exc:
            _as_drf_validation(exc)
        return Response(
            {
                "scenario": self.get_serializer(scenario).data,
                "bottlenecks": capacity_bottleneck_summary(scenario),
            },
            status=status.HTTP_201_CREATED,
        )


class CapacityAllocationViewSet(viewsets.ReadOnlyModelViewSet):
    queryset = CapacityAllocation.objects.select_related("scenario", "work_center", "item")
    serializer_class = s.CapacityAllocationSerializer
    filterset_fields = [
        "scenario",
        "work_center",
        "item",
        "source_type",
        "source_id",
        "load_date",
        "week_start",
        "is_existing_load",
    ]
    search_fields = ["work_center__code", "item__code", "source_id"]


class EngineeringChangeViewSet(BaseModelViewSet):
    queryset = EngineeringChange.objects.select_related("plant","requested_by","approved_by").prefetch_related("items","approvals","impacts")
    serializer_class = s.EngineeringChangeSerializer
    filterset_fields = ["plant","status","effectivity_type","effective_date"]
    search_fields = ["number","title","reason"]
    permission_required_by_action = {"approve":"engineering.approve_engineeringchange","activate":"engineering.activate_engineeringchange"}
    def perform_create(self, serializer): serializer.save(requested_by=self.request.user if self.request.user.is_authenticated else None)
    @action(detail=True, methods=["post"], url_path="analyze-impact")
    def analyze(self, request, pk=None):
        try: obj=analyze_impact(self.get_object(),request.user if request.user.is_authenticated else None)
        except DjangoValidationError as exc: _as_drf_validation(exc)
        return Response(self.get_serializer(obj).data)
    @action(detail=True, methods=["post"])
    def submit(self, request, pk=None):
        try: obj=submit_change(self.get_object(),request.user if request.user.is_authenticated else None)
        except DjangoValidationError as exc: _as_drf_validation(exc)
        return Response(self.get_serializer(obj).data)
    @action(detail=True, methods=["post"])
    def approve(self, request, pk=None):
        data=s.DecisionSerializer(data=request.data); data.is_valid(raise_exception=True)
        try: obj=approve_change(self.get_object(),request.user,data.validated_data.get("comment",""))
        except DjangoValidationError as exc: _as_drf_validation(exc)
        return Response(self.get_serializer(obj).data)
    @action(detail=True, methods=["post"])
    def reject(self, request, pk=None):
        data=s.DecisionSerializer(data=request.data); data.is_valid(raise_exception=True)
        try: obj=reject_change(self.get_object(),request.user,data.validated_data.get("comment",""))
        except DjangoValidationError as exc: _as_drf_validation(exc)
        return Response(self.get_serializer(obj).data)
    @action(detail=True, methods=["post"])
    def activate(self, request, pk=None):
        try: obj=activate_change(self.get_object(),request.user if request.user.is_authenticated else None)
        except DjangoValidationError as exc: _as_drf_validation(exc)
        return Response(self.get_serializer(obj).data)

class EngineeringChangeItemViewSet(BaseModelViewSet):
    queryset=EngineeringChangeItem.objects.select_related("change","affected_item","replacement_item"); serializer_class=s.EngineeringChangeItemSerializer; filterset_fields=["change","affected_item","action"]
class EngineeringChangeApprovalViewSet(BaseModelViewSet):
    queryset=EngineeringChangeApproval.objects.select_related("change","approver"); serializer_class=s.EngineeringChangeApprovalSerializer; filterset_fields=["change","decision","role"]
class EngineeringImpactViewSet(viewsets.ReadOnlyModelViewSet):
    queryset=EngineeringImpact.objects.select_related("change"); serializer_class=s.EngineeringImpactSerializer; filterset_fields=["change","impact_type","severity"]
class BOMRevisionViewSet(BaseModelViewSet):
    queryset=BOMRevision.objects.select_related("plant","parent","change").prefetch_related("lines"); serializer_class=s.BOMRevisionSerializer; filterset_fields=["plant","parent","status","change"]
class BOMRevisionLineViewSet(BaseModelViewSet):
    queryset=BOMRevisionLine.objects.select_related("revision","component"); serializer_class=s.BOMRevisionLineSerializer; filterset_fields=["revision","component"]
class RoutingRevisionViewSet(BaseModelViewSet):
    queryset=RoutingRevision.objects.select_related("plant","item","routing","change"); serializer_class=s.RoutingRevisionSerializer; filterset_fields=["plant","item","status","change"]


class InventoryLotViewSet(BaseModelViewSet):
    queryset = InventoryLot.objects.select_related("plant", "item", "supplier")
    serializer_class = s.InventoryLotSerializer
    filterset_fields = ["plant", "item", "supplier", "status", "expiration_date", "source_type", "source_id"]
    search_fields = ["lot_number", "item__code", "source_id"]
    permission_required_by_action = {"post_transaction": "traceability.add_lottransaction", "change_status": "traceability.change_inventorylot"}

    @action(detail=True, methods=["post"], url_path="post-transaction")
    def post_transaction(self, request, pk=None):
        payload = s.LotPostCommandSerializer(data=request.data); payload.is_valid(raise_exception=True)
        try:
            row = post_lot_transaction(lot=self.get_object(), user=request.user if request.user.is_authenticated else None, **payload.validated_data)
        except DjangoValidationError as exc: _as_drf_validation(exc)
        return Response(s.LotTransactionSerializer(row).data, status=status.HTTP_201_CREATED)

    @action(detail=True, methods=["post"], url_path="change-status")
    def change_status(self, request, pk=None):
        payload = s.LotStatusCommandSerializer(data=request.data); payload.is_valid(raise_exception=True)
        try:
            obj = change_lot_status(lot=self.get_object(), user=request.user if request.user.is_authenticated else None, **payload.validated_data)
        except DjangoValidationError as exc: _as_drf_validation(exc)
        return Response(self.get_serializer(obj).data)

    @action(detail=True, methods=["get"], url_path="genealogy")
    def genealogy(self, request, pk=None):
        lot = self.get_object()
        serials = SerialNumber.objects.filter(lot=lot).select_related("item", "lot")
        return Response({"lot": self.get_serializer(lot).data, "serials": s.SerialNumberSerializer(serials, many=True).data})

class LotBalanceViewSet(viewsets.ReadOnlyModelViewSet):
    queryset = LotBalance.objects.select_related("lot", "lot__item", "location")
    serializer_class = s.LotBalanceSerializer
    filterset_fields = ["lot", "location", "lot__item", "lot__status"]

class LotTransactionViewSet(viewsets.ReadOnlyModelViewSet):
    queryset = LotTransaction.objects.select_related("lot", "from_location", "to_location", "posted_by")
    serializer_class = s.LotTransactionSerializer
    filterset_fields = ["lot", "transaction_type", "reference_type", "reference_id", "posted_at"]
    search_fields = ["idempotency_key", "reference_id", "lot__lot_number"]

class LotReservationViewSet(BaseModelViewSet):
    queryset = LotReservation.objects.select_related("lot", "location")
    serializer_class = s.LotReservationSerializer
    filterset_fields = ["lot", "location", "status", "demand_type", "demand_id", "required_date"]

class SerialNumberViewSet(BaseModelViewSet):
    queryset = SerialNumber.objects.select_related("plant", "item", "lot", "current_location")
    serializer_class = s.SerialNumberSerializer
    filterset_fields = ["plant", "item", "lot", "status", "source_type", "source_id"]
    search_fields = ["serial_number", "item__code", "source_id"]

    @action(detail=True, methods=["post"], url_path="post-transaction")
    def post_transaction(self, request, pk=None):
        payload = s.SerialPostCommandSerializer(data=request.data); payload.is_valid(raise_exception=True)
        try:
            row = post_serial_transaction(serial=self.get_object(), user=request.user if request.user.is_authenticated else None, **payload.validated_data)
        except DjangoValidationError as exc: _as_drf_validation(exc)
        return Response(s.SerialTransactionSerializer(row).data, status=status.HTTP_201_CREATED)

    @action(detail=True, methods=["post"], url_path="install-component")
    def install_component_action(self, request, pk=None):
        payload = s.InstallComponentCommandSerializer(data=request.data); payload.is_valid(raise_exception=True)
        try:
            row = install_component(parent_serial=self.get_object(), user=request.user if request.user.is_authenticated else None, **payload.validated_data)
        except DjangoValidationError as exc: _as_drf_validation(exc)
        return Response(s.SerialComponentSerializer(row).data, status=status.HTTP_201_CREATED)

    @action(detail=True, methods=["get"], url_path="genealogy")
    def genealogy(self, request, pk=None):
        return Response(serial_genealogy(self.get_object()))

    @action(detail=True, methods=["get"], url_path="where-used")
    def where_used(self, request, pk=None):
        rows = self.get_object().where_installed.filter(removed_at__isnull=True).select_related("parent_serial", "parent_serial__item")
        return Response(s.SerialComponentSerializer(rows, many=True).data)

class SerialTransactionViewSet(viewsets.ReadOnlyModelViewSet):
    queryset = SerialTransaction.objects.select_related("serial", "from_location", "to_location", "posted_by")
    serializer_class = s.SerialTransactionSerializer
    filterset_fields = ["serial", "transaction_type", "reference_type", "reference_id", "posted_at"]

class SerialComponentViewSet(viewsets.ReadOnlyModelViewSet):
    queryset = SerialComponent.objects.select_related("parent_serial", "component_serial")
    serializer_class = s.SerialComponentSerializer
    filterset_fields = ["parent_serial", "component_serial", "work_order_id", "removed_at"]

from apps.quality.models import Disposition, InspectionCharacteristic, InspectionOrder, InspectionPlan, InspectionResult, NonConformance
from apps.quality.services import apply_disposition, complete_inspection, record_result, start_inspection

class InspectionPlanViewSet(BaseModelViewSet):
    queryset = InspectionPlan.objects.select_related("item")
    serializer_class = s.InspectionPlanSerializer
    filterset_fields = ["item", "source_type", "revision", "is_active"]
    search_fields = ["code", "description", "item__code"]

class InspectionCharacteristicViewSet(BaseModelViewSet):
    queryset = InspectionCharacteristic.objects.select_related("plan")
    serializer_class = s.InspectionCharacteristicSerializer
    filterset_fields = ["plan", "data_type", "is_mandatory"]

class InspectionOrderViewSet(BaseModelViewSet):
    queryset = InspectionOrder.objects.select_related("plant", "plan", "item", "lot", "serial", "supplier", "inspector").prefetch_related("results")
    serializer_class = s.InspectionOrderSerializer
    filterset_fields = ["plant", "plan", "item", "lot", "serial", "supplier", "status", "source_type", "source_id"]
    search_fields = ["source_id", "item__code", "lot__lot_number", "serial__serial_number"]
    permission_required_by_action = {"start": "quality.change_inspectionorder", "record_result": "quality.add_inspectionresult", "complete": "quality.change_inspectionorder"}

    @action(detail=True, methods=["post"])
    def start(self, request, pk=None):
        try: obj = start_inspection(order=self.get_object(), user=request.user if request.user.is_authenticated else None)
        except DjangoValidationError as exc: _as_drf_validation(exc)
        return Response(self.get_serializer(obj).data)

    @action(detail=True, methods=["post"], url_path="record-result")
    def record_result(self, request, pk=None):
        payload = s.InspectionResultCommandSerializer(data=request.data); payload.is_valid(raise_exception=True)
        try: row = record_result(order=self.get_object(), user=request.user if request.user.is_authenticated else None, **payload.validated_data)
        except DjangoValidationError as exc: _as_drf_validation(exc)
        return Response(s.InspectionResultSerializer(row).data, status=status.HTTP_201_CREATED)

    @action(detail=True, methods=["post"])
    def complete(self, request, pk=None):
        payload = s.InspectionCompleteCommandSerializer(data=request.data); payload.is_valid(raise_exception=True)
        try: obj = complete_inspection(order=self.get_object(), user=request.user if request.user.is_authenticated else None, **payload.validated_data)
        except DjangoValidationError as exc: _as_drf_validation(exc)
        return Response(self.get_serializer(obj).data)

class InspectionResultViewSet(viewsets.ReadOnlyModelViewSet):
    queryset = InspectionResult.objects.select_related("order", "characteristic", "measured_by")
    serializer_class = s.InspectionResultSerializer
    filterset_fields = ["order", "characteristic", "is_conforming", "measured_by"]

class NonConformanceViewSet(BaseModelViewSet):
    queryset = NonConformance.objects.select_related("inspection_order", "plant", "item", "lot", "serial", "supplier", "opened_by")
    serializer_class = s.NonConformanceSerializer
    filterset_fields = ["plant", "item", "lot", "serial", "supplier", "severity", "status"]
    search_fields = ["number", "description", "item__code", "lot__lot_number"]

    @action(detail=True, methods=["post"])
    def dispose(self, request, pk=None):
        payload = s.DispositionCommandSerializer(data=request.data); payload.is_valid(raise_exception=True)
        try: row = apply_disposition(nonconformance=self.get_object(), user=request.user if request.user.is_authenticated else None, **payload.validated_data)
        except DjangoValidationError as exc: _as_drf_validation(exc)
        return Response(s.DispositionSerializer(row).data, status=status.HTTP_201_CREATED)

class DispositionViewSet(viewsets.ReadOnlyModelViewSet):
    queryset = Disposition.objects.select_related("nonconformance", "approved_by")
    serializer_class = s.DispositionSerializer
    filterset_fields = ["nonconformance", "decision", "approved_by"]

from apps.recall.models import RecallAction, RecallAffectedUnit, RecallCase, RecallCriterion
from apps.recall.services import analyze_recall, approve_recall, complete_recall, execute_recall

class RecallCaseViewSet(BaseModelViewSet):
    queryset = RecallCase.objects.select_related("plant", "supplier", "nonconformance", "opened_by", "approved_by").prefetch_related("criteria", "affected_units")
    serializer_class = s.RecallCaseSerializer
    filterset_fields = ["plant", "classification", "status", "supplier", "nonconformance"]
    search_fields = ["number", "title", "description", "reason"]
    permission_required_by_action = {"approve": "recall.approve_recallcase", "execute": "recall.execute_recallcase"}

    def perform_create(self, serializer):
        serializer.save(opened_by=self.request.user if self.request.user.is_authenticated else None)

    @action(detail=True, methods=["post"], url_path="analyze")
    def analyze(self, request, pk=None):
        payload = s.RecallAnalyzeCommandSerializer(data=request.data); payload.is_valid(raise_exception=True)
        try: result = analyze_recall(case=self.get_object(), actor=request.user if request.user.is_authenticated else None, **payload.validated_data)
        except DjangoValidationError as exc: _as_drf_validation(exc)
        return Response(result)

    @action(detail=True, methods=["post"])
    def approve(self, request, pk=None):
        try: obj = approve_recall(case=self.get_object(), actor=request.user)
        except DjangoValidationError as exc: _as_drf_validation(exc)
        return Response(self.get_serializer(obj).data)

    @action(detail=True, methods=["post"])
    def execute(self, request, pk=None):
        try: result = execute_recall(case=self.get_object(), actor=request.user if request.user.is_authenticated else None)
        except DjangoValidationError as exc: _as_drf_validation(exc)
        return Response(result)

    @action(detail=True, methods=["post"])
    def complete(self, request, pk=None):
        try: obj = complete_recall(case=self.get_object(), actor=request.user if request.user.is_authenticated else None)
        except DjangoValidationError as exc: _as_drf_validation(exc)
        return Response(self.get_serializer(obj).data)

    @action(detail=True, methods=["get"], url_path="summary")
    def summary(self, request, pk=None):
        case = self.get_object()
        return Response({
            "case": case.number,
            "status": case.status,
            "affected_units": case.affected_units.count(),
            "serials": case.affected_units.exclude(serial__isnull=True).count(),
            "lots": case.affected_units.filter(serial__isnull=True).exclude(lot__isnull=True).count(),
            "pending_disposition": case.affected_units.filter(disposition__in=["PENDING", "BLOCKED"]).count(),
            "actions_open": case.actions.exclude(status__in=["DONE", "CANCELLED"]).count(),
        })

class RecallCriterionViewSet(BaseModelViewSet):
    queryset = RecallCriterion.objects.select_related("recall_case", "item", "lot", "serial", "supplier")
    serializer_class = s.RecallCriterionSerializer
    filterset_fields = ["recall_case", "criterion_type", "item", "lot", "serial", "supplier"]

class RecallAffectedUnitViewSet(BaseModelViewSet):
    queryset = RecallAffectedUnit.objects.select_related("recall_case", "item", "lot", "serial")
    serializer_class = s.RecallAffectedUnitSerializer
    filterset_fields = ["recall_case", "item", "lot", "serial", "source", "disposition"]
    http_method_names = ["get", "patch", "head", "options"]

class RecallActionViewSet(BaseModelViewSet):
    queryset = RecallAction.objects.select_related("recall_case", "affected_unit", "owner")
    serializer_class = s.RecallActionSerializer
    filterset_fields = ["recall_case", "affected_unit", "action_type", "status", "owner", "due_date"]


# 0.7.6 deliveries
from apps.demand.models import SalesDelivery, SalesDeliveryLine
from .serializers import SalesDeliverySerializer, SalesDeliveryLineSerializer
class SalesDeliveryViewSet(viewsets.ModelViewSet):
    queryset=SalesDelivery.objects.select_related("plant").prefetch_related("lines").all()
    serializer_class=SalesDeliverySerializer
    filterset_fields=["plant","delivery_date","number"]
class SalesDeliveryLineViewSet(viewsets.ModelViewSet):
    queryset=SalesDeliveryLine.objects.select_related("delivery","sales_order_line__sales_order","sales_order_line__item").all()
    serializer_class=SalesDeliveryLineSerializer
    filterset_fields=["delivery","sales_order_line"]
