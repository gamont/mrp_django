from rest_framework import serializers
from .models import IntegratedScheduleBlock, IntegratedScheduleConflict, IntegratedScheduleScenario, PublishedOperationSchedule, IndustrialShiftBreak, IndustrialCalendarWindow, IntegratedScheduleSegment, ProductFamily, ItemSchedulingProfile, SequenceSetupRule, ScheduleOptimizationRun, ScheduleOptimizationCandidate, ScheduleSolverRun, ScheduleSolverAssignment, ScheduleSolverIncumbent, ScheduleSolverSegment, LaborSkill, LaborResource, LaborResourceSkill, LaborShiftAssignment, LaborUnavailability, OperationLaborRequirement, ScheduleSolverLaborAssignment, LaborRuleSet, ScheduleSolverLaborCost


class IntegratedScheduleScenarioSerializer(serializers.ModelSerializer):
    class Meta:
        model = IntegratedScheduleScenario
        fields = "__all__"
        read_only_fields = ("status", "baseline_summary", "simulated_summary", "created_by", "applied_by", "applied_at", "error_message")


class IntegratedScheduleBlockSerializer(serializers.ModelSerializer):
    class Meta:
        model = IntegratedScheduleBlock
        fields = "__all__"


class IntegratedScheduleConflictSerializer(serializers.ModelSerializer):
    class Meta:
        model = IntegratedScheduleConflict
        fields = "__all__"


class PublishedOperationScheduleSerializer(serializers.ModelSerializer):
    class Meta:
        model = PublishedOperationSchedule
        fields = "__all__"
        read_only_fields = ("published_at",)


class IndustrialShiftBreakSerializer(serializers.ModelSerializer):
    class Meta:
        model = IndustrialShiftBreak
        fields = "__all__"

class IndustrialCalendarWindowSerializer(serializers.ModelSerializer):
    class Meta:
        model = IndustrialCalendarWindow
        fields = "__all__"

class IntegratedScheduleSegmentSerializer(serializers.ModelSerializer):
    class Meta:
        model = IntegratedScheduleSegment
        fields = "__all__"


class ProductFamilySerializer(serializers.ModelSerializer):
    class Meta:
        model = ProductFamily
        fields = "__all__"

class ItemSchedulingProfileSerializer(serializers.ModelSerializer):
    class Meta:
        model = ItemSchedulingProfile
        fields = "__all__"

class SequenceSetupRuleSerializer(serializers.ModelSerializer):
    class Meta:
        model = SequenceSetupRule
        fields = "__all__"


class ScheduleOptimizationRunSerializer(serializers.ModelSerializer):
    class Meta:
        model = ScheduleOptimizationRun
        fields = "__all__"
        read_only_fields = ("status", "best_candidate", "summary", "created_by", "error_message")


class ScheduleOptimizationCandidateSerializer(serializers.ModelSerializer):
    class Meta:
        model = ScheduleOptimizationCandidate
        fields = "__all__"
        read_only_fields = ("rank", "objective_score", "feasible", "pareto_front", "metrics", "normalized_metrics")


class ScheduleSolverRunSerializer(serializers.ModelSerializer):
    class Meta:
        model = ScheduleSolverRun
        fields = "__all__"
        read_only_fields = ("status", "objective_value", "best_bound", "wall_time_seconds", "conflicts", "branches", "summary", "created_by", "error_message", "celery_task_id", "cancel_requested_at", "started_at", "finished_at", "last_incumbent_at", "progress", "warm_start_source", "warm_start_scenario")


class ScheduleSolverIncumbentSerializer(serializers.ModelSerializer):
    class Meta:
        model = ScheduleSolverIncumbent
        fields = "__all__"
        read_only_fields = ("run", "sequence", "objective_value", "best_bound", "relative_gap", "wall_time_seconds", "solution_count", "summary")


