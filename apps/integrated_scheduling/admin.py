from django.contrib import admin
from .models import IntegratedScheduleBlock, IntegratedScheduleConflict, IntegratedScheduleScenario, PublishedOperationSchedule, IndustrialShiftBreak, IndustrialCalendarWindow, IntegratedScheduleSegment, ProductFamily, ItemSchedulingProfile, SequenceSetupRule


@admin.register(IntegratedScheduleScenario)
class IntegratedScheduleScenarioAdmin(admin.ModelAdmin):
    list_display = ("name", "plant", "horizon_start", "horizon_end", "scheduling_direction", "finite_by_machine", "status")
    list_filter = ("plant", "status", "scheduling_direction", "finite_by_machine")
    search_fields = ("name",)


@admin.register(IntegratedScheduleBlock)
class IntegratedScheduleBlockAdmin(admin.ModelAdmin):
    list_display = ("scenario", "block_type", "source_number", "work_center", "machine", "simulated_start", "simulated_end", "manually_locked")
    list_filter = ("block_type", "work_center", "manually_locked")
    search_fields = ("source_number", "description")


@admin.register(IntegratedScheduleConflict)
class IntegratedScheduleConflictAdmin(admin.ModelAdmin):
    list_display = ("scenario", "severity", "conflict_type", "work_center", "overlap_hours")
    list_filter = ("severity", "conflict_type", "work_center")


@admin.register(PublishedOperationSchedule)
class PublishedOperationScheduleAdmin(admin.ModelAdmin):
    list_display = ("operation", "work_center", "machine", "planned_start", "planned_end", "scenario", "published_at")
    list_filter = ("work_center", "machine")
    search_fields = ("operation__work_order__number", "operation__description")


@admin.register(IndustrialShiftBreak)
class IndustrialShiftBreakAdmin(admin.ModelAdmin):
    list_display = ("shift", "name", "start_time", "end_time", "is_active")
    list_filter = ("is_active", "shift__work_center")

@admin.register(IndustrialCalendarWindow)
class IndustrialCalendarWindowAdmin(admin.ModelAdmin):
    list_display = ("plant", "date", "window_type", "work_center", "machine", "start_time", "end_time", "capacity_factor")
    list_filter = ("plant", "window_type", "work_center")

@admin.register(IntegratedScheduleSegment)
class IntegratedScheduleSegmentAdmin(admin.ModelAdmin):
    list_display = ("block", "segment_type", "start", "end", "effective_hours", "capacity_factor")
    list_filter = ("segment_type",)


@admin.register(ProductFamily)
class ProductFamilyAdmin(admin.ModelAdmin):
    list_display = ("plant", "code", "name", "is_active")
    list_filter = ("plant", "is_active")
    search_fields = ("code", "name")

@admin.register(ItemSchedulingProfile)
class ItemSchedulingProfileAdmin(admin.ModelAdmin):
    list_display = ("plant", "item", "family", "commercial_priority", "campaign_code")
    list_filter = ("plant", "family")
    search_fields = ("item__code", "campaign_code")

@admin.register(SequenceSetupRule)
class SequenceSetupRuleAdmin(admin.ModelAdmin):
    list_display = ("plant", "work_center", "machine", "from_family", "to_family", "setup_hours", "is_active")
    list_filter = ("plant", "work_center", "machine", "is_active")

from .models import ScheduleOptimizationRun, ScheduleOptimizationCandidate
admin.site.register(ScheduleOptimizationRun)
admin.site.register(ScheduleOptimizationCandidate)

from .models import ScheduleSolverRun, ScheduleSolverAssignment, ScheduleSolverIncumbent, ScheduleSolverSegment, LaborSkill, LaborResource, LaborResourceSkill, LaborShiftAssignment, LaborUnavailability, OperationLaborRequirement, ScheduleSolverLaborAssignment, LaborRuleSet, ScheduleSolverLaborCost
admin.site.register(ScheduleSolverRun)
admin.site.register(ScheduleSolverAssignment)
admin.site.register(ScheduleSolverIncumbent)
admin.site.register(ScheduleSolverSegment)

for _m in [LaborSkill, LaborResource, LaborResourceSkill, LaborShiftAssignment, LaborUnavailability, OperationLaborRequirement, ScheduleSolverLaborAssignment]:
    try:
        admin.site.register(_m)
    except admin.sites.AlreadyRegistered:
        pass

admin.site.register(LaborRuleSet)
admin.site.register(ScheduleSolverLaborCost)

