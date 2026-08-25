from apps.integrated_scheduling.api import (
    IntegratedScheduleScenarioViewSet, IntegratedScheduleBlockViewSet, IntegratedScheduleConflictViewSet, PublishedOperationScheduleViewSet, IndustrialShiftBreakViewSet, IndustrialCalendarWindowViewSet, IntegratedScheduleSegmentViewSet, ProductFamilyViewSet, ItemSchedulingProfileViewSet, SequenceSetupRuleViewSet, ScheduleOptimizationRunViewSet, ScheduleOptimizationCandidateViewSet, ScheduleSolverRunViewSet, ScheduleSolverAssignmentViewSet, ScheduleSolverIncumbentViewSet, ScheduleSolverSegmentViewSet, LaborSkillViewSet, LaborResourceViewSet, LaborResourceSkillViewSet, LaborShiftAssignmentViewSet, LaborUnavailabilityViewSet, OperationLaborRequirementViewSet, ScheduleSolverLaborAssignmentViewSet, LaborRuleSetViewSet, ScheduleSolverLaborCostViewSet, ProductionSchedulePublicationViewSet, PublishedExecutionSlotViewSet, ScheduleExecutionDeviationViewSet, ReschedulingTriggerViewSet, RecoveryPolicyViewSet, RecoveryPlanViewSet, RecoveryCommercialImpactViewSet, CommercialPromiseAlertViewSet, SalesOrderPromiseViewSet, CommercialServiceCaseViewSet, SalesOrderCommercialContactViewSet, CustomerPromiseResponseViewSet, CommercialCommunicationViewSet, OTIFLineResultViewSet, ServiceLevelCauseViewSet, ServiceLevelTargetViewSet, ServiceLevelPeriodSnapshotViewSet,
)
from apps.maintenance.api import (
    MaintenanceAssetViewSet, AssetMeterReadingViewSet, MaintenancePlanViewSet,
    MaintenanceWorkOrderViewSet, MaintenancePartViewSet, FailureEventViewSet,
    TechnicianSkillViewSet, TechnicianProfileViewSet, TechnicianSkillAssignmentViewSet, WorkOrderAssignmentViewSet,
    MaintenanceSLAViewSet, ConditionReadingViewSet, ConditionRuleViewSet,
    MaintenanceRequiredSkillViewSet, MaintenancePartReservationViewSet, MaintenanceScheduleConflictViewSet,
)
from rest_framework.routers import DefaultRouter
from apps.costing.views import (
    CostVersionViewSet, WorkCenterRateViewSet, ItemCostViewSet, CostRollupRunViewSet,
    WorkOrderCostViewSet, CostVarianceViewSet, PurchasePriceVarianceViewSet,
    AccountingPeriodViewSet, InventoryValuationSnapshotViewSet, WIPSnapshotViewSet,
    MovingAverageCostBalanceViewSet, InventoryCostMovementViewSet, CostLedgerEntryViewSet, PeriodVariancePostingViewSet,
    InventoryRevaluationViewSet, FinancialInventoryAdjustmentViewSet, LotActualCostViewSet, SerialActualCostViewSet, InventoryReconciliationRunViewSet,
    PeriodCloseRunViewSet, PeriodReopenRequestViewSet, CostLedgerReversalViewSet, CostPeriodAuditViewSet,
)