class ScheduleSolverAssignmentSerializer(serializers.ModelSerializer):
    class Meta:
        model = ScheduleSolverAssignment
        fields = "__all__"
        read_only_fields = ("run",)


class ScheduleSolverSegmentSerializer(serializers.ModelSerializer):
    class Meta:
        model = ScheduleSolverSegment
        fields = "__all__"
        read_only_fields = ("assignment",)


class LaborSkillSerializer(serializers.ModelSerializer):
    class Meta:
        model = LaborSkill
        fields = "__all__"

class LaborResourceSerializer(serializers.ModelSerializer):
    class Meta:
        model = LaborResource
        fields = "__all__"

class LaborResourceSkillSerializer(serializers.ModelSerializer):
    class Meta:
        model = LaborResourceSkill
        fields = "__all__"

class LaborShiftAssignmentSerializer(serializers.ModelSerializer):
    class Meta:
        model = LaborShiftAssignment
        fields = "__all__"

class LaborUnavailabilitySerializer(serializers.ModelSerializer):
    class Meta:
        model = LaborUnavailability
        fields = "__all__"

class OperationLaborRequirementSerializer(serializers.ModelSerializer):
    class Meta:
        model = OperationLaborRequirement
        fields = "__all__"

class ScheduleSolverLaborAssignmentSerializer(serializers.ModelSerializer):
    class Meta:
        model = ScheduleSolverLaborAssignment
        fields = "__all__"
        read_only_fields = ("run", "assignment", "segment", "operation", "labor_resource", "skill", "start", "end", "shift_name", "is_handoff")


class LaborRuleSetSerializer(serializers.ModelSerializer):
    class Meta:
        model = LaborRuleSet
        fields = "__all__"

class ScheduleSolverLaborCostSerializer(serializers.ModelSerializer):
    class Meta:
        model = ScheduleSolverLaborCost
        fields = "__all__"
        read_only_fields = ("labor_assignment", "normal_minutes", "overtime_minutes", "night_minutes", "base_cost", "overtime_premium", "night_premium", "total_cost", "rule_set", "details")


from .models import ProductionSchedulePublication, PublishedExecutionSlot, ScheduleExecutionDeviation, ReschedulingTrigger

class ProductionSchedulePublicationSerializer(serializers.ModelSerializer):
    class Meta:
        model = ProductionSchedulePublication
        fields = "__all__"
        read_only_fields = ("version", "status", "published_by", "published_at", "metrics")

class PublishedExecutionSlotSerializer(serializers.ModelSerializer):
    class Meta:
        model = PublishedExecutionSlot
        fields = "__all__"
        read_only_fields = ("actual_start", "actual_end", "status", "team_snapshot")

class ScheduleExecutionDeviationSerializer(serializers.ModelSerializer):
    class Meta:
        model = ScheduleExecutionDeviation
        fields = "__all__"

class ReschedulingTriggerSerializer(serializers.ModelSerializer):
    class Meta:
        model = ReschedulingTrigger
        fields = "__all__"
        read_only_fields = ("status", "resulting_scenario", "resulting_solver_run", "processed_at", "error_message")


from .models import RecoveryPolicy, RecoveryPlan

class RecoveryPolicySerializer(serializers.ModelSerializer):
    class Meta:
        model = RecoveryPolicy
        fields = "__all__"

class RecoveryPlanSerializer(serializers.ModelSerializer):
    class Meta:
        model = RecoveryPlan
        fields = "__all__"
        read_only_fields = ("rank", "risk_score", "low_risk", "auto_publish_eligible", "metrics", "impact", "error_message")

from .models import RecoveryCommercialImpact, CommercialPromiseAlert

