from django.db import transaction
from django.utils import timezone
from rest_framework import status, viewsets
from rest_framework.decorators import action
from rest_framework.response import Response
from .models import CostVersion, WorkCenterRate, ItemCost, CostRollupRun, WorkOrderCost, CostVariance, PurchasePriceVariance
from .serializers import CostVersionSerializer, WorkCenterRateSerializer, ItemCostSerializer, CostRollupRunSerializer, WorkOrderCostSerializer, CostVarianceSerializer, PurchasePriceVarianceSerializer
from .services.rollup import run_rollup
from .services.work_order_cost import calculate_planned_cost, calculate_actual_cost
from .services.variances import calculate_variances
from .services.purchase_variance import calculate_purchase_price_variance
from apps.production.models import WorkOrder
from apps.purchasing.models import GoodsReceipt

class CostVersionViewSet(viewsets.ModelViewSet):
    queryset = CostVersion.objects.select_related("plant", "approved_by")
    serializer_class = CostVersionSerializer
    filterset_fields = ["plant", "status"]
    @action(detail=True, methods=["post"])
    def calculate(self, request, pk=None):
        run = run_rollup(self.get_object()); return Response(CostRollupRunSerializer(run).data)
    @action(detail=True, methods=["post"])
    def approve(self, request, pk=None):
        obj = self.get_object()
        if obj.status != CostVersion.Status.CALCULATED: return Response({"detail":"Calcule antes de aprovar."}, status=409)
        obj.status = CostVersion.Status.APPROVED; obj.approved_at = timezone.now(); obj.approved_by = request.user; obj.save(); return Response(self.get_serializer(obj).data)
    @action(detail=True, methods=["post"])
    @transaction.atomic
    def activate(self, request, pk=None):
        obj = self.get_object()
        if obj.status != CostVersion.Status.APPROVED: return Response({"detail":"Apenas versões aprovadas podem ser ativadas."}, status=409)
        CostVersion.objects.filter(plant=obj.plant, status=CostVersion.Status.ACTIVE).exclude(pk=obj.pk).update(status=CostVersion.Status.CLOSED)
        obj.status = CostVersion.Status.ACTIVE; obj.save(update_fields=["status", "updated_at"]); return Response(self.get_serializer(obj).data)

class WorkCenterRateViewSet(viewsets.ModelViewSet):
    queryset = WorkCenterRate.objects.select_related("cost_version", "work_center"); serializer_class = WorkCenterRateSerializer; filterset_fields = ["cost_version", "work_center"]
class ItemCostViewSet(viewsets.ReadOnlyModelViewSet):
    queryset = ItemCost.objects.select_related("cost_version", "item"); serializer_class = ItemCostSerializer; filterset_fields = ["cost_version", "item", "level"]
class CostRollupRunViewSet(viewsets.ReadOnlyModelViewSet):
    queryset = CostRollupRun.objects.select_related("cost_version"); serializer_class = CostRollupRunSerializer; filterset_fields = ["cost_version", "status"]
class WorkOrderCostViewSet(viewsets.ReadOnlyModelViewSet):
    queryset = WorkOrderCost.objects.select_related("work_order", "cost_version").prefetch_related("lines")
    serializer_class = WorkOrderCostSerializer; filterset_fields = ["work_order", "cost_version", "cost_type"]
    @action(detail=False, methods=["post"], url_path="calculate-planned")
    def calculate_planned(self, request):
        wo = WorkOrder.objects.get(pk=request.data["work_order"]); return Response(self.get_serializer(calculate_planned_cost(wo)).data)
    @action(detail=False, methods=["post"], url_path="calculate-actual")
    def calculate_actual(self, request):
        wo = WorkOrder.objects.get(pk=request.data["work_order"]); return Response(self.get_serializer(calculate_actual_cost(wo)).data)
    @action(detail=False, methods=["post"], url_path="calculate-variances")
    def variances(self, request):
        wo = WorkOrder.objects.get(pk=request.data["work_order"]); return Response(CostVarianceSerializer(calculate_variances(wo), many=True).data)
class CostVarianceViewSet(viewsets.ReadOnlyModelViewSet):
    queryset = CostVariance.objects.select_related("work_order"); serializer_class = CostVarianceSerializer; filterset_fields = ["work_order", "variance_type", "favorable"]