from .views import (
    BOMLineViewSet,
    BOMRevisionViewSet, BOMRevisionLineViewSet, EngineeringChangeViewSet, EngineeringChangeItemViewSet, EngineeringChangeApprovalViewSet, EngineeringImpactViewSet, RoutingRevisionViewSet,
    CapacityAllocationViewSet,
    CapacityScenarioViewSet,
    DomainEventViewSet,
    ForecastViewSet,
    GoodsReceiptViewSet,
    InventoryTransactionViewSet,
    ItemPlantPolicyViewSet,
    ItemSubstituteViewSet,
    ItemSupplierViewSet,
    ItemViewSet,
    LocationViewSet,
    MasterProductionScheduleViewSet,
    DemandPeggingAllocationViewSet,
    PeggingRecordViewSet,
    PlannedOrderViewSet,
    PlanningBucketViewSet,
    PlanningChangeViewSet,
    PlanningMessageViewSet,
    PlanningRunViewSet,
    PlantViewSet,
    ProductionReportViewSet,
    PurchaseOrderLineViewSet,
    PurchaseOrderViewSet,
    ReservationViewSet,
    RoutingOperationViewSet,
    RoutingViewSet,
    SalesOrderLineViewSet,
    SalesOrderViewSet, SalesDeliveryViewSet, SalesDeliveryLineViewSet,
    ShopCalendarDayViewSet,
    StockBalanceViewSet,
    SupplierViewSet,
    WarehouseViewSet,
    WorkCenterShiftViewSet,
    WorkCenterViewSet,
    WorkOrderCompletionViewSet,
    WorkOrderMaterialViewSet,
    WorkOrderOperationViewSet,
    WorkOrderViewSet,
    InventoryLotViewSet, LotBalanceViewSet, LotTransactionViewSet, LotReservationViewSet,
    SerialNumberViewSet, SerialTransactionViewSet, SerialComponentViewSet,
    InspectionPlanViewSet, InspectionCharacteristicViewSet, InspectionOrderViewSet, InspectionResultViewSet, NonConformanceViewSet, DispositionViewSet,
    RecallCaseViewSet, RecallCriterionViewSet, RecallAffectedUnitViewSet, RecallActionViewSet,
)