class RecoveryCommercialImpactSerializer(serializers.ModelSerializer):
    sales_order_number = serializers.CharField(source="sales_order_line.sales_order.number", read_only=True)
    customer_code = serializers.CharField(source="sales_order_line.sales_order.customer_code", read_only=True)
    customer_name = serializers.CharField(source="sales_order_line.sales_order.customer_name", read_only=True)
    item_code = serializers.CharField(source="sales_order_line.item.code", read_only=True)
    line_number = serializers.IntegerField(source="sales_order_line.line_number", read_only=True)
    class Meta:
        model = RecoveryCommercialImpact
        fields = "__all__"

class CommercialPromiseAlertSerializer(serializers.ModelSerializer):
    sales_order_number = serializers.CharField(source="sales_order_line.sales_order.number", read_only=True)
    customer_name = serializers.CharField(source="sales_order_line.sales_order.customer_name", read_only=True)
    class Meta:
        model = CommercialPromiseAlert
        fields = "__all__"
        read_only_fields = ("acknowledged_by", "acknowledged_at")


from .models import SalesOrderPromise, CommercialServiceCase

class SalesOrderPromiseSerializer(serializers.ModelSerializer):
    sales_order_number = serializers.CharField(source="sales_order_line.sales_order.number", read_only=True)
    customer_name = serializers.CharField(source="sales_order_line.sales_order.customer_name", read_only=True)
    item_code = serializers.CharField(source="sales_order_line.item.code", read_only=True)
    line_number = serializers.IntegerField(source="sales_order_line.line_number", read_only=True)
    class Meta:
        model = SalesOrderPromise
        fields = "__all__"
        read_only_fields = ("previous_approved_date", "decided_by", "decided_at", "atp_result", "ctp_result")

class CommercialServiceCaseSerializer(serializers.ModelSerializer):
    sales_order_number = serializers.CharField(source="sales_order_line.sales_order.number", read_only=True)
    customer_name = serializers.CharField(source="sales_order_line.sales_order.customer_name", read_only=True)
    class Meta:
        model = CommercialServiceCase
        fields = "__all__"


from .models import SalesOrderCommercialContact, CustomerPromiseResponse, CommercialCommunication

class SalesOrderCommercialContactSerializer(serializers.ModelSerializer):
    sales_order_number = serializers.CharField(source="sales_order.number", read_only=True)
    class Meta:
        model = SalesOrderCommercialContact
        fields = "__all__"

class CustomerPromiseResponseSerializer(serializers.ModelSerializer):
    sales_order_number = serializers.CharField(source="promise.sales_order_line.sales_order.number", read_only=True)
    line_number = serializers.IntegerField(source="promise.sales_order_line.line_number", read_only=True)
    class Meta:
        model = CustomerPromiseResponse
        fields = "__all__"
        read_only_fields = ("received_at", "received_by")

class CommercialCommunicationSerializer(serializers.ModelSerializer):
    sales_order_number = serializers.CharField(source="promise.sales_order_line.sales_order.number", read_only=True)
    class Meta:
        model = CommercialCommunication
        fields = "__all__"
        read_only_fields = ("status", "sent_at", "error", "external_reference")


from .models import OTIFLineResult, ServiceLevelCause
class OTIFLineResultSerializer(serializers.ModelSerializer):
    sales_order_number=serializers.CharField(source="sales_order_line.sales_order.number",read_only=True)
    customer_code=serializers.CharField(source="sales_order_line.sales_order.customer_code",read_only=True)
    customer_name=serializers.CharField(source="sales_order_line.sales_order.customer_name",read_only=True)
    item_code=serializers.CharField(source="sales_order_line.item.code",read_only=True)
    line_number=serializers.IntegerField(source="sales_order_line.line_number",read_only=True)
    class Meta:
        model=OTIFLineResult; fields="__all__"
class ServiceLevelCauseSerializer(serializers.ModelSerializer):
    class Meta:
        model=ServiceLevelCause; fields="__all__"

from .models import ServiceLevelTarget, ServiceLevelPeriodSnapshot
class ServiceLevelTargetSerializer(serializers.ModelSerializer):
    class Meta:
        model = ServiceLevelTarget
        fields = "__all__"