class PurchasePriceVarianceViewSet(viewsets.ReadOnlyModelViewSet):
    queryset = PurchasePriceVariance.objects.select_related("goods_receipt", "cost_version"); serializer_class = PurchasePriceVarianceSerializer; filterset_fields = ["cost_version", "favorable"]
    @action(detail=False, methods=["post"], url_path="calculate")
    def calculate(self, request):
        receipt = GoodsReceipt.objects.get(pk=request.data["goods_receipt"]); return Response(self.get_serializer(calculate_purchase_price_variance(receipt)).data)

from .models import AccountingPeriod, InventoryValuationSnapshot, WIPSnapshot
from .serializers import AccountingPeriodSerializer, InventoryValuationSnapshotSerializer, WIPSnapshotSerializer
from .services.valuation import create_inventory_valuation, create_wip_snapshot, close_accounting_period

class AccountingPeriodViewSet(viewsets.ModelViewSet):
    queryset = AccountingPeriod.objects.select_related("plant", "cost_version", "closed_by")
    serializer_class = AccountingPeriodSerializer
    filterset_fields = ["plant", "status", "cost_version"]

    @action(detail=True, methods=["post"], url_path="inventory-valuation")
    def inventory_valuation(self, request, pk=None):
        try:
            snapshot = create_inventory_valuation(self.get_object(), request.data.get("valuation_method", "STANDARD"))
            return Response(InventoryValuationSnapshotSerializer(snapshot).data)
        except ValueError as exc:
            return Response({"detail": str(exc)}, status=status.HTTP_409_CONFLICT)

    @action(detail=True, methods=["post"], url_path="wip-valuation")
    def wip_valuation(self, request, pk=None):
        try:
            return Response(WIPSnapshotSerializer(create_wip_snapshot(self.get_object())).data)
        except ValueError as exc:
            return Response({"detail": str(exc)}, status=status.HTTP_409_CONFLICT)

    @action(detail=True, methods=["post"], url_path="close")
    def close_period(self, request, pk=None):
        try:
            return Response(self.get_serializer(close_accounting_period(self.get_object(), request.user)).data)
        except ValueError as exc:
            return Response({"detail": str(exc)}, status=status.HTTP_409_CONFLICT)

class InventoryValuationSnapshotViewSet(viewsets.ReadOnlyModelViewSet):
    queryset = InventoryValuationSnapshot.objects.select_related("period", "cost_version").prefetch_related("lines")
    serializer_class = InventoryValuationSnapshotSerializer
    filterset_fields = ["period", "cost_version", "valuation_method"]

class WIPSnapshotViewSet(viewsets.ReadOnlyModelViewSet):
    queryset = WIPSnapshot.objects.select_related("period", "cost_version").prefetch_related("lines")
    serializer_class = WIPSnapshotSerializer
    filterset_fields = ["period", "cost_version"]


from .models import MovingAverageCostBalance, InventoryCostMovement, CostLedgerEntry, PeriodVariancePosting
from .serializers import MovingAverageCostBalanceSerializer, InventoryCostMovementSerializer, CostLedgerEntrySerializer, PeriodVariancePostingSerializer
from .services.moving_average import post_moving_average_cost, rebuild_moving_average
from .services.accounting import post_period_variances
from apps.inventory.models import InventoryTransaction

class MovingAverageCostBalanceViewSet(viewsets.ReadOnlyModelViewSet):
    queryset = MovingAverageCostBalance.objects.select_related("plant", "item", "last_transaction")
    serializer_class = MovingAverageCostBalanceSerializer
    filterset_fields = ["plant", "item"]

    @action(detail=False, methods=["post"], url_path="post-transaction")
    def post_transaction(self, request):
        tx = InventoryTransaction.objects.get(pk=request.data["inventory_transaction"])
        movement, created = post_moving_average_cost(tx, request.data.get("unit_cost"))
        return Response(InventoryCostMovementSerializer(movement).data, status=status.HTTP_201_CREATED if created else status.HTTP_200_OK)

    @action(detail=False, methods=["post"], url_path="rebuild")
    def rebuild(self, request):
        plant_id=request.data["plant"]
        from apps.common.models import Plant
        count=rebuild_moving_average(Plant.objects.get(pk=plant_id))
        return Response({"processed_transactions": count})

class InventoryCostMovementViewSet(viewsets.ReadOnlyModelViewSet):
    queryset = InventoryCostMovement.objects.select_related("plant", "item", "transaction")
    serializer_class = InventoryCostMovementSerializer
    filterset_fields = ["plant", "item", "movement_type", "transaction"]