router = DefaultRouter()
router.register("integrated-schedule-scenarios", IntegratedScheduleScenarioViewSet)
router.register("integrated-schedule-blocks", IntegratedScheduleBlockViewSet)
router.register("integrated-schedule-conflicts", IntegratedScheduleConflictViewSet)
router.register("industrial-shift-breaks", IndustrialShiftBreakViewSet)
router.register("industrial-calendar-windows", IndustrialCalendarWindowViewSet)
router.register("integrated-schedule-segments", IntegratedScheduleSegmentViewSet)
router.register("scheduling-product-families", ProductFamilyViewSet)
router.register("item-scheduling-profiles", ItemSchedulingProfileViewSet)
router.register("sequence-setup-rules", SequenceSetupRuleViewSet)
router.register("schedule-optimization-runs", ScheduleOptimizationRunViewSet)
router.register("schedule-optimization-candidates", ScheduleOptimizationCandidateViewSet)
router.register("schedule-solver-runs", ScheduleSolverRunViewSet, basename="schedule-solver-runs")
router.register("schedule-solver-assignments", ScheduleSolverAssignmentViewSet)
router.register("schedule-solver-incumbents", ScheduleSolverIncumbentViewSet)
router.register("schedule-solver-segments", ScheduleSolverSegmentViewSet)
router.register("labor-skills", LaborSkillViewSet)
router.register("labor-resources", LaborResourceViewSet)
router.register("labor-resource-skills", LaborResourceSkillViewSet)
router.register("labor-shift-assignments", LaborShiftAssignmentViewSet)
router.register("labor-unavailability", LaborUnavailabilityViewSet)
router.register("operation-labor-requirements", OperationLaborRequirementViewSet)
router.register("schedule-solver-labor-assignments", ScheduleSolverLaborAssignmentViewSet)
router.register("labor-rule-sets", LaborRuleSetViewSet)
router.register("schedule-solver-labor-costs", ScheduleSolverLaborCostViewSet)
router.register("published-operation-schedules", PublishedOperationScheduleViewSet)
router.register("production-schedule-publications", ProductionSchedulePublicationViewSet, basename="production-schedule-publications")
router.register("published-execution-slots", PublishedExecutionSlotViewSet)
router.register("schedule-execution-deviations", ScheduleExecutionDeviationViewSet)
router.register("rescheduling-triggers", ReschedulingTriggerViewSet, basename="rescheduling-triggers")
router.register("recovery-policies", RecoveryPolicyViewSet)
router.register("recovery-plans", RecoveryPlanViewSet)
router.register("recovery-commercial-impacts", RecoveryCommercialImpactViewSet)
router.register("commercial-promise-alerts", CommercialPromiseAlertViewSet, basename="commercial-promise-alerts")
router.register("sales-order-promises", SalesOrderPromiseViewSet, basename="sales-order-promises")
router.register("commercial-service-cases", CommercialServiceCaseViewSet)
router.register("sales-order-commercial-contacts", SalesOrderCommercialContactViewSet)
router.register("customer-promise-responses", CustomerPromiseResponseViewSet)
router.register("commercial-communications", CommercialCommunicationViewSet, basename="commercial-communications")
router.register("otif-line-results", OTIFLineResultViewSet, basename="otif-line-results")
router.register("service-level-causes", ServiceLevelCauseViewSet)
router.register("service-level-targets", ServiceLevelTargetViewSet)
router.register("service-level-snapshots", ServiceLevelPeriodSnapshotViewSet, basename="service-level-snapshots")
router.register("maintenance-assets", MaintenanceAssetViewSet)
router.register("maintenance-meter-readings", AssetMeterReadingViewSet)
router.register("maintenance-plans", MaintenancePlanViewSet)
router.register("maintenance-work-orders", MaintenanceWorkOrderViewSet)
router.register("maintenance-parts", MaintenancePartViewSet)
router.register("maintenance-failures", FailureEventViewSet)
router.register("maintenance-technician-skills", TechnicianSkillViewSet)
router.register("maintenance-technicians", TechnicianProfileViewSet)
router.register("maintenance-technician-skill-assignments", TechnicianSkillAssignmentViewSet)
router.register("maintenance-work-order-assignments", WorkOrderAssignmentViewSet)
router.register("maintenance-slas", MaintenanceSLAViewSet)
router.register("maintenance-condition-readings", ConditionReadingViewSet)
router.register("maintenance-condition-rules", ConditionRuleViewSet)
router.register("maintenance-required-skills", MaintenanceRequiredSkillViewSet)
router.register("maintenance-part-reservations", MaintenancePartReservationViewSet)
router.register("maintenance-schedule-conflicts", MaintenanceScheduleConflictViewSet)
router.register("plants", PlantViewSet)
router.register("calendar-days", ShopCalendarDayViewSet)
router.register("domain-events", DomainEventViewSet)
router.register("items", ItemViewSet)
router.register("item-policies", ItemPlantPolicyViewSet)
router.register("item-substitutes", ItemSubstituteViewSet)
router.register("bom-lines", BOMLineViewSet)
router.register("engineering-changes", EngineeringChangeViewSet)
router.register("engineering-change-items", EngineeringChangeItemViewSet)
router.register("engineering-change-approvals", EngineeringChangeApprovalViewSet)
router.register("engineering-impacts", EngineeringImpactViewSet)
router.register("bom-revisions", BOMRevisionViewSet)
router.register("bom-revision-lines", BOMRevisionLineViewSet)
router.register("routing-revisions", RoutingRevisionViewSet)
router.register("work-centers", WorkCenterViewSet)
router.register("work-center-shifts", WorkCenterShiftViewSet)
router.register("routings", RoutingViewSet)
router.register("routing-operations", RoutingOperationViewSet)
router.register("suppliers", SupplierViewSet)
router.register("item-suppliers", ItemSupplierViewSet)
router.register("warehouses", WarehouseViewSet)
router.register("locations", LocationViewSet)
router.register("stock-balances", StockBalanceViewSet)
router.register("inventory-transactions", InventoryTransactionViewSet)
router.register("reservations", ReservationViewSet)
router.register("forecasts", ForecastViewSet)
router.register("sales-orders", SalesOrderViewSet)
router.register("sales-order-lines", SalesOrderLineViewSet)
router.register("sales-deliveries", SalesDeliveryViewSet)
router.register("sales-delivery-lines", SalesDeliveryLineViewSet)
router.register("mps", MasterProductionScheduleViewSet)
router.register("work-orders", WorkOrderViewSet)
router.register("work-order-materials", WorkOrderMaterialViewSet)
router.register("work-order-operations", WorkOrderOperationViewSet)
router.register("work-order-completions", WorkOrderCompletionViewSet)
router.register("production-reports", ProductionReportViewSet)
router.register("purchase-orders", PurchaseOrderViewSet)
router.register("purchase-order-lines", PurchaseOrderLineViewSet)
router.register("goods-receipts", GoodsReceiptViewSet)
router.register("planning-runs", PlanningRunViewSet)
router.register("planning-buckets", PlanningBucketViewSet)
router.register("planning-changes", PlanningChangeViewSet)
router.register("planned-orders", PlannedOrderViewSet)
router.register("demand-pegging-allocations", DemandPeggingAllocationViewSet)
router.register("pegging", PeggingRecordViewSet)
router.register("planning-messages", PlanningMessageViewSet)
router.register("capacity-scenarios", CapacityScenarioViewSet)
router.register("capacity-allocations", CapacityAllocationViewSet)
router.register("inventory-lots", InventoryLotViewSet)
router.register("lot-balances", LotBalanceViewSet)
router.register("lot-transactions", LotTransactionViewSet)
router.register("lot-reservations", LotReservationViewSet)
router.register("serial-numbers", SerialNumberViewSet)
router.register("serial-transactions", SerialTransactionViewSet)
router.register("serial-components", SerialComponentViewSet)