class ServiceLevelPeriodSnapshotSerializer(serializers.ModelSerializer):
    plant_code = serializers.CharField(source="plant.code", read_only=True)
    class Meta:
        model = ServiceLevelPeriodSnapshot
        fields = "__all__"


# 0.7.8
from .models import ForecastAccuracySnapshot, ExecutiveSAndOPSnapshot, SAndOPScenario
class ForecastAccuracySnapshotSerializer(serializers.ModelSerializer):
    class Meta: model=ForecastAccuracySnapshot; fields='__all__'
class ExecutiveSAndOPSnapshotSerializer(serializers.ModelSerializer):
    class Meta: model=ExecutiveSAndOPSnapshot; fields='__all__'
class SAndOPScenarioSerializer(serializers.ModelSerializer):
    class Meta: model=SAndOPScenario; fields='__all__'; read_only_fields=['baseline','simulated','status','created_by','approved_by','approved_at']

# 0.7.9 — ciclo S&OP mensal formal
from .models import SAndOPCycle, SAndOPDemandConsensusLine, SAndOPSupplyPlanLine, SAndOPConstraint, SAndOPDecision, SAndOPPublication
class SAndOPCycleSerializer(serializers.ModelSerializer):
    plant_code = serializers.CharField(source="plant.code", read_only=True)
    class Meta:
        model=SAndOPCycle; fields="__all__"
        read_only_fields=("code","version","demand_baseline","demand_consensus_summary","supply_summary","constraints_summary","executive_summary","created_by","approved_by","approved_at","published_by","published_at","published_planning_run")
class SAndOPDemandConsensusLineSerializer(serializers.ModelSerializer):
    item_code=serializers.CharField(source="item.code",read_only=True)
    class Meta: model=SAndOPDemandConsensusLine; fields="__all__"
class SAndOPSupplyPlanLineSerializer(serializers.ModelSerializer):
    item_code=serializers.CharField(source="item.code",read_only=True)
    class Meta: model=SAndOPSupplyPlanLine; fields="__all__"
class SAndOPConstraintSerializer(serializers.ModelSerializer):
    class Meta: model=SAndOPConstraint; fields="__all__"
class SAndOPDecisionSerializer(serializers.ModelSerializer):
    class Meta: model=SAndOPDecision; fields="__all__"
class SAndOPPublicationSerializer(serializers.ModelSerializer):
    class Meta: model=SAndOPPublication; fields="__all__"

# 0.8.0 — MPS operacional semanal
from .models import MPSOperationalPolicy, OperationalMPSPublication, MPSWeeklyBucket, MPSRCCPException, MPSBucketChangeRequest
class MPSOperationalPolicySerializer(serializers.ModelSerializer):
    class Meta: model=MPSOperationalPolicy; fields="__all__"
class OperationalMPSPublicationSerializer(serializers.ModelSerializer):
    cycle_code=serializers.CharField(source="cycle.code",read_only=True)
    class Meta: model=OperationalMPSPublication; fields="__all__"
class MPSWeeklyBucketSerializer(serializers.ModelSerializer):
    item_code=serializers.CharField(source="item.code",read_only=True)
    class Meta: model=MPSWeeklyBucket; fields="__all__"
class MPSRCCPExceptionSerializer(serializers.ModelSerializer):
    work_center_code=serializers.CharField(source="work_center.code",read_only=True)
    class Meta: model=MPSRCCPException; fields="__all__"

# 0.8.1 — interactive MPS
class MPSBucketChangeRequestSerializer(serializers.ModelSerializer):
    item_code=serializers.CharField(source="source_bucket.item.code",read_only=True)
    class Meta: model=MPSBucketChangeRequest; fields="__all__"


# 0.8.2 — MPS revisioning
from .models import MPSRevision, MPSRevisionLine, MPSRevisionRCCPLine
class MPSRevisionSerializer(serializers.ModelSerializer):
    class Meta: model=MPSRevision; fields="__all__"