class CostLedgerEntryViewSet(viewsets.ReadOnlyModelViewSet):
    queryset = CostLedgerEntry.objects.select_related("period", "plant")
    serializer_class = CostLedgerEntrySerializer
    filterset_fields = ["period", "plant", "entry_type", "account_code", "posting_date"]

class PeriodVariancePostingViewSet(viewsets.ReadOnlyModelViewSet):
    queryset = PeriodVariancePosting.objects.select_related("period", "ledger_debit", "ledger_credit")
    serializer_class = PeriodVariancePostingSerializer
    filterset_fields = ["period", "variance_type", "favorable"]

    @action(detail=False, methods=["post"], url_path="post-period")
    def post_period(self, request):
        period = AccountingPeriod.objects.get(pk=request.data["period"])
        return Response(self.get_serializer(post_period_variances(period), many=True).data)

from .models import (
    InventoryRevaluation, FinancialInventoryAdjustment, LotActualCost, SerialActualCost,
    InventoryReconciliationRun,
)
from .serializers import (
    InventoryRevaluationSerializer, FinancialInventoryAdjustmentSerializer,
    LotActualCostSerializer, SerialActualCostSerializer, InventoryReconciliationRunSerializer,
)
from .services.revaluation import revalue_item, post_financial_adjustment
from .services.actual_traceability import calculate_lot_actual_cost, calculate_serial_actual_cost
from .services.reconciliation import reconcile_inventory
from apps.masterdata.models import Item
from apps.traceability.models import InventoryLot, SerialNumber
from apps.common.models import Plant

class InventoryRevaluationViewSet(viewsets.ReadOnlyModelViewSet):
    queryset = InventoryRevaluation.objects.select_related("plant", "item", "period", "posted_by")
    serializer_class = InventoryRevaluationSerializer
    filterset_fields = ["plant", "item", "period", "method"]

    @action(detail=False, methods=["post"], url_path="post")
    def post_revaluation(self, request):
        try:
            obj, created = revalue_item(
                plant=Plant.objects.get(pk=request.data["plant"]),
                item=Item.objects.get(pk=request.data["item"]),
                new_unit_cost=request.data["new_unit_cost"], reason=request.data["reason"],
                user=request.user, period=AccountingPeriod.objects.filter(pk=request.data.get("period")).first(),
                idempotency_key=request.data["idempotency_key"],
            )
            return Response(self.get_serializer(obj).data, status=status.HTTP_201_CREATED if created else status.HTTP_200_OK)
        except ValueError as exc:
            return Response({"detail": str(exc)}, status=status.HTTP_409_CONFLICT)

class FinancialInventoryAdjustmentViewSet(viewsets.ModelViewSet):
    queryset = FinancialInventoryAdjustment.objects.select_related("plant", "item", "location", "period")
    serializer_class = FinancialInventoryAdjustmentSerializer
    filterset_fields = ["plant", "item", "period", "status", "reason_code"]

    @action(detail=True, methods=["post"])
    def post(self, request, pk=None):
        try:
            return Response(self.get_serializer(post_financial_adjustment(self.get_object(), request.user)).data)
        except ValueError as exc:
            return Response({"detail": str(exc)}, status=status.HTTP_409_CONFLICT)

class LotActualCostViewSet(viewsets.ReadOnlyModelViewSet):
    queryset = LotActualCost.objects.select_related("lot", "lot__item", "cost_version")
    serializer_class = LotActualCostSerializer
    filterset_fields = ["lot", "cost_version"]

    @action(detail=False, methods=["post"], url_path="calculate")
    def calculate(self, request):
        obj = calculate_lot_actual_cost(InventoryLot.objects.get(pk=request.data["lot"]))
        return Response(self.get_serializer(obj).data)

class SerialActualCostViewSet(viewsets.ReadOnlyModelViewSet):
    queryset = SerialActualCost.objects.select_related("serial", "serial__item")
    serializer_class = SerialActualCostSerializer
    filterset_fields = ["serial"]

    @action(detail=False, methods=["post"], url_path="calculate")
    def calculate(self, request):
        obj = calculate_serial_actual_cost(SerialNumber.objects.get(pk=request.data["serial"]))
        return Response(self.get_serializer(obj).data)

class InventoryReconciliationRunViewSet(viewsets.ReadOnlyModelViewSet):
    queryset = InventoryReconciliationRun.objects.select_related("plant", "period", "created_by").prefetch_related("lines")
    serializer_class = InventoryReconciliationRunSerializer
    filterset_fields = ["plant", "period", "status"]

    @action(detail=False, methods=["post"], url_path="run")
    def run(self, request):
        obj = reconcile_inventory(
            plant=Plant.objects.get(pk=request.data["plant"]),
            period=AccountingPeriod.objects.filter(pk=request.data.get("period")).first(),
            user=request.user,
        )
        return Response(self.get_serializer(obj).data, status=status.HTTP_201_CREATED)