router.register("inspection-plans", InspectionPlanViewSet)
router.register("inspection-characteristics", InspectionCharacteristicViewSet)
router.register("inspection-orders", InspectionOrderViewSet)
router.register("inspection-results", InspectionResultViewSet)
router.register("nonconformances", NonConformanceViewSet)
router.register("dispositions", DispositionViewSet)

router.register("recall-cases", RecallCaseViewSet)
router.register("recall-criteria", RecallCriterionViewSet)
router.register("recall-affected-units", RecallAffectedUnitViewSet)
router.register("recall-actions", RecallActionViewSet)

router.register("cost-versions", CostVersionViewSet)
router.register("work-center-rates", WorkCenterRateViewSet)
router.register("item-costs", ItemCostViewSet)
router.register("cost-rollup-runs", CostRollupRunViewSet)
router.register("work-order-costs", WorkOrderCostViewSet, basename="work-order-costs")
router.register("cost-variances", CostVarianceViewSet)
router.register("purchase-price-variances", PurchasePriceVarianceViewSet, basename="purchase-price-variances")
router.register("accounting-periods", AccountingPeriodViewSet)
router.register("inventory-valuations", InventoryValuationSnapshotViewSet)
router.register("wip-valuations", WIPSnapshotViewSet)
router.register("moving-average-costs", MovingAverageCostBalanceViewSet, basename="moving-average-costs")
router.register("inventory-cost-movements", InventoryCostMovementViewSet)
router.register("cost-ledger-entries", CostLedgerEntryViewSet)
router.register("period-variance-postings", PeriodVariancePostingViewSet, basename="period-variance-postings")
router.register("inventory-revaluations", InventoryRevaluationViewSet, basename="inventory-revaluations")
router.register("financial-inventory-adjustments", FinancialInventoryAdjustmentViewSet)
router.register("lot-actual-costs", LotActualCostViewSet, basename="lot-actual-costs")
router.register("serial-actual-costs", SerialActualCostViewSet, basename="serial-actual-costs")
router.register("inventory-reconciliations", InventoryReconciliationRunViewSet, basename="inventory-reconciliations")
router.register("period-close-runs", PeriodCloseRunViewSet)
router.register("period-reopen-requests", PeriodReopenRequestViewSet, basename="period-reopen-requests")
router.register("cost-ledger-reversals", CostLedgerReversalViewSet, basename="cost-ledger-reversals")
router.register("cost-period-audit", CostPeriodAuditViewSet)

urlpatterns = router.urls