class MPSRevisionLineSerializer(serializers.ModelSerializer):
    item_code=serializers.CharField(source="item.code",read_only=True)
    class Meta: model=MPSRevisionLine; fields="__all__"
class MPSRevisionRCCPLineSerializer(serializers.ModelSerializer):
    work_center_code=serializers.CharField(source="work_center.code",read_only=True)
    class Meta: model=MPSRevisionRCCPLine; fields="__all__"

# 0.8.3 — MPS revision MRP what-if
from .models import MPSRevisionSimulation, MPSRevisionSimulationDiffLine
class MPSRevisionSimulationSerializer(serializers.ModelSerializer):
    revision_number=serializers.IntegerField(source="revision.number",read_only=True)
    compare_revision_number=serializers.IntegerField(source="compare_revision.number",read_only=True)
    class Meta: model=MPSRevisionSimulation; fields="__all__"
class MPSRevisionSimulationDiffLineSerializer(serializers.ModelSerializer):
    item_code=serializers.CharField(source="item.code",read_only=True)
    class Meta: model=MPSRevisionSimulationDiffLine; fields="__all__"


# 0.8.4 — financial what-if
from .models import MPSRevisionSimulationFinancialLine
class MPSRevisionSimulationFinancialLineSerializer(serializers.ModelSerializer):
    item_code=serializers.CharField(source="item.code",read_only=True)
    class Meta: model=MPSRevisionSimulationFinancialLine; fields="__all__"


# 0.8.5 — budget e cash-flow temporal
from .models import MPSFinancialBudget, MPSFinancialBudgetLine, MPSRevisionSimulationCashFlowBucket
class MPSFinancialBudgetSerializer(serializers.ModelSerializer):
    plant_code=serializers.CharField(source="plant.code",read_only=True)
    class Meta: model=MPSFinancialBudget; fields="__all__"
class MPSFinancialBudgetLineSerializer(serializers.ModelSerializer):
    class Meta: model=MPSFinancialBudgetLine; fields="__all__"
class MPSRevisionSimulationCashFlowBucketSerializer(serializers.ModelSerializer):
    class Meta: model=MPSRevisionSimulationCashFlowBucket; fields="__all__"


# 0.8.6 — working capital
from .models import WorkingCapitalPolicy, MPSRevisionSimulationWorkingCapitalBucket
class WorkingCapitalPolicySerializer(serializers.ModelSerializer):
    plant_code=serializers.CharField(source="plant.code",read_only=True)
    class Meta: model=WorkingCapitalPolicy; fields="__all__"
class MPSRevisionSimulationWorkingCapitalBucketSerializer(serializers.ModelSerializer):
    class Meta: model=MPSRevisionSimulationWorkingCapitalBucket; fields="__all__"

# 0.8.7 — financing capacity
from .models import FinancingPolicy, FinancingFacility, MPSRevisionSimulationFinancingBucket
class FinancingPolicySerializer(serializers.ModelSerializer):
    plant_code=serializers.CharField(source='plant.code',read_only=True)
    class Meta: model=FinancingPolicy; fields='__all__'
class FinancingFacilitySerializer(serializers.ModelSerializer):
    plant_code=serializers.CharField(source='plant.code',read_only=True)
    class Meta: model=FinancingFacility; fields='__all__'
class MPSRevisionSimulationFinancingBucketSerializer(serializers.ModelSerializer):
    class Meta: model=MPSRevisionSimulationFinancingBucket; fields='__all__'

# 0.8.8 — optimizer serializers
from .models import MPSOptimizationPolicy, MPSRevisionOptimizationRun, MPSRevisionOptimizationCandidate, MPSRevisionOptimizationAction
class MPSOptimizationPolicySerializer(serializers.ModelSerializer):
    plant_code=serializers.CharField(source='plant.code',read_only=True)
    class Meta: model=MPSOptimizationPolicy; fields='__all__'