from .models import ProductionSchedulePublication, PublishedExecutionSlot, ScheduleExecutionDeviation, ReschedulingTrigger
for _m in [ProductionSchedulePublication, PublishedExecutionSlot, ScheduleExecutionDeviation, ReschedulingTrigger]:
    try:
        admin.site.register(_m)
    except admin.sites.AlreadyRegistered:
        pass

from .models import RecoveryPolicy, RecoveryPlan
for _m in [RecoveryPolicy, RecoveryPlan]:
    try:
        admin.site.register(_m)
    except admin.sites.AlreadyRegistered:
        pass

from .models import SalesOrderPromise, CommercialServiceCase
for _m in [SalesOrderPromise, CommercialServiceCase]:
    try: admin.site.register(_m)
    except admin.sites.AlreadyRegistered: pass

from .models import SalesOrderCommercialContact, CustomerPromiseResponse, CommercialCommunication
for _m in [SalesOrderCommercialContact, CustomerPromiseResponse, CommercialCommunication]:
    try: admin.site.register(_m)
    except admin.sites.AlreadyRegistered: pass


from .models import OTIFLineResult, ServiceLevelCause
for _m in [OTIFLineResult, ServiceLevelCause]:
    try: admin.site.register(_m)
    except admin.sites.AlreadyRegistered: pass

from .models import ServiceLevelTarget, ServiceLevelPeriodSnapshot
for _m in [ServiceLevelTarget, ServiceLevelPeriodSnapshot]:
    try: admin.site.register(_m)
    except admin.sites.AlreadyRegistered: pass

# 0.7.8
from .models import ForecastAccuracySnapshot, ExecutiveSAndOPSnapshot, SAndOPScenario
admin.site.register([ForecastAccuracySnapshot, ExecutiveSAndOPSnapshot, SAndOPScenario])

# 0.7.9
from .models import SAndOPCycle, SAndOPDemandConsensusLine, SAndOPSupplyPlanLine, SAndOPConstraint, SAndOPDecision, SAndOPPublication
for _m in [SAndOPCycle, SAndOPDemandConsensusLine, SAndOPSupplyPlanLine, SAndOPConstraint, SAndOPDecision, SAndOPPublication]:
    try: admin.site.register(_m)
    except admin.sites.AlreadyRegistered: pass

# 0.8.0
from .models import MPSOperationalPolicy, OperationalMPSPublication, MPSWeeklyBucket, MPSRCCPException
for _m in [MPSOperationalPolicy, OperationalMPSPublication, MPSWeeklyBucket, MPSRCCPException]:
    try: admin.site.register(_m)
    except admin.sites.AlreadyRegistered: pass

# 0.8.1 — interactive MPS
from .models import MPSBucketChangeRequest
@admin.register(MPSBucketChangeRequest)
class MPSBucketChangeRequestAdmin(admin.ModelAdmin):
    list_display=('id','publication','source_bucket','target_bucket','violation','status','requested_by','requested_at','decided_by')
    list_filter=('status','violation','publication')
    search_fields=('reason','decision_notes','source_bucket__item__code')


# 0.8.2
from .models import MPSRevision, MPSRevisionLine, MPSRevisionRCCPLine
admin.site.register(MPSRevision)
admin.site.register(MPSRevisionLine)
admin.site.register(MPSRevisionRCCPLine)

# 0.8.3 — MPS revision what-if
from .models import MPSRevisionSimulation, MPSRevisionSimulationDiffLine
@admin.register(MPSRevisionSimulation)
class MPSRevisionSimulationAdmin(admin.ModelAdmin):
    list_display=("id","revision","compare_revision","status","started_at","completed_at")
    list_filter=("status",)
    search_fields=("revision__publication__source",)
@admin.register(MPSRevisionSimulationDiffLine)
class MPSRevisionSimulationDiffLineAdmin(admin.ModelAdmin):
    list_display=("simulation","diff_type","item","event_date","left_quantity","right_quantity","delta_quantity")
    list_filter=("diff_type",)

# 0.8.4 — financial what-if
from .models import MPSRevisionSimulationFinancialLine
@admin.register(MPSRevisionSimulationFinancialLine)
class MPSRevisionSimulationFinancialLineAdmin(admin.ModelAdmin):
    list_display=("simulation","category","item","left_value","right_value","delta_value")
    list_filter=("category",)
    search_fields=("item__code","simulation__revision__publication__source")