# 0.7.8 registrations
from apps.integrated_scheduling.api import ForecastAccuracySnapshotViewSet, ExecutiveSAndOPSnapshotViewSet, SAndOPScenarioViewSet
router.register("forecast-accuracy-snapshots", ForecastAccuracySnapshotViewSet)
router.register("executive-sop-snapshots", ExecutiveSAndOPSnapshotViewSet, basename="executive-sop-snapshots")
router.register("sop-scenarios", SAndOPScenarioViewSet)

urlpatterns = router.urls

# 0.7.9 registrations — formal S&OP cycle
from apps.integrated_scheduling.api import (
    SAndOPCycleViewSet, SAndOPDemandConsensusLineViewSet, SAndOPSupplyPlanLineViewSet,
    SAndOPConstraintViewSet, SAndOPDecisionViewSet, SAndOPPublicationViewSet,
)
router.register("sop-cycles", SAndOPCycleViewSet)
router.register("sop-demand-consensus-lines", SAndOPDemandConsensusLineViewSet)
router.register("sop-supply-plan-lines", SAndOPSupplyPlanLineViewSet)
router.register("sop-constraints", SAndOPConstraintViewSet)
router.register("sop-decisions", SAndOPDecisionViewSet)
router.register("sop-publications", SAndOPPublicationViewSet)
urlpatterns = router.urls

# 0.8.0 registrations — operational weekly MPS
from apps.integrated_scheduling.api import MPSOperationalPolicyViewSet, OperationalMPSPublicationViewSet, MPSWeeklyBucketViewSet, MPSRCCPExceptionViewSet, MPSBucketChangeRequestViewSet
router.register("mps-operational-policies", MPSOperationalPolicyViewSet)
router.register("operational-mps-publications", OperationalMPSPublicationViewSet, basename="operational-mps-publications")
router.register("mps-weekly-buckets", MPSWeeklyBucketViewSet)
router.register("mps-rccp-exceptions", MPSRCCPExceptionViewSet)
router.register("mps-bucket-change-requests", MPSBucketChangeRequestViewSet)
urlpatterns = router.urls


# 0.8.2 registrations — MPS revisions
from apps.integrated_scheduling.api import MPSRevisionViewSet, MPSRevisionLineViewSet, MPSRevisionRCCPLineViewSet
router.register("mps-revisions", MPSRevisionViewSet, basename="mps-revisions")
router.register("mps-revision-lines", MPSRevisionLineViewSet)
router.register("mps-revision-rccp-lines", MPSRevisionRCCPLineViewSet)
urlpatterns = router.urls

# 0.8.3 registrations — MPS revision what-if MRP
from apps.integrated_scheduling.api import MPSRevisionSimulationViewSet, MPSRevisionSimulationDiffLineViewSet
router.register("mps-revision-simulations", MPSRevisionSimulationViewSet, basename="mps-revision-simulations")
router.register("mps-revision-simulation-diffs", MPSRevisionSimulationDiffLineViewSet)
urlpatterns = router.urls


# 0.8.4 registrations — financial what-if
from apps.integrated_scheduling.api import MPSRevisionSimulationFinancialLineViewSet
router.register("mps-revision-simulation-financial-lines", MPSRevisionSimulationFinancialLineViewSet)
urlpatterns = router.urls


# 0.8.5 registrations — budget and temporal cash-flow
from apps.integrated_scheduling.api import MPSFinancialBudgetViewSet, MPSFinancialBudgetLineViewSet, MPSRevisionSimulationCashFlowBucketViewSet
router.register("mps-financial-budgets", MPSFinancialBudgetViewSet)
router.register("mps-financial-budget-lines", MPSFinancialBudgetLineViewSet)
router.register("mps-revision-simulation-cashflow", MPSRevisionSimulationCashFlowBucketViewSet, basename="mps-revision-simulation-cashflow")
urlpatterns = router.urls


# 0.8.6 registrations — working capital
from apps.integrated_scheduling.api import WorkingCapitalPolicyViewSet, MPSRevisionSimulationWorkingCapitalBucketViewSet
router.register("working-capital-policies", WorkingCapitalPolicyViewSet)
router.register("mps-revision-simulation-working-capital", MPSRevisionSimulationWorkingCapitalBucketViewSet, basename="mps-revision-simulation-working-capital")
urlpatterns = router.urls