class MPSRevisionOptimizationRunSerializer(serializers.ModelSerializer):
    revision_number=serializers.IntegerField(source='revision.number',read_only=True)
    compare_revision_number=serializers.IntegerField(source='compare_revision.number',read_only=True)
    class Meta: model=MPSRevisionOptimizationRun; fields='__all__'
class MPSRevisionOptimizationCandidateSerializer(serializers.ModelSerializer):
    generated_revision_number=serializers.IntegerField(source='generated_revision.number',read_only=True)
    class Meta: model=MPSRevisionOptimizationCandidate; fields='__all__'
class MPSRevisionOptimizationActionSerializer(serializers.ModelSerializer):
    item_code=serializers.CharField(source='item.code',read_only=True)
    supplier_from_code=serializers.CharField(source='supplier_from.code',read_only=True)
    supplier_to_code=serializers.CharField(source='supplier_to.code',read_only=True)
    class Meta: model=MPSRevisionOptimizationAction; fields='__all__'

# 0.9.0 — decision cockpit serializers
from .models import MPSDecisionCockpit, MPSDecisionCandidateReview
class MPSDecisionCockpitSerializer(serializers.ModelSerializer):
    publication_source=serializers.CharField(source='publication.source',read_only=True)
    plant_code=serializers.CharField(source='publication.cycle.plant.code',read_only=True)
    selected_candidate_name=serializers.CharField(source='selected_candidate.name',read_only=True)
    official_revision_number=serializers.IntegerField(source='official_revision.number',read_only=True)
    class Meta: model=MPSDecisionCockpit; fields='__all__'
class MPSDecisionCandidateReviewSerializer(serializers.ModelSerializer):
    candidate_name=serializers.CharField(source='candidate.name',read_only=True)
    candidate_rank=serializers.IntegerField(source='candidate.rank',read_only=True)
    pareto_rank=serializers.IntegerField(source='candidate.pareto_rank',read_only=True)
    class Meta: model=MPSDecisionCandidateReview; fields='__all__'; read_only_fields=('reviewed_by','reviewed_at')
    def validate(self,attrs):
        cockpit=attrs.get('cockpit') or getattr(self.instance,'cockpit',None)
        candidate=attrs.get('candidate') or getattr(self.instance,'candidate',None)
        if cockpit and candidate and candidate.optimization_run_id != cockpit.optimization_run_id:
            raise serializers.ValidationError('Candidato não pertence ao cockpit.')
        return attrs


# 0.9.1 — formal decision governance
from .models import MPSDecisionGovernancePolicy,MPSDecisionMeeting,MPSDecisionParticipant,MPSDecisionComment,MPSDecisionRiskAcceptance,MPSDecisionCondition,MPSDecisionAreaApproval,MPSDecisionAttachment
class _AllFields(serializers.ModelSerializer):
    class Meta: fields='__all__'
class MPSDecisionGovernancePolicySerializer(_AllFields):
    class Meta: model=MPSDecisionGovernancePolicy; fields='__all__'
class MPSDecisionMeetingSerializer(_AllFields):
    class Meta: model=MPSDecisionMeeting; fields='__all__'
class MPSDecisionParticipantSerializer(_AllFields):
    class Meta: model=MPSDecisionParticipant; fields='__all__'
class MPSDecisionCommentSerializer(_AllFields):
    class Meta: model=MPSDecisionComment; fields='__all__'; read_only_fields=('author',)
class MPSDecisionRiskAcceptanceSerializer(_AllFields):
    class Meta: model=MPSDecisionRiskAcceptance; fields='__all__'
class MPSDecisionConditionSerializer(_AllFields):
    class Meta: model=MPSDecisionCondition; fields='__all__'