# 0.8.5 — budget and temporal cash-flow
from .models import MPSFinancialBudget, MPSFinancialBudgetLine, MPSRevisionSimulationCashFlowBucket
@admin.register(MPSFinancialBudget)
class MPSFinancialBudgetAdmin(admin.ModelAdmin):
    list_display=("code","plant","period_start","period_end","bucket_type","status")
    list_filter=("plant","bucket_type","status")
@admin.register(MPSFinancialBudgetLine)
class MPSFinancialBudgetLineAdmin(admin.ModelAdmin):
    list_display=("budget","bucket_date","category","amount")
    list_filter=("category",)
@admin.register(MPSRevisionSimulationCashFlowBucket)
class MPSRevisionSimulationCashFlowBucketAdmin(admin.ModelAdmin):
    list_display=("simulation","bucket_date","category","left_value","right_value","budget_value","variance_to_budget")
    list_filter=("category",)


# 0.8.6 — working capital
from .models import WorkingCapitalPolicy, MPSRevisionSimulationWorkingCapitalBucket
@admin.register(WorkingCapitalPolicy)
class WorkingCapitalPolicyAdmin(admin.ModelAdmin):
    list_display=("plant","initial_cash_balance","minimum_cash_buffer","default_customer_terms_days","sales_tax_percent","freight_percent")
@admin.register(MPSRevisionSimulationWorkingCapitalBucket)
class MPSRevisionSimulationWorkingCapitalBucketAdmin(admin.ModelAdmin):
    list_display=("simulation","bucket_date","left_cumulative_cash","right_cumulative_cash","left_working_capital_need","right_working_capital_need")

# 0.8.7 — financing capacity
from .models import FinancingPolicy, FinancingFacility, MPSRevisionSimulationFinancingBucket
@admin.register(FinancingPolicy)
class FinancingPolicyAdmin(admin.ModelAdmin):
    list_display=('plant','block_revision_approval_when_exceeded','max_financing_utilization_percent')
@admin.register(FinancingFacility)
class FinancingFacilityAdmin(admin.ModelAdmin):
    list_display=('code','plant','limit_amount','annual_interest_rate_percent','priority','is_active')
    list_filter=('plant','is_active')
@admin.register(MPSRevisionSimulationFinancingBucket)
class MPSRevisionSimulationFinancingBucketAdmin(admin.ModelAdmin):
    list_display=('simulation','bucket_date','right_required_financing','right_financing_outstanding','right_uncovered_need','right_interest_expense')

# 0.8.8 optimizer
from .models import MPSOptimizationPolicy, MPSRevisionOptimizationRun, MPSRevisionOptimizationCandidate, MPSRevisionOptimizationAction
admin.site.register(MPSOptimizationPolicy)
admin.site.register(MPSRevisionOptimizationRun)
admin.site.register(MPSRevisionOptimizationCandidate)
admin.site.register(MPSRevisionOptimizationAction)

# 0.9.0 — executive decision cockpit
from .models import MPSDecisionCockpit, MPSDecisionCandidateReview
@admin.register(MPSDecisionCockpit)
class MPSDecisionCockpitAdmin(admin.ModelAdmin):
    list_display=('id','publication','optimization_run','status','selected_candidate','official_revision','approved_by','frozen_at')
    list_filter=('status','publication')
    search_fields=('publication__source','selection_rationale','executive_notes')
@admin.register(MPSDecisionCandidateReview)
class MPSDecisionCandidateReviewAdmin(admin.ModelAdmin):
    list_display=('cockpit','candidate','shortlisted','business_label','priority','reviewed_by')
    list_filter=('shortlisted','cockpit')


# 0.9.1 formal decision governance
from .models import MPSDecisionGovernancePolicy,MPSDecisionMeeting,MPSDecisionParticipant,MPSDecisionComment,MPSDecisionRiskAcceptance,MPSDecisionCondition,MPSDecisionAreaApproval,MPSDecisionAttachment
for _m in [MPSDecisionGovernancePolicy,MPSDecisionMeeting,MPSDecisionParticipant,MPSDecisionComment,MPSDecisionRiskAcceptance,MPSDecisionCondition,MPSDecisionAreaApproval,MPSDecisionAttachment]:
    try: admin.site.register(_m)
    except admin.sites.AlreadyRegistered: pass


