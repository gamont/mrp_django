from rest_framework import serializers
from .models import CostVersion, WorkCenterRate, ItemCost, CostRollupRun, WorkOrderCost, WorkOrderCostLine, CostVariance, PurchasePriceVariance

class CostVersionSerializer(serializers.ModelSerializer):
    class Meta:
        model = CostVersion; fields = "__all__"; read_only_fields = ["calculated_at", "approved_at", "approved_by"]
class WorkCenterRateSerializer(serializers.ModelSerializer):
    class Meta: model = WorkCenterRate; fields = "__all__"
class ItemCostSerializer(serializers.ModelSerializer):
    class Meta: model = ItemCost; fields = "__all__"
class CostRollupRunSerializer(serializers.ModelSerializer):
    class Meta: model = CostRollupRun; fields = "__all__"
class WorkOrderCostLineSerializer(serializers.ModelSerializer):
    class Meta: model = WorkOrderCostLine; fields = "__all__"
class WorkOrderCostSerializer(serializers.ModelSerializer):
    lines = WorkOrderCostLineSerializer(many=True, read_only=True)
    class Meta: model = WorkOrderCost; fields = "__all__"
class CostVarianceSerializer(serializers.ModelSerializer):
    class Meta: model = CostVariance; fields = "__all__"
class PurchasePriceVarianceSerializer(serializers.ModelSerializer):
    class Meta: model = PurchasePriceVariance; fields = "__all__"

from .models import AccountingPeriod, InventoryValuationSnapshot, InventoryValuationLine, WIPSnapshot, WIPLine

class AccountingPeriodSerializer(serializers.ModelSerializer):
    class Meta: model = AccountingPeriod; fields = "__all__"; read_only_fields = ["closed_at", "closed_by"]
class InventoryValuationLineSerializer(serializers.ModelSerializer):
    class Meta: model = InventoryValuationLine; fields = "__all__"
class InventoryValuationSnapshotSerializer(serializers.ModelSerializer):
    lines = InventoryValuationLineSerializer(many=True, read_only=True)
    class Meta: model = InventoryValuationSnapshot; fields = "__all__"
class WIPLineSerializer(serializers.ModelSerializer):
    class Meta: model = WIPLine; fields = "__all__"
class WIPSnapshotSerializer(serializers.ModelSerializer):
    lines = WIPLineSerializer(many=True, read_only=True)
    class Meta: model = WIPSnapshot; fields = "__all__"


from .models import MovingAverageCostBalance, InventoryCostMovement, CostLedgerEntry, PeriodVariancePosting

class MovingAverageCostBalanceSerializer(serializers.ModelSerializer):
    class Meta: model = MovingAverageCostBalance; fields = "__all__"
class InventoryCostMovementSerializer(serializers.ModelSerializer):
    class Meta: model = InventoryCostMovement; fields = "__all__"
class CostLedgerEntrySerializer(serializers.ModelSerializer):
    class Meta: model = CostLedgerEntry; fields = "__all__"
class PeriodVariancePostingSerializer(serializers.ModelSerializer):
    class Meta: model = PeriodVariancePosting; fields = "__all__"

from .models import (
    InventoryRevaluation, FinancialInventoryAdjustment, LotActualCost, SerialActualCost,
    InventoryReconciliationRun, InventoryReconciliationLine,
)

class InventoryRevaluationSerializer(serializers.ModelSerializer):
    class Meta: model = InventoryRevaluation; fields = "__all__"; read_only_fields = ["old_unit_cost", "old_value", "new_value", "variance_value", "posted_at", "posted_by", "ledger_debit", "ledger_credit"]

class FinancialInventoryAdjustmentSerializer(serializers.ModelSerializer):
    class Meta: model = FinancialInventoryAdjustment; fields = "__all__"; read_only_fields = ["status", "posted_at", "posted_by", "ledger_debit", "ledger_credit"]

class LotActualCostSerializer(serializers.ModelSerializer):
    class Meta: model = LotActualCost; fields = "__all__"

class SerialActualCostSerializer(serializers.ModelSerializer):
    class Meta: model = SerialActualCost; fields = "__all__"

class InventoryReconciliationLineSerializer(serializers.ModelSerializer):
    class Meta: model = InventoryReconciliationLine; fields = "__all__"

class InventoryReconciliationRunSerializer(serializers.ModelSerializer):
    lines = InventoryReconciliationLineSerializer(many=True, read_only=True)
    class Meta: model = InventoryReconciliationRun; fields = "__all__"

from .models import PeriodCloseRun, PeriodReopenRequest, CostLedgerReversal, CostPeriodAudit

class PeriodCloseRunSerializer(serializers.ModelSerializer):
    class Meta: model = PeriodCloseRun; fields = "__all__"; read_only_fields = ["status", "started_at", "finished_at", "inventory_value", "wip_value", "variance_value", "ledger_debits", "ledger_credits", "reconciliation_quantity_variance", "reconciliation_value_variance", "error_message", "executed_by"]

class PeriodReopenRequestSerializer(serializers.ModelSerializer):
    class Meta: model = PeriodReopenRequest; fields = "__all__"; read_only_fields = ["status", "requested_by", "requested_at", "decided_by", "decided_at", "decision_notes", "applied_by", "applied_at"]

class CostLedgerReversalSerializer(serializers.ModelSerializer):
    class Meta: model = CostLedgerReversal; fields = "__all__"; read_only_fields = ["original_entry", "reversal_entry", "reason", "reversed_by", "reversed_at"]

class CostPeriodAuditSerializer(serializers.ModelSerializer):
    class Meta: model = CostPeriodAudit; fields = "__all__"