class MPSDecisionAreaApprovalSerializer(_AllFields):
    class Meta: model=MPSDecisionAreaApproval; fields='__all__'; read_only_fields=('approver','decided_at')
class MPSDecisionAttachmentSerializer(_AllFields):
    class Meta: model=MPSDecisionAttachment; fields='__all__'; read_only_fields=('uploaded_by',)


# 0.9.2 — authority matrix / electronic approvals
from .models import MPSDecisionApprovalMatrix,MPSDecisionApprovalRequirement,MPSDecisionElectronicSignature
class MPSDecisionApprovalMatrixSerializer(serializers.ModelSerializer):
    plant_code=serializers.CharField(source='plant.code',read_only=True)
    class Meta: model=MPSDecisionApprovalMatrix; fields='__all__'
class MPSDecisionApprovalRequirementSerializer(serializers.ModelSerializer):
    level_display=serializers.CharField(source='get_level_display',read_only=True)
    signature_count=serializers.IntegerField(source='signatures.count',read_only=True)
    class Meta: model=MPSDecisionApprovalRequirement; fields='__all__'; read_only_fields=('status','satisfied_at','decision_content_hash','exposure_snapshot')
class MPSDecisionElectronicSignatureSerializer(serializers.ModelSerializer):
    signer_name=serializers.CharField(source='signer.get_username',read_only=True)
    class Meta: model=MPSDecisionElectronicSignature; fields='__all__'

# 0.9.3 — chained audit trail / evidence exports
from .models import MPSDecisionAuditEvent, MPSDecisionEvidenceExport
class MPSDecisionAuditEventSerializer(serializers.ModelSerializer):
    class Meta:
        model=MPSDecisionAuditEvent; fields='__all__'
class MPSDecisionEvidenceExportSerializer(serializers.ModelSerializer):
    generated_by_name=serializers.CharField(source='generated_by.get_username',read_only=True)
    class Meta:
        model=MPSDecisionEvidenceExport; fields='__all__'

# 0.9.4 — external audit anchors
from .models import MPSDecisionAuditAnchor
class MPSDecisionAuditAnchorSerializer(serializers.ModelSerializer):
    created_by_name=serializers.CharField(source='created_by.get_username',read_only=True)
    class Meta:
        model=MPSDecisionAuditAnchor; fields='__all__'; read_only_fields=('anchored_sequence','anchored_head_hash','anchored_at','receipt','receipt_hash','status','verified_at','verification_details','created_by')


# 0.9.5 — automatic anchor policy
from .models import MPSDecisionAnchorPolicy
class MPSDecisionAnchorPolicySerializer(serializers.ModelSerializer):
    plant_code=serializers.CharField(source='plant.code',read_only=True)
    class Meta:
        model=MPSDecisionAnchorPolicy; fields='__all__'

# 0.9.6 — security & compliance center
from .models import MPSDecisionCompliancePolicy, MPSDecisionComplianceIncident, MPSDecisionComplianceSnapshot
class MPSDecisionCompliancePolicySerializer(serializers.ModelSerializer):
    plant_code=serializers.CharField(source='plant.code',read_only=True)
    class Meta: model=MPSDecisionCompliancePolicy; fields='__all__'
class MPSDecisionComplianceIncidentSerializer(serializers.ModelSerializer):
    class Meta: model=MPSDecisionComplianceIncident; fields='__all__'; read_only_fields=('first_seen_at','last_seen_at','alerted_at','acknowledged_by','acknowledged_at','resolved_at')
class MPSDecisionComplianceSnapshotSerializer(serializers.ModelSerializer):
    plant_code=serializers.CharField(source='plant.code',read_only=True)
    class Meta: model=MPSDecisionComplianceSnapshot; fields='__all__'; read_only_fields=tuple(f.name for f in MPSDecisionComplianceSnapshot._meta.fields)