# 0.8.7 registrations — financing capacity
from apps.integrated_scheduling.api import FinancingPolicyViewSet, FinancingFacilityViewSet, MPSRevisionSimulationFinancingBucketViewSet
router.register('financing-policies', FinancingPolicyViewSet)
router.register('financing-facilities', FinancingFacilityViewSet)
router.register('mps-revision-simulation-financing', MPSRevisionSimulationFinancingBucketViewSet, basename='mps-revision-simulation-financing')
urlpatterns = router.urls

# 0.8.8 registrations — MPS multi-criteria optimizer
from apps.integrated_scheduling.api import MPSOptimizationPolicyViewSet, MPSRevisionOptimizationRunViewSet, MPSRevisionOptimizationCandidateViewSet, MPSRevisionOptimizationActionViewSet
router.register('mps-optimization-policies', MPSOptimizationPolicyViewSet)
router.register('mps-revision-optimization-runs', MPSRevisionOptimizationRunViewSet, basename='mps-revision-optimization-runs')
router.register('mps-revision-optimization-candidates', MPSRevisionOptimizationCandidateViewSet)
router.register('mps-revision-optimization-actions', MPSRevisionOptimizationActionViewSet)
urlpatterns = router.urls

# 0.9.0 registrations — executive decision cockpit
from apps.integrated_scheduling.api import MPSDecisionCockpitViewSet, MPSDecisionCandidateReviewViewSet
router.register('mps-decision-cockpits', MPSDecisionCockpitViewSet, basename='mps-decision-cockpits')
router.register('mps-decision-candidate-reviews', MPSDecisionCandidateReviewViewSet)
urlpatterns = router.urls


# 0.9.1 registrations — formal decision minutes and cross-functional approvals
from apps.integrated_scheduling.api import MPSDecisionGovernancePolicyViewSet,MPSDecisionMeetingViewSet,MPSDecisionParticipantViewSet,MPSDecisionCommentViewSet,MPSDecisionRiskAcceptanceViewSet,MPSDecisionConditionViewSet,MPSDecisionAreaApprovalViewSet,MPSDecisionAttachmentViewSet
router.register('mps-decision-governance-policies',MPSDecisionGovernancePolicyViewSet)
router.register('mps-decision-meetings',MPSDecisionMeetingViewSet)
router.register('mps-decision-participants',MPSDecisionParticipantViewSet)
router.register('mps-decision-comments',MPSDecisionCommentViewSet)
router.register('mps-decision-risks',MPSDecisionRiskAcceptanceViewSet)
router.register('mps-decision-conditions',MPSDecisionConditionViewSet)
router.register('mps-decision-area-approvals',MPSDecisionAreaApprovalViewSet,basename='mps-decision-area-approvals')
router.register('mps-decision-attachments',MPSDecisionAttachmentViewSet)
urlpatterns=router.urls


# 0.9.2 registrations — approval authority and electronic signatures
from apps.integrated_scheduling.api import MPSDecisionApprovalMatrixViewSet,MPSDecisionApprovalRequirementViewSet,MPSDecisionElectronicSignatureViewSet
router.register('mps-decision-approval-matrix',MPSDecisionApprovalMatrixViewSet)
router.register('mps-decision-approval-requirements',MPSDecisionApprovalRequirementViewSet,basename='mps-decision-approval-requirements')
router.register('mps-decision-electronic-signatures',MPSDecisionElectronicSignatureViewSet)
urlpatterns=router.urls

# 0.9.3 registrations — tamper-evident audit trail/evidence packages
from apps.integrated_scheduling.api import MPSDecisionAuditEventViewSet, MPSDecisionEvidenceExportViewSet
router.register('mps-decision-audit-events',MPSDecisionAuditEventViewSet,basename='mps-decision-audit-events')
router.register('mps-decision-evidence-exports',MPSDecisionEvidenceExportViewSet,basename='mps-decision-evidence-exports')
urlpatterns=router.urls