from .models import PeriodCloseRun, PeriodReopenRequest, CostLedgerReversal, CostPeriodAudit
from .serializers import PeriodCloseRunSerializer, PeriodReopenRequestSerializer, CostLedgerReversalSerializer, CostPeriodAuditSerializer
from .services.period_close import final_close_period, request_reopen, decide_reopen, apply_reopen, reverse_ledger_entry, period_cost_report

class PeriodCloseRunViewSet(viewsets.ReadOnlyModelViewSet):
    queryset = PeriodCloseRun.objects.select_related("period", "executed_by")
    serializer_class = PeriodCloseRunSerializer
    filterset_fields = ["period", "status", "strict_reconciliation"]

class PeriodReopenRequestViewSet(viewsets.ReadOnlyModelViewSet):
    queryset = PeriodReopenRequest.objects.select_related("period", "requested_by", "decided_by", "applied_by")
    serializer_class = PeriodReopenRequestSerializer
    filterset_fields = ["period", "status"]

    @action(detail=False, methods=["post"], url_path="request")
    def request_reopen_action(self, request):
        try:
            period = AccountingPeriod.objects.get(pk=request.data["period"])
            obj = request_reopen(period, request.data["reason"], request.user)
            return Response(self.get_serializer(obj).data, status=status.HTTP_201_CREATED)
        except ValueError as exc:
            return Response({"detail": str(exc)}, status=status.HTTP_409_CONFLICT)

    @action(detail=True, methods=["post"], url_path="approve")
    def approve(self, request, pk=None):
        try:
            return Response(self.get_serializer(decide_reopen(self.get_object(), True, request.user, request.data.get("notes", ""))).data)
        except ValueError as exc:
            return Response({"detail": str(exc)}, status=status.HTTP_409_CONFLICT)

    @action(detail=True, methods=["post"], url_path="reject")
    def reject(self, request, pk=None):
        try:
            return Response(self.get_serializer(decide_reopen(self.get_object(), False, request.user, request.data.get("notes", ""))).data)
        except ValueError as exc:
            return Response({"detail": str(exc)}, status=status.HTTP_409_CONFLICT)

    @action(detail=True, methods=["post"], url_path="apply")
    def apply(self, request, pk=None):
        try:
            return Response(self.get_serializer(apply_reopen(self.get_object(), request.user)).data)
        except ValueError as exc:
            return Response({"detail": str(exc)}, status=status.HTTP_409_CONFLICT)

class CostLedgerReversalViewSet(viewsets.ReadOnlyModelViewSet):
    queryset = CostLedgerReversal.objects.select_related("original_entry", "reversal_entry", "reversed_by")
    serializer_class = CostLedgerReversalSerializer
    filterset_fields = ["original_entry", "reversal_entry"]

    @action(detail=False, methods=["post"], url_path="reverse")
    def reverse(self, request):
        try:
            entry = CostLedgerEntry.objects.get(pk=request.data["ledger_entry"])
            obj = reverse_ledger_entry(entry, request.data["reason"], request.user)
            return Response(self.get_serializer(obj).data, status=status.HTTP_201_CREATED)
        except ValueError as exc:
            return Response({"detail": str(exc)}, status=status.HTTP_409_CONFLICT)

class CostPeriodAuditViewSet(viewsets.ReadOnlyModelViewSet):
    queryset = CostPeriodAudit.objects.select_related("period", "actor")
    serializer_class = CostPeriodAuditSerializer
    filterset_fields = ["period", "action", "actor"]

# Extensões da API de AccountingPeriod da 0.4.4.
def final_close(self, request, pk=None):
    try:
        run = final_close_period(self.get_object(), request.user, request.data.get("strict_reconciliation", False))
        return Response(PeriodCloseRunSerializer(run).data)
    except ValueError as exc:
        return Response({"detail": str(exc)}, status=status.HTTP_409_CONFLICT)

def cost_report(self, request, pk=None):
    return Response(period_cost_report(self.get_object()))

AccountingPeriodViewSet.final_close = action(detail=True, methods=["post"], url_path="final-close")(final_close)
AccountingPeriodViewSet.cost_report = action(detail=True, methods=["get"], url_path="cost-report")(cost_report)