# 0.9.7 — Compliance SLA & Escalation Engine
from .models import MPSComplianceEscalationPolicy, MPSComplianceEscalationRule, MPSComplianceOnCallContact, MPSComplianceEscalationEvent
class MPSComplianceEscalationPolicySerializer(serializers.ModelSerializer):
    plant_code=serializers.CharField(source='plant.code',read_only=True)
    class Meta: model=MPSComplianceEscalationPolicy; fields='__all__'
class MPSComplianceEscalationRuleSerializer(serializers.ModelSerializer):
    class Meta: model=MPSComplianceEscalationRule; fields='__all__'
class MPSComplianceOnCallContactSerializer(serializers.ModelSerializer):
    plant_code=serializers.CharField(source='plant.code',read_only=True)
    class Meta: model=MPSComplianceOnCallContact; fields='__all__'
class MPSComplianceEscalationEventSerializer(serializers.ModelSerializer):
    class Meta: model=MPSComplianceEscalationEvent; fields='__all__'; read_only_fields=('activated_at','first_notified_at','last_notified_at','notification_count','recipients','details','stopped_at')


# 0.9.8 — corporate escalation calendar/channels
from .models import MPSComplianceHoliday,MPSComplianceOnCallAbsence,MPSComplianceOnCallSubstitution,MPSComplianceNotificationDelivery
class MPSComplianceHolidaySerializer(serializers.ModelSerializer):
    plant_code=serializers.CharField(source='plant.code',read_only=True)
    class Meta: model=MPSComplianceHoliday; fields='__all__'
class MPSComplianceOnCallAbsenceSerializer(serializers.ModelSerializer):
    class Meta: model=MPSComplianceOnCallAbsence; fields='__all__'
class MPSComplianceOnCallSubstitutionSerializer(serializers.ModelSerializer):
    class Meta: model=MPSComplianceOnCallSubstitution; fields='__all__'
class MPSComplianceNotificationDeliverySerializer(serializers.ModelSerializer):
    class Meta: model=MPSComplianceNotificationDelivery; fields='__all__'; read_only_fields=tuple(f.name for f in MPSComplianceNotificationDelivery._meta.fields)

# 0.9.9 — Incident Command & Postmortem
from .models import (
    MPSIncidentCommandPolicy, MPSMajorIncident, MPSMajorIncidentTimelineEvent,
    MPSMajorIncidentAction, MPSMajorIncidentPostmortem, MPSMajorIncidentLearningAction,
)
class MPSIncidentCommandPolicySerializer(serializers.ModelSerializer):
    plant_code=serializers.CharField(source='plant.code',read_only=True)
    class Meta: model=MPSIncidentCommandPolicy; fields='__all__'
class MPSMajorIncidentSerializer(serializers.ModelSerializer):
    plant_code=serializers.CharField(source='plant.code',read_only=True)
    commander_name=serializers.CharField(source='commander.get_username',read_only=True)
    class Meta: model=MPSMajorIncident; fields='__all__'; read_only_fields=('code','started_at','acknowledged_at','resolved_at','closed_at','closed_by')
class MPSMajorIncidentTimelineEventSerializer(serializers.ModelSerializer):
    actor_name=serializers.CharField(source='actor.get_username',read_only=True)
    class Meta: model=MPSMajorIncidentTimelineEvent; fields='__all__'; read_only_fields=('actor','occurred_at')
class MPSMajorIncidentActionSerializer(serializers.ModelSerializer):
    class Meta: model=MPSMajorIncidentAction; fields='__all__'; read_only_fields=('completed_at',)
class MPSMajorIncidentPostmortemSerializer(serializers.ModelSerializer):
    class Meta: model=MPSMajorIncidentPostmortem; fields='__all__'; read_only_fields=('approved_by','approved_at')
class MPSMajorIncidentLearningActionSerializer(serializers.ModelSerializer):
    class Meta: model=MPSMajorIncidentLearningAction; fields='__all__'; read_only_fields=('applied_at',)