# 0.9.2 approval authority / electronic signatures
from .models import MPSDecisionApprovalMatrix,MPSDecisionApprovalRequirement,MPSDecisionElectronicSignature
@admin.register(MPSDecisionApprovalMatrix)
class MPSDecisionApprovalMatrixAdmin(admin.ModelAdmin):
    list_display=('plant','name','level','priority','required_signatures','is_default','is_active')
    list_filter=('plant','level','is_default','is_active')
@admin.register(MPSDecisionApprovalRequirement)
class MPSDecisionApprovalRequirementAdmin(admin.ModelAdmin):
    list_display=('cockpit','level','required_signatures','status','satisfied_at')
    list_filter=('level','status')
@admin.register(MPSDecisionElectronicSignature)
class MPSDecisionElectronicSignatureAdmin(admin.ModelAdmin):
    list_display=('requirement','signer_username','authentication_method','signed_at','signature_version')
    readonly_fields=('requirement','signer','authentication_method','confirmation_statement','signed_at','content_hash','signature_hash','signature_version','signer_username','signer_groups','client_ip','user_agent','created_at','updated_at')
    def has_add_permission(self,request): return False
    def has_change_permission(self,request,obj=None): return False

# 0.9.3 chained audit/evidence — immutable through normal admin
from .models import MPSDecisionAuditEvent,MPSDecisionEvidenceExport
@admin.register(MPSDecisionAuditEvent)
class MPSDecisionAuditEventAdmin(admin.ModelAdmin):
    list_display=('cockpit','sequence','event_type','actor_username','occurred_at','event_hash')
    list_filter=('event_type','cockpit'); readonly_fields=[f.name for f in MPSDecisionAuditEvent._meta.fields]
    def has_add_permission(self,request): return False
    def has_change_permission(self,request,obj=None): return False
    def has_delete_permission(self,request,obj=None): return False
@admin.register(MPSDecisionEvidenceExport)
class MPSDecisionEvidenceExportAdmin(admin.ModelAdmin):
    list_display=('cockpit','generated_at','verification_ok','audit_event_count','package_sha256')
    readonly_fields=[f.name for f in MPSDecisionEvidenceExport._meta.fields]
    def has_add_permission(self,request): return False
    def has_change_permission(self,request,obj=None): return False

# 0.9.4 external anchors — immutable through normal admin
from .models import MPSDecisionAuditAnchor
@admin.register(MPSDecisionAuditAnchor)
class MPSDecisionAuditAnchorAdmin(admin.ModelAdmin):
    list_display=('cockpit','anchored_sequence','provider','status','anchored_at','anchored_head_hash')
    list_filter=('provider','status','cockpit'); readonly_fields=[f.name for f in MPSDecisionAuditAnchor._meta.fields]
    def has_add_permission(self,request): return False
    def has_change_permission(self,request,obj=None): return False
    def has_delete_permission(self,request,obj=None): return False


# 0.9.5 automatic anchor policy
from .models import MPSDecisionAnchorPolicy
@admin.register(MPSDecisionAnchorPolicy)
class MPSDecisionAnchorPolicyAdmin(admin.ModelAdmin):
    list_display=('plant','is_active','cadence','max_anchor_age_hours','retention_days','verify_after_publish','protect_active_cockpits')
    list_filter=('is_active','cadence','verify_after_publish','protect_active_cockpits')

# 0.9.6 Security & Compliance Center
from .models import MPSDecisionCompliancePolicy,MPSDecisionComplianceIncident,MPSDecisionComplianceSnapshot
@admin.register(MPSDecisionCompliancePolicy)
class MPSDecisionCompliancePolicyAdmin(admin.ModelAdmin):
    list_display=('plant','is_active','standard_sla_hours','high_sla_hours','critical_sla_hours','auto_export_evidence','evidence_max_age_hours','send_email_alerts')
    list_filter=('is_active','auto_export_evidence','send_email_alerts')
@admin.register(MPSDecisionComplianceIncident)
class MPSDecisionComplianceIncidentAdmin(admin.ModelAdmin):
    list_display=('cockpit','category','severity','status','first_seen_at','last_seen_at','alerted_at')
    list_filter=('category','severity','status')
    readonly_fields=('first_seen_at','last_seen_at','alerted_at','resolved_at')
@admin.register(MPSDecisionComplianceSnapshot)
class MPSDecisionComplianceSnapshotAdmin(admin.ModelAdmin):
    list_display=('plant','snapshot_date','protected_percent','evidence_current_percent','avg_minutes_to_first_anchor','integrity_failures','open_incidents')
    list_filter=('plant','snapshot_date'); readonly_fields=[f.name for f in MPSDecisionComplianceSnapshot._meta.fields]
    def has_add_permission(self,request): return False
    def has_change_permission(self,request,obj=None): return False

