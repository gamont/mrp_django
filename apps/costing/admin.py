from django.contrib import admin
from .models import CostVersion, WorkCenterRate, ItemCost, CostRollupRun, WorkOrderCost, WorkOrderCostLine, CostVariance, PurchasePriceVariance
for model in [CostVersion, WorkCenterRate, ItemCost, CostRollupRun, WorkOrderCost, WorkOrderCostLine, CostVariance, PurchasePriceVariance]:
    admin.site.register(model)

from .models import AccountingPeriod, InventoryValuationSnapshot, InventoryValuationLine, WIPSnapshot, WIPLine
admin.site.register([AccountingPeriod, InventoryValuationSnapshot, InventoryValuationLine, WIPSnapshot, WIPLine])

from .models import MovingAverageCostBalance, InventoryCostMovement, CostLedgerEntry, PeriodVariancePosting
admin.site.register([MovingAverageCostBalance, InventoryCostMovement, CostLedgerEntry, PeriodVariancePosting])

from .models import InventoryRevaluation, FinancialInventoryAdjustment, LotActualCost, SerialActualCost, InventoryReconciliationRun, InventoryReconciliationLine
admin.site.register([InventoryRevaluation, FinancialInventoryAdjustment, LotActualCost, SerialActualCost, InventoryReconciliationRun, InventoryReconciliationLine])

from .models import PeriodCloseRun, PeriodReopenRequest, CostLedgerReversal, CostPeriodAudit
admin.site.register([PeriodCloseRun, PeriodReopenRequest, CostLedgerReversal, CostPeriodAudit])