# 0.9.4 registrations — external integrity anchors
from apps.integrated_scheduling.api import MPSDecisionAuditAnchorViewSet
router.register('mps-decision-audit-anchors',MPSDecisionAuditAnchorViewSet,basename='mps-decision-audit-anchors')
urlpatterns=router.urls


# 0.9.5 automatic anchor policies
from apps.integrated_scheduling.api import MPSDecisionAnchorPolicyViewSet
router.register('mps-decision-anchor-policies',MPSDecisionAnchorPolicyViewSet,basename='mps-decision-anchor-policies')


# 0.9.6 security & compliance center
from apps.integrated_scheduling.api import MPSDecisionCompliancePolicyViewSet,MPSDecisionComplianceIncidentViewSet,MPSDecisionComplianceSnapshotViewSet
router.register('mps-decision-compliance-policies',MPSDecisionCompliancePolicyViewSet,basename='mps-decision-compliance-policies')
router.register('mps-decision-compliance-incidents',MPSDecisionComplianceIncidentViewSet,basename='mps-decision-compliance-incidents')
router.register('mps-decision-compliance-snapshots',MPSDecisionComplianceSnapshotViewSet,basename='mps-decision-compliance-snapshots')
urlpatterns=router.urls

# 0.9.7 — compliance escalation
from apps.integrated_scheduling.api import MPSComplianceEscalationPolicyViewSet,MPSComplianceEscalationRuleViewSet,MPSComplianceOnCallContactViewSet,MPSComplianceEscalationEventViewSet
router.register('mps-compliance-escalation-policies',MPSComplianceEscalationPolicyViewSet,basename='mps-compliance-escalation-policies')
router.register('mps-compliance-escalation-rules',MPSComplianceEscalationRuleViewSet,basename='mps-compliance-escalation-rules')
router.register('mps-compliance-on-call-contacts',MPSComplianceOnCallContactViewSet,basename='mps-compliance-on-call-contacts')
router.register('mps-compliance-escalation-events',MPSComplianceEscalationEventViewSet,basename='mps-compliance-escalation-events')
urlpatterns=router.urls


# 0.9.8 — corporate escalation calendar/channels
from apps.integrated_scheduling.api import MPSComplianceHolidayViewSet,MPSComplianceOnCallAbsenceViewSet,MPSComplianceOnCallSubstitutionViewSet,MPSComplianceNotificationDeliveryViewSet
router.register('mps-compliance-holidays',MPSComplianceHolidayViewSet,basename='mps-compliance-holidays')
router.register('mps-compliance-on-call-absences',MPSComplianceOnCallAbsenceViewSet,basename='mps-compliance-on-call-absences')
router.register('mps-compliance-on-call-substitutions',MPSComplianceOnCallSubstitutionViewSet,basename='mps-compliance-on-call-substitutions')
router.register('mps-compliance-notification-deliveries',MPSComplianceNotificationDeliveryViewSet,basename='mps-compliance-notification-deliveries')
urlpatterns=router.urls

# 0.9.9 — Incident Command & Postmortem
from apps.integrated_scheduling.api import MPSIncidentCommandPolicyViewSet,MPSMajorIncidentViewSet,MPSMajorIncidentTimelineEventViewSet,MPSMajorIncidentActionViewSet,MPSMajorIncidentPostmortemViewSet,MPSMajorIncidentLearningActionViewSet
router.register('mps-incident-command-policies',MPSIncidentCommandPolicyViewSet,basename='mps-incident-command-policies')
router.register('mps-major-incidents',MPSMajorIncidentViewSet,basename='mps-major-incidents')
router.register('mps-major-incident-timeline',MPSMajorIncidentTimelineEventViewSet,basename='mps-major-incident-timeline')
router.register('mps-major-incident-actions',MPSMajorIncidentActionViewSet,basename='mps-major-incident-actions')
router.register('mps-major-incident-postmortems',MPSMajorIncidentPostmortemViewSet,basename='mps-major-incident-postmortems')
router.register('mps-major-incident-learning-actions',MPSMajorIncidentLearningActionViewSet,basename='mps-major-incident-learning-actions')
urlpatterns=router.urls