# 0.9.7 — compliance escalation admin
from .models import MPSComplianceEscalationPolicy,MPSComplianceEscalationRule,MPSComplianceOnCallContact,MPSComplianceEscalationEvent
@admin.register(MPSComplianceEscalationPolicy)
class MPSComplianceEscalationPolicyAdmin(admin.ModelAdmin): list_display=('plant','is_active','repeat_notifications','repeat_interval_minutes','send_email')
@admin.register(MPSComplianceEscalationRule)
class MPSComplianceEscalationRuleAdmin(admin.ModelAdmin): list_display=('policy','order','level','after_minutes','is_active'); list_filter=('level','is_active')
@admin.register(MPSComplianceOnCallContact)
class MPSComplianceOnCallContactAdmin(admin.ModelAdmin): list_display=('plant','name','email','is_active'); list_filter=('plant','is_active')
@admin.register(MPSComplianceEscalationEvent)
class MPSComplianceEscalationEventAdmin(admin.ModelAdmin): list_display=('incident','level','status','activated_at','notification_count','last_notified_at'); list_filter=('level','status'); readonly_fields=('incident','rule','level','status','activated_at','first_notified_at','last_notified_at','notification_count','recipients','details','stopped_at','created_at','updated_at')


# 0.9.8 — escalation calendar/channels
from .models import MPSComplianceHoliday,MPSComplianceOnCallAbsence,MPSComplianceOnCallSubstitution,MPSComplianceNotificationDelivery
@admin.register(MPSComplianceHoliday)
class MPSComplianceHolidayAdmin(admin.ModelAdmin): list_display=('plant','date','name','is_active'); list_filter=('plant','is_active')
@admin.register(MPSComplianceOnCallAbsence)
class MPSComplianceOnCallAbsenceAdmin(admin.ModelAdmin): list_display=('contact','starts_at','ends_at','reason','is_active'); list_filter=('is_active',)
@admin.register(MPSComplianceOnCallSubstitution)
class MPSComplianceOnCallSubstitutionAdmin(admin.ModelAdmin): list_display=('primary_contact','substitute_contact','starts_at','ends_at','is_active'); list_filter=('is_active',)
@admin.register(MPSComplianceNotificationDelivery)
class MPSComplianceNotificationDeliveryAdmin(admin.ModelAdmin):
    list_display=('event','channel','status','destination','attempted_at','response_code'); list_filter=('channel','status'); readonly_fields=[f.name for f in MPSComplianceNotificationDelivery._meta.fields]
    def has_add_permission(self,request): return False
    def has_change_permission(self,request,obj=None): return False

# 0.9.9 — Incident Command & Postmortem
from .models import MPSIncidentCommandPolicy,MPSMajorIncident,MPSMajorIncidentTimelineEvent,MPSMajorIncidentAction,MPSMajorIncidentPostmortem,MPSMajorIncidentLearningAction
@admin.register(MPSIncidentCommandPolicy)
class MPSIncidentCommandPolicyAdmin(admin.ModelAdmin): list_display=('plant','is_active')
@admin.register(MPSMajorIncident)
class MPSMajorIncidentAdmin(admin.ModelAdmin): list_display=('code','plant','severity','status','commander','started_at','resolved_at','closed_at'); list_filter=('plant','severity','status'); search_fields=('code','title','summary')
@admin.register(MPSMajorIncidentTimelineEvent)
class MPSMajorIncidentTimelineEventAdmin(admin.ModelAdmin): list_display=('incident','event_type','occurred_at','actor'); list_filter=('event_type',)
@admin.register(MPSMajorIncidentAction)
class MPSMajorIncidentActionAdmin(admin.ModelAdmin): list_display=('incident','action_type','title','owner','due_at','status'); list_filter=('action_type','status')
@admin.register(MPSMajorIncidentPostmortem)
class MPSMajorIncidentPostmortemAdmin(admin.ModelAdmin): list_display=('incident','status','root_cause_category','prepared_by','approved_by','approved_at'); list_filter=('status','root_cause_category')
@admin.register(MPSMajorIncidentLearningAction)
class MPSMajorIncidentLearningActionAdmin(admin.ModelAdmin): list_display=('postmortem','target_type','status','owner','applied_at'); list_filter=('target_type','status')
