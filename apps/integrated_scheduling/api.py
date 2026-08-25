from rest_framework import decorators, response, status, viewsets

from .models import IntegratedScheduleBlock, IntegratedScheduleConflict, IntegratedScheduleScenario, PublishedOperationSchedule, IndustrialShiftBreak, IndustrialCalendarWindow, IntegratedScheduleSegment, ProductFamily, ItemSchedulingProfile, SequenceSetupRule, ScheduleOptimizationRun, ScheduleOptimizationCandidate, ScheduleSolverRun, ScheduleSolverAssignment, ScheduleSolverIncumbent, ScheduleSolverSegment, LaborSkill, LaborResource, LaborResourceSkill, LaborShiftAssignment, LaborUnavailability, OperationLaborRequirement, ScheduleSolverLaborAssignment, LaborRuleSet, ScheduleSolverLaborCost
from .serializers import IntegratedScheduleBlockSerializer, IntegratedScheduleConflictSerializer, IntegratedScheduleScenarioSerializer, PublishedOperationScheduleSerializer, IndustrialShiftBreakSerializer, IndustrialCalendarWindowSerializer, IntegratedScheduleSegmentSerializer, ProductFamilySerializer, ItemSchedulingProfileSerializer, SequenceSetupRuleSerializer, ScheduleOptimizationRunSerializer, ScheduleOptimizationCandidateSerializer, ScheduleSolverRunSerializer, ScheduleSolverAssignmentSerializer, ScheduleSolverIncumbentSerializer, ScheduleSolverSegmentSerializer, LaborSkillSerializer, LaborResourceSerializer, LaborResourceSkillSerializer, LaborShiftAssignmentSerializer, LaborUnavailabilitySerializer, OperationLaborRequirementSerializer, ScheduleSolverLaborAssignmentSerializer, LaborRuleSetSerializer, ScheduleSolverLaborCostSerializer
from .services import apply_integrated_scenario
from .advanced import compare_scenarios, move_schedule_block, run_finite_scenario
from .optimizer import optimize_schedule
from .cp_sat_solver import solve_cp_sat, ortools_available, request_solver_cancel
from .tasks import enqueue_cp_sat_solver
from .solver_compare import compare_solver_methods
from apps.shopfloor.models import Machine
from django.utils.dateparse import parse_datetime


class IntegratedScheduleScenarioViewSet(viewsets.ModelViewSet):
    queryset = IntegratedScheduleScenario.objects.select_related("plant").all()
    serializer_class = IntegratedScheduleScenarioSerializer
    filterset_fields = ["plant", "status"]
    search_fields = ["name"]

    def perform_create(self, serializer):
        serializer.save(created_by=self.request.user if self.request.user.is_authenticated else None)

    @decorators.action(detail=True, methods=["post"])
    def simulate(self, request, pk=None):
        obj = run_finite_scenario(scenario=self.get_object(), actor=request.user)
        return response.Response(self.get_serializer(obj).data)

    @decorators.action(detail=True, methods=["post"])
    def apply(self, request, pk=None):
        try:
            obj = apply_integrated_scenario(scenario=self.get_object(), actor=request.user)
        except Exception as exc:
            return response.Response({"detail": str(exc)}, status=status.HTTP_409_CONFLICT)
        return response.Response(self.get_serializer(obj).data)

    @decorators.action(detail=True, methods=["post"], url_path="move-block")
    def move_block(self, request, pk=None):
        scenario = self.get_object()
        block = scenario.blocks.filter(pk=request.data.get("block_id")).first()
        if not block:
            return response.Response({"detail": "Bloco não encontrado."}, status=status.HTTP_404_NOT_FOUND)
        start = parse_datetime(request.data.get("start", ""))
        end = parse_datetime(request.data.get("end", ""))
        if not start or not end:
            return response.Response({"detail": "start/end ISO 8601 são obrigatórios."}, status=status.HTTP_400_BAD_REQUEST)
        machine = None
        if request.data.get("machine_id"):
            machine = Machine.objects.filter(pk=request.data["machine_id"], plant=scenario.plant).first()
            if not machine:
                return response.Response({"detail": "Máquina inválida."}, status=status.HTTP_400_BAD_REQUEST)
        try:
            move_schedule_block(block=block, start=start, end=end, machine=machine, actor=request.user)
        except Exception as exc:
            return response.Response({"detail": str(exc)}, status=status.HTTP_409_CONFLICT)
        return response.Response(IntegratedScheduleBlockSerializer(block).data)

    @decorators.action(detail=False, methods=["get"], url_path="compare")
    def compare(self, request):
        ids = request.query_params.getlist("scenario")
        qs = self.get_queryset().filter(pk__in=ids, status__in=[IntegratedScheduleScenario.Status.COMPLETED, IntegratedScheduleScenario.Status.APPLIED])
        return response.Response(compare_scenarios(qs))


class IntegratedScheduleBlockViewSet(viewsets.ReadOnlyModelViewSet):
    queryset = IntegratedScheduleBlock.objects.select_related("scenario", "work_center", "machine").all()
    serializer_class = IntegratedScheduleBlockSerializer
    filterset_fields = ["scenario", "block_type", "work_center", "machine"]


class IntegratedScheduleConflictViewSet(viewsets.ReadOnlyModelViewSet):
    queryset = IntegratedScheduleConflict.objects.select_related("scenario", "work_center").all()
    serializer_class = IntegratedScheduleConflictSerializer
    filterset_fields = ["scenario", "conflict_type", "severity", "work_center"]


class PublishedOperationScheduleViewSet(viewsets.ReadOnlyModelViewSet):
    queryset = PublishedOperationSchedule.objects.select_related("operation", "scenario", "work_center", "machine").all()
    serializer_class = PublishedOperationScheduleSerializer
    filterset_fields = ["scenario", "work_center", "machine"]


class IndustrialShiftBreakViewSet(viewsets.ModelViewSet):
    queryset = IndustrialShiftBreak.objects.select_related("shift", "shift__work_center").all()
    serializer_class = IndustrialShiftBreakSerializer
    filterset_fields = ["shift", "is_active"]

class IndustrialCalendarWindowViewSet(viewsets.ModelViewSet):
    queryset = IndustrialCalendarWindow.objects.select_related("plant", "work_center", "machine").all()
    serializer_class = IndustrialCalendarWindowSerializer
    filterset_fields = ["plant", "work_center", "machine", "date", "window_type"]

class IntegratedScheduleSegmentViewSet(viewsets.ReadOnlyModelViewSet):
    queryset = IntegratedScheduleSegment.objects.select_related("block", "block__scenario").all()
    serializer_class = IntegratedScheduleSegmentSerializer
    filterset_fields = ["block", "segment_type"]


class ProductFamilyViewSet(viewsets.ModelViewSet):
    queryset = ProductFamily.objects.select_related("plant").all()
    serializer_class = ProductFamilySerializer
    filterset_fields = ["plant", "is_active"]
    search_fields = ["code", "name"]

class ItemSchedulingProfileViewSet(viewsets.ModelViewSet):
    queryset = ItemSchedulingProfile.objects.select_related("plant", "item", "family").all()
    serializer_class = ItemSchedulingProfileSerializer
    filterset_fields = ["plant", "item", "family", "commercial_priority", "campaign_code"]

class SequenceSetupRuleViewSet(viewsets.ModelViewSet):
    queryset = SequenceSetupRule.objects.select_related("plant", "work_center", "machine", "from_family", "to_family").all()
    serializer_class = SequenceSetupRuleSerializer
    filterset_fields = ["plant", "work_center", "machine", "from_family", "to_family", "is_active"]


class ScheduleOptimizationRunViewSet(viewsets.ReadOnlyModelViewSet):
    queryset = ScheduleOptimizationRun.objects.select_related("base_scenario", "best_candidate").all()
    serializer_class = ScheduleOptimizationRunSerializer
    filterset_fields = ["base_scenario", "status"]

    @decorators.action(detail=False, methods=["post"], url_path="optimize")
    def optimize(self, request):
        scenario = IntegratedScheduleScenario.objects.filter(pk=request.data.get("scenario_id")).first()
        if not scenario:
            return response.Response({"detail": "scenario_id inválido."}, status=status.HTTP_400_BAD_REQUEST)
        try:
            run = optimize_schedule(
                base_scenario=scenario,
                candidate_count=request.data.get("candidate_count", 8),
                weights=request.data.get("weights") or {},
                actor=request.user if request.user.is_authenticated else None,
            )
        except Exception as exc:
            return response.Response({"detail": str(exc)}, status=status.HTTP_409_CONFLICT)
        return response.Response(self.get_serializer(run).data, status=status.HTTP_201_CREATED)


class ScheduleOptimizationCandidateViewSet(viewsets.ReadOnlyModelViewSet):
    queryset = ScheduleOptimizationCandidate.objects.select_related("run", "scenario").all()
    serializer_class = ScheduleOptimizationCandidateSerializer
    filterset_fields = ["run", "scenario", "feasible", "pareto_front", "rank"]


class ScheduleSolverRunViewSet(viewsets.ReadOnlyModelViewSet):
    queryset = ScheduleSolverRun.objects.select_related("scenario").all()
    serializer_class = ScheduleSolverRunSerializer
    filterset_fields = ["scenario", "status", "solver"]

    @decorators.action(detail=False, methods=["get"], url_path="availability")
    def availability(self, request):
        return response.Response({"solver": "CP-SAT", "available": ortools_available()})

    @decorators.action(detail=False, methods=["post"], url_path="solve")
    def solve(self, request):
        scenario = IntegratedScheduleScenario.objects.filter(pk=request.data.get("scenario_id")).first()
        if not scenario:
            return response.Response({"detail": "scenario_id inválido."}, status=status.HTTP_400_BAD_REQUEST)
        actor = request.user if request.user.is_authenticated else None
        params = dict(
            scenario=scenario, actor=actor, time_limit_seconds=request.data.get("time_limit_seconds", 30),
            workers=request.data.get("workers", 8), granularity_minutes=request.data.get("granularity_minutes", 5),
            weights=request.data.get("weights") or {}, apply_to_scenario=bool(request.data.get("apply_to_scenario", True)),
            relative_gap_limit=request.data.get("relative_gap_limit", 0), warm_start=bool(request.data.get("warm_start", True)),
            preemptive_operations=bool(request.data.get("preemptive_operations", False)),
            max_consecutive_minutes=request.data.get("max_consecutive_minutes", 240),
            handoff_penalty=request.data.get("handoff_penalty", 5),
            use_labor_constraints=bool(request.data.get("use_labor_constraints", True)),
        )
        try:
            if bool(request.data.get("async", False)):
                run = enqueue_cp_sat_solver(**params)
            else:
                run = solve_cp_sat(**params)
        except Exception as exc:
            return response.Response({"detail": str(exc)}, status=status.HTTP_409_CONFLICT)
        return response.Response(self.get_serializer(run).data, status=status.HTTP_202_ACCEPTED if run.execution_mode == "ASYNC" else status.HTTP_201_CREATED)

    @decorators.action(detail=True, methods=["post"], url_path="cancel")
    def cancel(self, request, pk=None):
        run = self.get_object()
        if run.status not in {ScheduleSolverRun.Status.DRAFT, ScheduleSolverRun.Status.RUNNING}:
            return response.Response({"detail": "A execução já terminou."}, status=status.HTTP_409_CONFLICT)
        request_solver_cancel(run, reason=request.data.get("reason") or "Cancelado via API")
        return response.Response(self.get_serializer(run).data)

    @decorators.action(detail=False, methods=["get"], url_path="compare-methods")
    def compare_methods(self, request):
        scenario = IntegratedScheduleScenario.objects.filter(pk=request.query_params.get("scenario_id")).first()
        if not scenario:
            return response.Response({"detail": "scenario_id inválido."}, status=status.HTTP_400_BAD_REQUEST)
        return response.Response(compare_solver_methods(scenario))


class ScheduleSolverAssignmentViewSet(viewsets.ReadOnlyModelViewSet):
    queryset = ScheduleSolverAssignment.objects.select_related("run", "operation", "work_center", "machine").all()
    serializer_class = ScheduleSolverAssignmentSerializer
    filterset_fields = ["run", "work_center", "machine", "is_alternate_resource"]


class ScheduleSolverIncumbentViewSet(viewsets.ReadOnlyModelViewSet):
    queryset = ScheduleSolverIncumbent.objects.select_related("run", "run__scenario").all()
    serializer_class = ScheduleSolverIncumbentSerializer
    filterset_fields = ["run"]


class ScheduleSolverSegmentViewSet(viewsets.ReadOnlyModelViewSet):
    queryset = ScheduleSolverSegment.objects.select_related("assignment", "assignment__run", "assignment__operation").all()
    serializer_class = ScheduleSolverSegmentSerializer
    filterset_fields = ["assignment", "calendar_kind", "shift_name"]


class LaborSkillViewSet(viewsets.ModelViewSet):
    queryset = LaborSkill.objects.select_related("plant").all()
    serializer_class = LaborSkillSerializer
    filterset_fields = ["plant", "is_active"]
    search_fields = ["code", "name"]

class LaborResourceViewSet(viewsets.ModelViewSet):
    queryset = LaborResource.objects.select_related("plant", "user", "operator_profile", "technician_profile").all()
    serializer_class = LaborResourceSerializer
    filterset_fields = ["plant", "resource_type", "is_active"]
    search_fields = ["employee_code", "name"]

class LaborResourceSkillViewSet(viewsets.ModelViewSet):
    queryset = LaborResourceSkill.objects.select_related("labor_resource", "skill").all()
    serializer_class = LaborResourceSkillSerializer
    filterset_fields = ["labor_resource", "skill", "proficiency"]

class LaborShiftAssignmentViewSet(viewsets.ModelViewSet):
    queryset = LaborShiftAssignment.objects.select_related("labor_resource", "shift", "shift__work_center").all()
    serializer_class = LaborShiftAssignmentSerializer
    filterset_fields = ["labor_resource", "shift", "is_active"]

class LaborUnavailabilityViewSet(viewsets.ModelViewSet):
    queryset = LaborUnavailability.objects.select_related("labor_resource").all()
    serializer_class = LaborUnavailabilitySerializer
    filterset_fields = ["labor_resource"]

class OperationLaborRequirementViewSet(viewsets.ModelViewSet):
    queryset = OperationLaborRequirement.objects.select_related("operation", "skill").all()
    serializer_class = OperationLaborRequirementSerializer
    filterset_fields = ["operation", "skill", "min_workers", "min_proficiency"]

class ScheduleSolverLaborAssignmentViewSet(viewsets.ReadOnlyModelViewSet):
    queryset = ScheduleSolverLaborAssignment.objects.select_related("run", "assignment", "segment", "operation", "labor_resource", "skill").all()
    serializer_class = ScheduleSolverLaborAssignmentSerializer
    filterset_fields = ["run", "assignment", "segment", "operation", "labor_resource", "skill", "is_handoff"]


class LaborRuleSetViewSet(viewsets.ModelViewSet):
    queryset = LaborRuleSet.objects.select_related("plant").all()
    serializer_class = LaborRuleSetSerializer
    filterset_fields = ["plant", "is_active"]

class ScheduleSolverLaborCostViewSet(viewsets.ReadOnlyModelViewSet):
    queryset = ScheduleSolverLaborCost.objects.select_related("labor_assignment", "labor_assignment__run", "labor_assignment__labor_resource", "rule_set").all()
    serializer_class = ScheduleSolverLaborCostSerializer
    filterset_fields = ["labor_assignment__run", "labor_assignment__labor_resource", "rule_set"]

# 0.7.1 — publicação e execução do plano ótimo
from .models import ProductionSchedulePublication, PublishedExecutionSlot, ScheduleExecutionDeviation, ReschedulingTrigger
from .serializers import ProductionSchedulePublicationSerializer, PublishedExecutionSlotSerializer, ScheduleExecutionDeviationSerializer, ReschedulingTriggerSerializer
from .execution import publish_solver_run, sync_execution_actuals, planned_vs_actual, create_rescheduling_trigger, prepare_rescheduling_scenario

class ProductionSchedulePublicationViewSet(viewsets.ReadOnlyModelViewSet):
    queryset = ProductionSchedulePublication.objects.select_related("plant", "scenario", "solver_run", "published_by").all()
    serializer_class = ProductionSchedulePublicationSerializer
    filterset_fields = ["plant", "status", "version", "solver_run"]

    @decorators.action(detail=False, methods=["post"], url_path="publish-solver")
    def publish_solver(self, request):
        run = ScheduleSolverRun.objects.filter(pk=request.data.get("solver_run_id")).first()
        if not run:
            return response.Response({"detail": "solver_run_id inválido."}, status=status.HTTP_400_BAD_REQUEST)
        try:
            pub = publish_solver_run(run=run, actor=request.user if request.user.is_authenticated else None,
                                     frozen_hours=request.data.get("frozen_hours", 24), notes=request.data.get("notes", ""))
        except Exception as exc:
            return response.Response({"detail": str(exc)}, status=status.HTTP_409_CONFLICT)
        return response.Response(self.get_serializer(pub).data, status=status.HTTP_201_CREATED)

    @decorators.action(detail=True, methods=["post"], url_path="sync-actuals")
    def sync_actuals(self, request, pk=None):
        pub = self.get_object()
        return response.Response(sync_execution_actuals(publication=pub, threshold_minutes=int(request.data.get("threshold_minutes", 15))))

    @decorators.action(detail=True, methods=["get"], url_path="planned-vs-actual")
    def planned_actual(self, request, pk=None):
        data = planned_vs_actual(self.get_object())
        return response.Response({k:v for k,v in data.items() if k != "rows"} | {"rows": [
            {"slot_id": r["slot"].pk, "operation_id": r["slot"].operation_id,
             "start_variance_minutes": r["start_variance_minutes"], "finish_variance_minutes": r["finish_variance_minutes"]}
            for r in data["rows"]]})

class PublishedExecutionSlotViewSet(viewsets.ReadOnlyModelViewSet):
    queryset = PublishedExecutionSlot.objects.select_related("publication", "operation", "work_center", "machine").all()
    serializer_class = PublishedExecutionSlotSerializer
    filterset_fields = ["publication", "work_center", "machine", "status", "frozen"]

class ScheduleExecutionDeviationViewSet(viewsets.ReadOnlyModelViewSet):
    queryset = ScheduleExecutionDeviation.objects.select_related("slot", "slot__publication").all()
    serializer_class = ScheduleExecutionDeviationSerializer
    filterset_fields = ["slot", "deviation_type"]

class ReschedulingTriggerViewSet(viewsets.ReadOnlyModelViewSet):
    queryset = ReschedulingTrigger.objects.select_related("plant", "publication", "resulting_scenario", "resulting_solver_run").all()
    serializer_class = ReschedulingTriggerSerializer

    @decorators.action(detail=True, methods=["post"], url_path="recover")
    def recover(self, request, pk=None):
        from .tasks import auto_process_rescheduling_trigger_task
        trigger=self.get_object()
        auto_process_rescheduling_trigger_task.delay(trigger.pk, int(request.data.get("horizon_days",14)))
        return response.Response({"id":trigger.pk,"status":"queued"}, status=status.HTTP_202_ACCEPTED)

    @decorators.action(detail=True, methods=["get"], url_path="compare")
    def compare(self, request, pk=None):
        from .recovery import build_recovery_comparison
        return response.Response(build_recovery_comparison(self.get_object()))

    @decorators.action(detail=True, methods=["post"], url_path="publish-recovery")
    def publish_recovery(self, request, pk=None):
        from .recovery import publish_recovery
        pub=publish_recovery(self.get_object(), actor=request.user, notes=request.data.get("notes",""))
        return response.Response(ProductionSchedulePublicationSerializer(pub).data, status=status.HTTP_201_CREATED)
    filterset_fields = ["plant", "trigger_type", "status", "auto_reschedule"]

    @decorators.action(detail=False, methods=["post"], url_path="trigger")
    def trigger(self, request):
        from apps.common.models import Plant
        plant = Plant.objects.filter(pk=request.data.get("plant_id")).first()
        if not plant:
            return response.Response({"detail": "plant_id inválido."}, status=status.HTTP_400_BAD_REQUEST)
        try:
            trig = create_rescheduling_trigger(
                plant=plant, trigger_type=request.data.get("trigger_type", "MANUAL"), source_type=request.data.get("source_type", ""),
                source_id=request.data.get("source_id", ""), payload=request.data.get("payload") or {},
                actor=request.user if request.user.is_authenticated else None, idempotency_key=request.data.get("idempotency_key"),
                auto_reschedule=bool(request.data.get("auto_reschedule", True)),
            )
            if trig.auto_reschedule and not trig.resulting_scenario_id:
                prepare_rescheduling_scenario(trigger=trig, actor=request.user if request.user.is_authenticated else None,
                                              horizon_days=request.data.get("horizon_days", 14))
        except Exception as exc:
            return response.Response({"detail": str(exc)}, status=status.HTTP_409_CONFLICT)
        return response.Response(self.get_serializer(trig).data, status=status.HTTP_201_CREATED)


from .models import RecoveryPolicy, RecoveryPlan
from .serializers import RecoveryPolicySerializer, RecoveryPlanSerializer

class RecoveryPolicyViewSet(viewsets.ModelViewSet):
    queryset = RecoveryPolicy.objects.select_related("plant").all()
    serializer_class = RecoveryPolicySerializer
    filterset_fields = ["plant", "is_active", "auto_publish_enabled"]

class RecoveryPlanViewSet(viewsets.ReadOnlyModelViewSet):
    queryset = RecoveryPlan.objects.select_related("trigger", "scenario", "solver_run").all()
    serializer_class = RecoveryPlanSerializer
    filterset_fields = ["trigger", "status", "strategy", "low_risk", "auto_publish_eligible", "rank"]

    @decorators.action(detail=False, methods=["post"], url_path="generate")
    def generate(self, request):
        from .models import ReschedulingTrigger
        from .tasks import build_recovery_control_center_task
        trigger = ReschedulingTrigger.objects.filter(pk=request.data.get("trigger_id")).first()
        if not trigger:
            return response.Response({"detail":"trigger_id inválido."}, status=status.HTTP_400_BAD_REQUEST)
        task = build_recovery_control_center_task.delay(trigger.pk, candidate_count=request.data.get("candidate_count"))
        return response.Response({"trigger_id":trigger.pk, "task_id":task.id}, status=status.HTTP_202_ACCEPTED)

from .models import RecoveryCommercialImpact, CommercialPromiseAlert
from .serializers import RecoveryCommercialImpactSerializer, CommercialPromiseAlertSerializer
from .commercial_pegging import rebuild_recovery_commercial_impact
from django.utils import timezone

class RecoveryCommercialImpactViewSet(viewsets.ReadOnlyModelViewSet):
    queryset = RecoveryCommercialImpact.objects.select_related("trigger", "recovery_plan", "sales_order_line__sales_order", "sales_order_line__item").all()
    serializer_class = RecoveryCommercialImpactSerializer
    filterset_fields = ["trigger", "recovery_plan", "sales_order_line", "promise_status", "pegging_method"]

class CommercialPromiseAlertViewSet(viewsets.ModelViewSet):
    queryset = CommercialPromiseAlert.objects.select_related("trigger", "recovery_plan", "sales_order_line__sales_order").all()
    serializer_class = CommercialPromiseAlertSerializer
    filterset_fields = ["trigger", "recovery_plan", "sales_order_line", "severity", "status"]

    @decorators.action(detail=True, methods=["post"])
    def acknowledge(self, request, pk=None):
        obj = self.get_object()
        obj.status = CommercialPromiseAlert.Status.ACKNOWLEDGED
        obj.acknowledged_by = request.user if request.user.is_authenticated else None
        obj.acknowledged_at = timezone.now()
        obj.save(update_fields=["status", "acknowledged_by", "acknowledged_at", "updated_at"])
        return response.Response(self.get_serializer(obj).data)

    @decorators.action(detail=False, methods=["post"], url_path="rebuild-trigger")
    def rebuild_trigger(self, request):
        trigger = ReschedulingTrigger.objects.filter(pk=request.data.get("trigger_id")).first()
        if not trigger:
            return response.Response({"detail": "Trigger não encontrado."}, status=status.HTTP_404_NOT_FOUND)
        result = rebuild_recovery_commercial_impact(trigger)
        return response.Response({"exact": result["exact"], "method": result["method"], "rows": len(result["rows"])})


# 0.7.4 — ATP/CTP por pedido e fila comercial
from .models import SalesOrderPromise, CommercialServiceCase
from .serializers import SalesOrderPromiseSerializer, CommercialServiceCaseSerializer
from .commercial_promising import evaluate_line_atp_ctp, approve_promise, reject_promise, create_recovery_promise_proposals
from apps.demand.models import SalesOrderLine

class SalesOrderPromiseViewSet(viewsets.ReadOnlyModelViewSet):
    queryset = SalesOrderPromise.objects.select_related("sales_order_line__sales_order", "sales_order_line__item", "trigger", "recovery_plan").all()
    serializer_class = SalesOrderPromiseSerializer
    filterset_fields = ["sales_order_line", "source", "status", "trigger", "recovery_plan"]

    @decorators.action(detail=False, methods=["post"], url_path="evaluate-line")
    def evaluate_line(self, request):
        line = SalesOrderLine.objects.select_related("sales_order__plant", "item").filter(pk=request.data.get("sales_order_line_id")).first()
        if not line:
            return response.Response({"detail":"sales_order_line_id inválido."}, status=status.HTTP_400_BAD_REQUEST)
        try:
            obj = evaluate_line_atp_ctp(line, actor=request.user if request.user.is_authenticated else None, run_ctp=bool(request.data.get("run_ctp", True)), horizon_days=int(request.data.get("horizon_days",365)))
        except Exception as exc:
            return response.Response({"detail":str(exc)}, status=status.HTTP_409_CONFLICT)
        return response.Response(self.get_serializer(obj).data, status=status.HTTP_201_CREATED)

    @decorators.action(detail=True, methods=["post"])
    def approve(self, request, pk=None):
        try: obj=approve_promise(self.get_object(), actor=request.user if request.user.is_authenticated else None)
        except Exception as exc: return response.Response({"detail":str(exc)}, status=status.HTTP_409_CONFLICT)
        return response.Response(self.get_serializer(obj).data)

    @decorators.action(detail=True, methods=["post"])
    def reject(self, request, pk=None):
        try: obj=reject_promise(self.get_object(), actor=request.user if request.user.is_authenticated else None, reason=request.data.get("reason", ""))
        except Exception as exc: return response.Response({"detail":str(exc)}, status=status.HTTP_409_CONFLICT)
        return response.Response(self.get_serializer(obj).data)

    @decorators.action(detail=False, methods=["post"], url_path="from-recovery")
    def from_recovery(self, request):
        trigger=ReschedulingTrigger.objects.filter(pk=request.data.get("trigger_id")).first()
        plan=RecoveryPlan.objects.filter(pk=request.data.get("recovery_plan_id"), trigger=trigger).first() if trigger else None
        if not trigger or not plan: return response.Response({"detail":"trigger_id/recovery_plan_id inválidos."}, status=status.HTTP_400_BAD_REQUEST)
        rows=create_recovery_promise_proposals(trigger, plan, actor=request.user if request.user.is_authenticated else None)
        return response.Response(self.get_serializer(rows, many=True).data, status=status.HTTP_201_CREATED)

class CommercialServiceCaseViewSet(viewsets.ModelViewSet):
    queryset = CommercialServiceCase.objects.select_related("sales_order_line__sales_order", "promise", "trigger", "recovery_plan", "owner").all()
    serializer_class = CommercialServiceCaseSerializer
    filterset_fields = ["status", "priority", "sales_order_line", "trigger", "recovery_plan", "owner"]

# 0.7.5 — comunicação e confirmação do cliente
from .models import SalesOrderCommercialContact, CustomerPromiseResponse, CommercialCommunication
from .serializers import SalesOrderCommercialContactSerializer, CustomerPromiseResponseSerializer, CommercialCommunicationSerializer
from .commercial_confirmation import send_promise_to_customer, record_customer_response
from django.utils.dateparse import parse_date

class SalesOrderCommercialContactViewSet(viewsets.ModelViewSet):
    queryset = SalesOrderCommercialContact.objects.select_related("sales_order").all()
    serializer_class = SalesOrderCommercialContactSerializer
    filterset_fields = ["sales_order", "preferred_channel", "is_active"]

class CustomerPromiseResponseViewSet(viewsets.ReadOnlyModelViewSet):
    queryset = CustomerPromiseResponse.objects.select_related("promise__sales_order_line__sales_order", "received_by").all()
    serializer_class = CustomerPromiseResponseSerializer
    filterset_fields = ["promise", "response", "channel"]

class CommercialCommunicationViewSet(viewsets.ReadOnlyModelViewSet):
    queryset = CommercialCommunication.objects.select_related("promise__sales_order_line__sales_order", "contact", "service_case").all()
    serializer_class = CommercialCommunicationSerializer
    filterset_fields = ["promise", "contact", "channel", "direction", "status"]

    @decorators.action(detail=False, methods=["post"], url_path="send-promise")
    def send_promise(self, request):
        promise = SalesOrderPromise.objects.filter(pk=request.data.get("promise_id")).first()
        contact = SalesOrderCommercialContact.objects.filter(pk=request.data.get("contact_id")).first() if request.data.get("contact_id") else None
        if not promise:
            return response.Response({"detail": "promise_id inválido."}, status=status.HTTP_400_BAD_REQUEST)
        try:
            obj = send_promise_to_customer(promise, contact=contact, actor=request.user if request.user.is_authenticated else None, channel=request.data.get("channel") or None)
        except Exception as exc:
            return response.Response({"detail": str(exc)}, status=status.HTTP_409_CONFLICT)
        return response.Response(self.get_serializer(obj).data, status=status.HTTP_201_CREATED)

    @decorators.action(detail=False, methods=["post"], url_path="customer-response")
    def customer_response(self, request):
        promise = SalesOrderPromise.objects.filter(pk=request.data.get("promise_id")).first()
        if not promise:
            return response.Response({"detail": "promise_id inválido."}, status=status.HTTP_400_BAD_REQUEST)
        try:
            obj = record_customer_response(
                promise,
                response=request.data.get("response"),
                actor=request.user if request.user.is_authenticated else None,
                channel=request.data.get("channel", "MANUAL"),
                confirmed_date=parse_date(request.data.get("confirmed_date")) if request.data.get("confirmed_date") else None,
                counterproposed_date=parse_date(request.data.get("counterproposed_date")) if request.data.get("counterproposed_date") else None,
                notes=request.data.get("notes", ""),
                external_reference=request.data.get("external_reference", ""),
                reevaluate=bool(request.data.get("reevaluate", True)),
            )
        except Exception as exc:
            return response.Response({"detail": str(exc)}, status=status.HTTP_409_CONFLICT)
        return response.Response(CustomerPromiseResponseSerializer(obj).data, status=status.HTTP_201_CREATED)


# 0.7.6 — OTIF/service level
from .models import OTIFLineResult, ServiceLevelCause
from .serializers import OTIFLineResultSerializer, ServiceLevelCauseSerializer
from .service_level import evaluate_otif_line, evaluate_otif_queryset, service_level_summary
class OTIFLineResultViewSet(viewsets.ReadOnlyModelViewSet):
    queryset=OTIFLineResult.objects.select_related("sales_order_line__sales_order","sales_order_line__item").all()
    serializer_class=OTIFLineResultSerializer
    filterset_fields=["reference","otif","on_time","in_full","primary_cause","sales_order_line"]
    @decorators.action(detail=False,methods=["post"],url_path="evaluate")
    def evaluate(self,request):
        ref=request.data.get("reference","CUSTOMER_ACCEPTED")
        line_id=request.data.get("sales_order_line_id")
        if line_id:
            line=SalesOrderLine.objects.filter(pk=line_id).first()
            if not line: return response.Response({"detail":"sales_order_line_id inválido."},status=status.HTTP_400_BAD_REQUEST)
            return response.Response(self.get_serializer(evaluate_otif_line(line,ref)).data)
        qs=SalesOrderLine.objects.exclude(sales_order__status="CANCELLED")
        evaluate_otif_queryset(qs,ref)
        out=OTIFLineResult.objects.filter(reference=ref)
        return response.Response(service_level_summary(out))
    @decorators.action(detail=False,methods=["get"],url_path="summary")
    def summary(self,request):
        qs=self.filter_queryset(self.get_queryset())
        return response.Response(service_level_summary(qs))
class ServiceLevelCauseViewSet(viewsets.ReadOnlyModelViewSet):
    queryset=ServiceLevelCause.objects.select_related("otif_result__sales_order_line__sales_order").all()
    serializer_class=ServiceLevelCauseSerializer
    filterset_fields=["category","is_primary","otif_result"]

# 0.7.7 — service-level management analytics
from .models import ServiceLevelTarget, ServiceLevelPeriodSnapshot
from .serializers import ServiceLevelTargetSerializer, ServiceLevelPeriodSnapshotSerializer
from .service_level_analytics import analytics, build_monthly_snapshots
class ServiceLevelTargetViewSet(viewsets.ModelViewSet):
    queryset = ServiceLevelTarget.objects.select_related("plant").all()
    serializer_class = ServiceLevelTargetSerializer
    filterset_fields = ["plant", "scope", "scope_key", "is_active"]
class ServiceLevelPeriodSnapshotViewSet(viewsets.ReadOnlyModelViewSet):
    queryset = ServiceLevelPeriodSnapshot.objects.select_related("plant").all()
    serializer_class = ServiceLevelPeriodSnapshotSerializer
    filterset_fields = ["plant", "reference", "period_start", "scope", "scope_key", "target_met"]
    @decorators.action(detail=False, methods=["post"], url_path="build-month")
    def build_month(self, request):
        from apps.common.models import Plant
        plant = Plant.objects.filter(pk=request.data.get("plant_id")).first()
        if not plant:
            return response.Response({"detail":"plant_id inválido."}, status=status.HTTP_400_BAD_REQUEST)
        try:
            rows = build_monthly_snapshots(plant, int(request.data["year"]), int(request.data["month"]), request.data.get("reference","CUSTOMER_ACCEPTED"))
        except Exception as exc:
            return response.Response({"detail":str(exc)}, status=status.HTTP_400_BAD_REQUEST)
        return response.Response({"snapshots": len(rows)})
    @decorators.action(detail=False, methods=["get"], url_path="trend")
    def trend(self, request):
        qs=self.filter_queryset(self.get_queryset()).order_by("period_start")
        return response.Response(self.get_serializer(qs, many=True).data)


# 0.7.8 — S&OP executive
from .models import ForecastAccuracySnapshot, ExecutiveSAndOPSnapshot, SAndOPScenario
from .serializers import ForecastAccuracySnapshotSerializer, ExecutiveSAndOPSnapshotSerializer, SAndOPScenarioSerializer
from .sop import calculate_forecast_accuracy, build_executive_snapshot, simulate_sop_scenario

class ForecastAccuracySnapshotViewSet(viewsets.ReadOnlyModelViewSet):
    queryset=ForecastAccuracySnapshot.objects.select_related('plant').all(); serializer_class=ForecastAccuracySnapshotSerializer
    filterset_fields=['plant','period_start','period_end']

class ExecutiveSAndOPSnapshotViewSet(viewsets.ReadOnlyModelViewSet):
    queryset=ExecutiveSAndOPSnapshot.objects.select_related('plant').all(); serializer_class=ExecutiveSAndOPSnapshotSerializer
    filterset_fields=['plant','period_start','period_end']
    @decorators.action(detail=False, methods=['post'], url_path='build')
    def build(self,request):
        from apps.common.models import Plant
        from django.utils.dateparse import parse_date
        plant=Plant.objects.filter(pk=request.data.get('plant_id')).first(); start=parse_date(request.data.get('start','')); end=parse_date(request.data.get('end',''))
        if not plant or not start or not end: return response.Response({'detail':'plant_id/start/end inválidos.'},status=status.HTTP_400_BAD_REQUEST)
        obj=build_executive_snapshot(plant,start,end); return response.Response(self.get_serializer(obj).data,status=status.HTTP_201_CREATED)

class SAndOPScenarioViewSet(viewsets.ModelViewSet):
    queryset=SAndOPScenario.objects.select_related('plant','created_by','approved_by').all(); serializer_class=SAndOPScenarioSerializer
    filterset_fields=['plant','status','horizon_start','horizon_end']
    def perform_create(self,serializer): serializer.save(created_by=self.request.user if self.request.user.is_authenticated else None)
    @decorators.action(detail=True,methods=['post'])
    def simulate(self,request,pk=None):
        obj=simulate_sop_scenario(self.get_object()); return response.Response(self.get_serializer(obj).data)
    @decorators.action(detail=True,methods=['post'])
    def approve(self,request,pk=None):
        obj=self.get_object(); obj.status=SAndOPScenario.Status.APPROVED; obj.approved_by=request.user if request.user.is_authenticated else None; obj.approved_at=timezone.now(); obj.save(update_fields=['status','approved_by','approved_at','updated_at']); return response.Response(self.get_serializer(obj).data)

# 0.7.9 — ciclo S&OP formal
from .models import SAndOPCycle, SAndOPDemandConsensusLine, SAndOPSupplyPlanLine, SAndOPConstraint, SAndOPDecision, SAndOPPublication
from .serializers import SAndOPCycleSerializer, SAndOPDemandConsensusLineSerializer, SAndOPSupplyPlanLineSerializer, SAndOPConstraintSerializer, SAndOPDecisionSerializer, SAndOPPublicationSerializer
from .sop_cycle import create_sop_cycle, refresh_demand_baseline, update_consensus_line, build_supply_review, advance_cycle, approve_cycle, publish_cycle_to_mps, summarize_constraints

class SAndOPCycleViewSet(viewsets.ModelViewSet):
    queryset=SAndOPCycle.objects.select_related('plant','approved_by','published_by').all(); serializer_class=SAndOPCycleSerializer
    filterset_fields=['plant','cycle_month','status','code','version']
    def create(self, request, *args, **kwargs):
        from apps.common.models import Plant
        from django.utils.dateparse import parse_date
        plant=Plant.objects.filter(pk=request.data.get('plant_id')).first(); cm=parse_date(request.data.get('cycle_month','')); end=parse_date(request.data.get('horizon_end',''))
        if not plant or not cm or not end: return response.Response({'detail':'plant_id/cycle_month/horizon_end inválidos.'},status=status.HTTP_400_BAD_REQUEST)
        obj=create_sop_cycle(plant,cm,end,user=request.user if request.user.is_authenticated else None,meeting_date=parse_date(request.data.get('meeting_date','')))
        return response.Response(self.get_serializer(obj).data,status=status.HTTP_201_CREATED)
    @decorators.action(detail=True,methods=['post'],url_path='refresh-demand')
    def refresh_demand(self,request,pk=None):
        try: obj=refresh_demand_baseline(self.get_object()); return response.Response(self.get_serializer(obj).data)
        except ValueError as e: return response.Response({'detail':str(e)},status=status.HTTP_409_CONFLICT)
    @decorators.action(detail=True,methods=['post'],url_path='build-supply')
    def build_supply(self,request,pk=None):
        try: obj=build_supply_review(self.get_object()); return response.Response(self.get_serializer(obj).data)
        except ValueError as e: return response.Response({'detail':str(e)},status=status.HTTP_409_CONFLICT)
    @decorators.action(detail=True,methods=['post'],url_path='advance')
    def advance(self,request,pk=None):
        try: obj=advance_cycle(self.get_object()); return response.Response(self.get_serializer(obj).data)
        except ValueError as e: return response.Response({'detail':str(e)},status=status.HTTP_409_CONFLICT)
    @decorators.action(detail=True,methods=['post'],url_path='approve')
    def approve_cycle_action(self,request,pk=None):
        try: obj=approve_cycle(self.get_object(),request.user if request.user.is_authenticated else None); return response.Response(self.get_serializer(obj).data)
        except ValueError as e: return response.Response({'detail':str(e)},status=status.HTTP_409_CONFLICT)
    @decorators.action(detail=True,methods=['post'],url_path='publish')
    def publish(self,request,pk=None):
        try:
            pub=publish_cycle_to_mps(self.get_object(),request.user if request.user.is_authenticated else None,bool(request.data.get('create_planning_run',True)))
            return response.Response(SAndOPPublicationSerializer(pub).data,status=status.HTTP_201_CREATED)
        except ValueError as e: return response.Response({'detail':str(e)},status=status.HTTP_409_CONFLICT)

class SAndOPDemandConsensusLineViewSet(viewsets.ModelViewSet):
    queryset=SAndOPDemandConsensusLine.objects.select_related('cycle','item').all(); serializer_class=SAndOPDemandConsensusLineSerializer
    filterset_fields=['cycle','item','bucket_date']
    @decorators.action(detail=True,methods=['post'],url_path='adjust')
    def adjust(self,request,pk=None):
        try: obj=update_consensus_line(self.get_object(),request.data.get('adjustment',0),request.data.get('rationale','')); return response.Response(self.get_serializer(obj).data)
        except ValueError as e: return response.Response({'detail':str(e)},status=status.HTTP_409_CONFLICT)
class SAndOPSupplyPlanLineViewSet(viewsets.ReadOnlyModelViewSet):
    queryset=SAndOPSupplyPlanLine.objects.select_related('cycle','item').all(); serializer_class=SAndOPSupplyPlanLineSerializer; filterset_fields=['cycle','item','bucket_date']
class SAndOPConstraintViewSet(viewsets.ModelViewSet):
    queryset=SAndOPConstraint.objects.select_related('cycle','owner').all(); serializer_class=SAndOPConstraintSerializer; filterset_fields=['cycle','category','severity','status']
class SAndOPDecisionViewSet(viewsets.ModelViewSet):
    queryset=SAndOPDecision.objects.select_related('cycle','owner').all(); serializer_class=SAndOPDecisionSerializer; filterset_fields=['cycle','category','status','owner']
class SAndOPPublicationViewSet(viewsets.ReadOnlyModelViewSet):
    queryset=SAndOPPublication.objects.select_related('cycle','planning_run','published_by').all(); serializer_class=SAndOPPublicationSerializer; filterset_fields=['cycle','mps_source','planning_run']


# 0.8.0 — Operational weekly MPS
from .models import MPSOperationalPolicy, OperationalMPSPublication, MPSWeeklyBucket, MPSRCCPException, MPSBucketChangeRequest
from .serializers import MPSOperationalPolicySerializer, OperationalMPSPublicationSerializer, MPSWeeklyBucketSerializer, MPSRCCPExceptionSerializer, MPSBucketChangeRequestSerializer
from .sop_mps import build_operational_mps, run_rccp, publish_operational_mps, execute_publication_mrp
class MPSOperationalPolicyViewSet(viewsets.ModelViewSet):
    queryset=MPSOperationalPolicy.objects.select_related('plant').all(); serializer_class=MPSOperationalPolicySerializer; filterset_fields=['plant','require_rccp_clear']
class OperationalMPSPublicationViewSet(viewsets.ReadOnlyModelViewSet):
    queryset=OperationalMPSPublication.objects.select_related('cycle','policy','planning_run').all(); serializer_class=OperationalMPSPublicationSerializer; filterset_fields=['cycle','status','as_of_date']
    @decorators.action(detail=False,methods=['post'],url_path='build')
    def build(self,request):
        from django.utils.dateparse import parse_date
        cycle=SAndOPCycle.objects.filter(pk=request.data.get('cycle_id')).first()
        if not cycle: return response.Response({'detail':'cycle_id inválido.'},status=status.HTTP_400_BAD_REQUEST)
        try: obj=build_operational_mps(cycle,request.user if request.user.is_authenticated else None,parse_date(request.data.get('as_of_date','')) if request.data.get('as_of_date') else None); return response.Response(self.get_serializer(obj).data,status=status.HTTP_201_CREATED)
        except ValueError as e: return response.Response({'detail':str(e)},status=status.HTTP_409_CONFLICT)
    @decorators.action(detail=True,methods=['post'],url_path='validate-rccp')
    def validate_rccp(self,request,pk=None):
        return response.Response(self.get_serializer(run_rccp(self.get_object())).data)
    @decorators.action(detail=True,methods=['post'],url_path='publish')
    def publish(self,request,pk=None):
        try: return response.Response(self.get_serializer(publish_operational_mps(self.get_object(),request.user if request.user.is_authenticated else None,bool(request.data.get('force',False)))).data)
        except ValueError as e: return response.Response({'detail':str(e)},status=status.HTTP_409_CONFLICT)
    @decorators.action(detail=True,methods=['post'],url_path='run-mrp')
    def run_mrp(self,request,pk=None):
        try:
            run=execute_publication_mrp(self.get_object()); return response.Response({'planning_run_id':run.id,'status':run.status})
        except ValueError as e: return response.Response({'detail':str(e)},status=status.HTTP_409_CONFLICT)
class MPSWeeklyBucketViewSet(viewsets.ReadOnlyModelViewSet):
    queryset=MPSWeeklyBucket.objects.select_related('publication','item','published_mps').all(); serializer_class=MPSWeeklyBucketSerializer; filterset_fields=['publication','item','bucket_start','mps_status']
    @decorators.action(detail=True,methods=['post'])
    def edit_quantity(self,request,pk=None):
        try:
            req=request_bucket_edit(self.get_object(),request.data.get('quantity'),request.user if request.user.is_authenticated else None,request.data.get('reason','')); return response.Response(MPSBucketChangeRequestSerializer(req).data)
        except ValueError as e: return response.Response({'detail':str(e)},status=status.HTTP_409_CONFLICT)
    @decorators.action(detail=True,methods=['post'])
    def move_volume(self,request,pk=None):
        target=MPSWeeklyBucket.objects.filter(pk=request.data.get('target_bucket_id')).first()
        if not target: return response.Response({'detail':'target_bucket_id inválido.'},status=status.HTTP_400_BAD_REQUEST)
        try:
            req=request_volume_move(self.get_object(),target,request.data.get('quantity'),request.user if request.user.is_authenticated else None,request.data.get('reason','')); return response.Response(MPSBucketChangeRequestSerializer(req).data)
        except ValueError as e: return response.Response({'detail':str(e)},status=status.HTTP_409_CONFLICT)
class MPSRCCPExceptionViewSet(viewsets.ModelViewSet):
    queryset=MPSRCCPException.objects.select_related('publication','work_center').all(); serializer_class=MPSRCCPExceptionSerializer; filterset_fields=['publication','work_center','bucket_start','severity','status']

# 0.8.1 — interactive MPS actions
from .mps_interactive import request_bucket_edit, request_volume_move, approve_change, reject_change
class MPSBucketChangeRequestViewSet(viewsets.ReadOnlyModelViewSet):
    queryset=MPSBucketChangeRequest.objects.select_related('publication','source_bucket__item','target_bucket','requested_by','decided_by').all()
    serializer_class=MPSBucketChangeRequestSerializer
    filterset_fields=['publication','status','violation','source_bucket','target_bucket']
    @decorators.action(detail=True,methods=['post'])
    def approve(self,request,pk=None):
        try: return response.Response(self.get_serializer(approve_change(self.get_object(),request.user if request.user.is_authenticated else None,request.data.get('notes',''))).data)
        except ValueError as e: return response.Response({'detail':str(e)},status=status.HTTP_409_CONFLICT)
    @decorators.action(detail=True,methods=['post'])
    def reject(self,request,pk=None):
        try: return response.Response(self.get_serializer(reject_change(self.get_object(),request.user if request.user.is_authenticated else None,request.data.get('notes',''))).data)
        except ValueError as e: return response.Response({'detail':str(e)},status=status.HTTP_409_CONFLICT)


# 0.8.2 — revision API
from .models import MPSRevision, MPSRevisionLine, MPSRevisionRCCPLine
from .serializers import MPSRevisionSerializer, MPSRevisionLineSerializer, MPSRevisionRCCPLineSerializer
from .mps_revision import capture_revision, compare_revisions, submit_revision, approve_revision, reject_revision, rollback_to_revision
class MPSRevisionViewSet(viewsets.ReadOnlyModelViewSet):
    queryset=MPSRevision.objects.select_related('publication','parent','created_by','approved_by').all()
    serializer_class=MPSRevisionSerializer
    filterset_fields=['publication','status','kind','number']
    @decorators.action(detail=False,methods=['post'],url_path='capture')
    def capture(self,request):
        pub=OperationalMPSPublication.objects.filter(pk=request.data.get('publication_id')).first()
        if not pub: return response.Response({'detail':'publication_id inválido.'},status=status.HTTP_400_BAD_REQUEST)
        try:
            rev=capture_revision(pub,request.user if request.user.is_authenticated else None,label=request.data.get('label','Revisão manual'),notes=request.data.get('notes',''))
            return response.Response(self.get_serializer(rev).data,status=status.HTTP_201_CREATED)
        except ValueError as e: return response.Response({'detail':str(e)},status=status.HTTP_409_CONFLICT)
    @decorators.action(detail=True,methods=['post'])
    def submit(self,request,pk=None):
        try:return response.Response(self.get_serializer(submit_revision(self.get_object(),request.user if request.user.is_authenticated else None)).data)
        except ValueError as e:return response.Response({'detail':str(e)},status=status.HTTP_409_CONFLICT)
    @decorators.action(detail=True,methods=['post'])
    def approve(self,request,pk=None):
        try:return response.Response(self.get_serializer(approve_revision(self.get_object(),request.user if request.user.is_authenticated else None,request.data.get('notes',''))).data)
        except ValueError as e:return response.Response({'detail':str(e)},status=status.HTTP_409_CONFLICT)
    @decorators.action(detail=True,methods=['post'])
    def reject(self,request,pk=None):
        try:return response.Response(self.get_serializer(reject_revision(self.get_object(),request.user if request.user.is_authenticated else None,request.data.get('notes',''))).data)
        except ValueError as e:return response.Response({'detail':str(e)},status=status.HTTP_409_CONFLICT)
    @decorators.action(detail=True,methods=['get'])
    def compare(self,request,pk=None):
        other=MPSRevision.objects.filter(pk=request.query_params.get('other')).first()
        if not other:return response.Response({'detail':'other inválido.'},status=status.HTTP_400_BAD_REQUEST)
        return response.Response(compare_revisions(self.get_object(),other))
    @decorators.action(detail=True,methods=['post'])
    def rollback(self,request,pk=None):
        rev=self.get_object()
        try:
            new=rollback_to_revision(rev.publication,rev,request.user if request.user.is_authenticated else None,request.data.get('reason',''))
            return response.Response(self.get_serializer(new).data,status=status.HTTP_201_CREATED)
        except ValueError as e:return response.Response({'detail':str(e)},status=status.HTTP_409_CONFLICT)
class MPSRevisionLineViewSet(viewsets.ReadOnlyModelViewSet):
    queryset=MPSRevisionLine.objects.select_related('revision','item').all(); serializer_class=MPSRevisionLineSerializer; filterset_fields=['revision','item','bucket_start','mps_status']
class MPSRevisionRCCPLineViewSet(viewsets.ReadOnlyModelViewSet):
    queryset=MPSRevisionRCCPLine.objects.select_related('revision','work_center').all(); serializer_class=MPSRevisionRCCPLineSerializer; filterset_fields=['revision','work_center','bucket_start','severity']

# 0.8.3 — MRP what-if API
from .models import MPSRevisionSimulation, MPSRevisionSimulationDiffLine
from .serializers import MPSRevisionSimulationSerializer, MPSRevisionSimulationDiffLineSerializer
from .mps_whatif import create_simulation, run_simulation
class MPSRevisionSimulationViewSet(viewsets.ReadOnlyModelViewSet):
    queryset=MPSRevisionSimulation.objects.select_related('revision','compare_revision','target_planning_run','compare_planning_run','created_by').all()
    serializer_class=MPSRevisionSimulationSerializer
    filterset_fields=['revision','compare_revision','status']
    @decorators.action(detail=False,methods=['post'],url_path='run')
    def run_whatif(self,request):
        rev=MPSRevision.objects.filter(pk=request.data.get('revision_id')).first()
        if not rev:return response.Response({'detail':'revision_id inválido.'},status=status.HTTP_400_BAD_REQUEST)
        comp=MPSRevision.objects.filter(pk=request.data.get('compare_revision_id')).first() if request.data.get('compare_revision_id') else None
        try:
            sim=create_simulation(rev,comp,request.user if request.user.is_authenticated else None)
            if request.data.get('async') in [True,'true','1',1]:
                try:
                    from .tasks import run_mps_revision_whatif_task
                    task=run_mps_revision_whatif_task.delay(sim.id)
                    data=self.get_serializer(sim).data; data['task_id']=task.id
                    return response.Response(data,status=status.HTTP_202_ACCEPTED)
                except Exception as exc:
                    sim.delete(); raise ValueError(f'Falha ao enfileirar simulação: {exc}')
            sim=run_simulation(sim)
            return response.Response(self.get_serializer(sim).data,status=status.HTTP_201_CREATED)
        except ValueError as e:return response.Response({'detail':str(e)},status=status.HTTP_409_CONFLICT)
    @decorators.action(detail=True,methods=['get'])
    def report(self,request,pk=None):
        sim=self.get_object()
        from .serializers import MPSRevisionSimulationFinancialLineSerializer, MPSRevisionSimulationCashFlowBucketSerializer, MPSRevisionSimulationWorkingCapitalBucketSerializer, MPSRevisionSimulationFinancingBucketSerializer
        return response.Response({'simulation':self.get_serializer(sim).data,'diff_lines':MPSRevisionSimulationDiffLineSerializer(sim.diff_lines.select_related('item').all(),many=True).data,'financial_lines':MPSRevisionSimulationFinancialLineSerializer(sim.financial_lines.select_related('item').all(),many=True).data,'cashflow_buckets':MPSRevisionSimulationCashFlowBucketSerializer(sim.cashflow_buckets.select_related('budget').all(),many=True).data,'working_capital_buckets':MPSRevisionSimulationWorkingCapitalBucketSerializer(sim.working_capital_buckets.all(),many=True).data,'financing_buckets':MPSRevisionSimulationFinancingBucketSerializer(sim.financing_buckets.all(),many=True).data})
class MPSRevisionSimulationDiffLineViewSet(viewsets.ReadOnlyModelViewSet):
    queryset=MPSRevisionSimulationDiffLine.objects.select_related('simulation','item').all(); serializer_class=MPSRevisionSimulationDiffLineSerializer
    filterset_fields=['simulation','diff_type','item','event_date']


# 0.8.4 — financial what-if API
from .models import MPSRevisionSimulationFinancialLine
from .serializers import MPSRevisionSimulationFinancialLineSerializer
class MPSRevisionSimulationFinancialLineViewSet(viewsets.ReadOnlyModelViewSet):
    queryset=MPSRevisionSimulationFinancialLine.objects.select_related('simulation','item').all()
    serializer_class=MPSRevisionSimulationFinancialLineSerializer
    filterset_fields=['simulation','category','item']


# 0.8.5 — budget and temporal cash-flow API
from django.utils import timezone as dj_timezone
from .models import MPSFinancialBudget, MPSFinancialBudgetLine, MPSRevisionSimulationCashFlowBucket
from .serializers import MPSFinancialBudgetSerializer, MPSFinancialBudgetLineSerializer, MPSRevisionSimulationCashFlowBucketSerializer
from .mps_cashflow_whatif import build_cashflow_impact
class MPSFinancialBudgetViewSet(viewsets.ModelViewSet):
    queryset=MPSFinancialBudget.objects.select_related("plant","approved_by").all()
    serializer_class=MPSFinancialBudgetSerializer
    filterset_fields=["plant","status","bucket_type"]
    @decorators.action(detail=True,methods=["post"])
    def approve(self,request,pk=None):
        obj=self.get_object(); obj.status=MPSFinancialBudget.Status.APPROVED; obj.approved_by=request.user if request.user.is_authenticated else None; obj.approved_at=dj_timezone.now(); obj.save(update_fields=["status","approved_by","approved_at","updated_at"]); return response.Response(self.get_serializer(obj).data)
class MPSFinancialBudgetLineViewSet(viewsets.ModelViewSet):
    queryset=MPSFinancialBudgetLine.objects.select_related("budget").all(); serializer_class=MPSFinancialBudgetLineSerializer
    filterset_fields=["budget","bucket_date","category"]
class MPSRevisionSimulationCashFlowBucketViewSet(viewsets.ReadOnlyModelViewSet):
    queryset=MPSRevisionSimulationCashFlowBucket.objects.select_related("simulation","budget").all(); serializer_class=MPSRevisionSimulationCashFlowBucketSerializer
    filterset_fields=["simulation","budget","bucket_date","category"]
    @decorators.action(detail=False,methods=["post"],url_path="rebuild")
    def rebuild(self,request):
        sim=MPSRevisionSimulation.objects.filter(pk=request.data.get("simulation_id")).first()
        if not sim:return response.Response({"detail":"simulation_id inválido."},status=status.HTTP_400_BAD_REQUEST)
        try: result=build_cashflow_impact(sim,request.data.get("budget_id"),request.data.get("bucket_type")); return response.Response(result)
        except ValueError as e:return response.Response({"detail":str(e)},status=status.HTTP_409_CONFLICT)


# 0.8.6 — working capital / cash conversion API
from .models import WorkingCapitalPolicy, MPSRevisionSimulationWorkingCapitalBucket
from .serializers import WorkingCapitalPolicySerializer, MPSRevisionSimulationWorkingCapitalBucketSerializer, MPSRevisionSimulationFinancingBucketSerializer
from .working_capital_whatif import build_working_capital_impact
class WorkingCapitalPolicyViewSet(viewsets.ModelViewSet):
    queryset=WorkingCapitalPolicy.objects.select_related("plant").all(); serializer_class=WorkingCapitalPolicySerializer; filterset_fields=["plant"]
class MPSRevisionSimulationWorkingCapitalBucketViewSet(viewsets.ReadOnlyModelViewSet):
    queryset=MPSRevisionSimulationWorkingCapitalBucket.objects.select_related("simulation").all(); serializer_class=MPSRevisionSimulationWorkingCapitalBucketSerializer; filterset_fields=["simulation","bucket_date"]
    @decorators.action(detail=False,methods=["post"],url_path="rebuild")
    def rebuild(self,request):
        sim=MPSRevisionSimulation.objects.filter(pk=request.data.get("simulation_id")).first()
        if not sim:return response.Response({"detail":"simulation_id inválido."},status=status.HTTP_400_BAD_REQUEST)
        try:return response.Response(build_working_capital_impact(sim,request.data.get("bucket_type")))
        except ValueError as e:return response.Response({"detail":str(e)},status=status.HTTP_409_CONFLICT)

# 0.8.7 — financing capacity
from .models import FinancingPolicy, FinancingFacility, MPSRevisionSimulationFinancingBucket
from .serializers import FinancingPolicySerializer, FinancingFacilitySerializer, MPSRevisionSimulationFinancingBucketSerializer
from .financing_whatif import build_financing_impact
class FinancingPolicyViewSet(viewsets.ModelViewSet):
    queryset=FinancingPolicy.objects.select_related('plant').all(); serializer_class=FinancingPolicySerializer; filterset_fields=['plant','block_revision_approval_when_exceeded']
class FinancingFacilityViewSet(viewsets.ModelViewSet):
    queryset=FinancingFacility.objects.select_related('plant').all(); serializer_class=FinancingFacilitySerializer; filterset_fields=['plant','is_active','priority']
class MPSRevisionSimulationFinancingBucketViewSet(viewsets.ReadOnlyModelViewSet):
    queryset=MPSRevisionSimulationFinancingBucket.objects.select_related('simulation').all(); serializer_class=MPSRevisionSimulationFinancingBucketSerializer; filterset_fields=['simulation','bucket_date']
    @decorators.action(detail=False,methods=['post'])
    def rebuild(self,request):
        sim=MPSRevisionSimulation.objects.filter(pk=request.data.get('simulation_id')).first()
        if not sim:return response.Response({'detail':'simulation_id inválido.'},status=status.HTTP_400_BAD_REQUEST)
        try:return response.Response(build_financing_impact(sim))
        except ValueError as e:return response.Response({'detail':str(e)},status=status.HTTP_409_CONFLICT)

# 0.8.8 — heuristic multi-criteria MPS optimizer
from .models import MPSOptimizationPolicy, MPSRevisionOptimizationRun, MPSRevisionOptimizationCandidate, MPSRevisionOptimizationAction
from .serializers import MPSOptimizationPolicySerializer, MPSRevisionOptimizationRunSerializer, MPSRevisionOptimizationCandidateSerializer, MPSRevisionOptimizationActionSerializer
from .mps_optimizer import create_optimization_run, run_optimizer, adopt_candidate
class MPSOptimizationPolicyViewSet(viewsets.ModelViewSet):
    queryset=MPSOptimizationPolicy.objects.select_related('plant').all(); serializer_class=MPSOptimizationPolicySerializer; filterset_fields=['plant','allow_supplier_switch']
class MPSRevisionOptimizationRunViewSet(viewsets.ReadOnlyModelViewSet):
    queryset=MPSRevisionOptimizationRun.objects.select_related('revision','compare_revision','created_by').all(); serializer_class=MPSRevisionOptimizationRunSerializer; filterset_fields=['revision','compare_revision','status']
    @decorators.action(detail=False,methods=['post'],url_path='run')
    def run_optimizer_action(self,request):
        rev=MPSRevision.objects.filter(pk=request.data.get('revision_id')).first()
        if not rev:return response.Response({'detail':'revision_id inválido.'},status=status.HTTP_400_BAD_REQUEST)
        comp=MPSRevision.objects.filter(pk=request.data.get('compare_revision_id')).first() if request.data.get('compare_revision_id') else None
        try:
            obj=create_optimization_run(rev,comp,request.user if request.user.is_authenticated else None)
            if request.data.get('async') in [True,'true','1',1]:
                from .tasks import run_mps_optimizer_task
                task=run_mps_optimizer_task.delay(obj.id)
                data=self.get_serializer(obj).data; data['task_id']=task.id
                return response.Response(data,status=status.HTTP_202_ACCEPTED)
            obj=run_optimizer(obj)
            return response.Response(self.get_serializer(obj).data,status=status.HTTP_201_CREATED)
        except ValueError as e:return response.Response({'detail':str(e)},status=status.HTTP_409_CONFLICT)
    @decorators.action(detail=False,methods=['post'],url_path='run-pareto')
    def run_pareto(self,request):
        rev=MPSRevision.objects.filter(pk=request.data.get('revision_id')).first()
        if not rev:return response.Response({'detail':'revision_id inválido.'},status=status.HTTP_400_BAD_REQUEST)
        comp=MPSRevision.objects.filter(pk=request.data.get('compare_revision_id')).first() if request.data.get('compare_revision_id') else None
        try:
            obj=create_optimization_run(rev,comp,request.user if request.user.is_authenticated else None)
            obj.optimizer_mode='CP_SAT_PARETO'; obj.save(update_fields=['optimizer_mode','updated_at'])
            if request.data.get('async') in [True,'true','1',1]:
                from .tasks import run_mps_pareto_optimizer_task
                task=run_mps_pareto_optimizer_task.delay(obj.id)
                data=self.get_serializer(obj).data; data['task_id']=task.id; data['ortools_available']=ortools_pareto_available()
                return response.Response(data,status=status.HTTP_202_ACCEPTED)
            obj=run_pareto_optimizer(obj)
            return response.Response(self.get_serializer(obj).data,status=status.HTTP_201_CREATED)
        except (ValueError,RuntimeError) as e:return response.Response({'detail':str(e)},status=status.HTTP_409_CONFLICT)

    @decorators.action(detail=True,methods=['get'],url_path='report')
    def report(self,request,pk=None):
        obj=self.get_object()
        cands=MPSRevisionOptimizationCandidateSerializer(obj.candidates.select_related('generated_revision','simulation').all(),many=True).data
        acts=MPSRevisionOptimizationActionSerializer(MPSRevisionOptimizationAction.objects.filter(candidate__optimization_run=obj).select_related('item','supplier_from','supplier_to'),many=True).data
        return response.Response({'optimization_run':self.get_serializer(obj).data,'candidates':cands,'actions':acts})
class MPSRevisionOptimizationCandidateViewSet(viewsets.ReadOnlyModelViewSet):
    queryset=MPSRevisionOptimizationCandidate.objects.select_related('optimization_run','generated_revision','simulation').all(); serializer_class=MPSRevisionOptimizationCandidateSerializer; filterset_fields=['optimization_run','strategy','rank','is_recommended']
    @decorators.action(detail=True,methods=['post'],url_path='adopt')
    def adopt(self,request,pk=None):
        try:
            rev=adopt_candidate(self.get_object(),request.user if request.user.is_authenticated else None,request.data.get('reason',''))
            return response.Response({'revision_id':rev.id,'revision_number':rev.number,'status':rev.status})
        except ValueError as e:return response.Response({'detail':str(e)},status=status.HTTP_409_CONFLICT)
class MPSRevisionOptimizationActionViewSet(viewsets.ReadOnlyModelViewSet):
    queryset=MPSRevisionOptimizationAction.objects.select_related('candidate','item','supplier_from','supplier_to').all(); serializer_class=MPSRevisionOptimizationActionSerializer; filterset_fields=['candidate','action_type','item']


# 0.8.9 — CP-SAT Pareto frontier
from .mps_pareto_optimizer import run_pareto_optimizer, ortools_pareto_available

# 0.9.0 — executive decision cockpit API
from .models import MPSDecisionCockpit, MPSDecisionCandidateReview, MPSRevisionOptimizationRun, MPSRevisionOptimizationCandidate
from .serializers import MPSDecisionCockpitSerializer, MPSDecisionCandidateReviewSerializer
from .mps_decision_cockpit import create_decision_cockpit, review_candidate, select_candidate, submit_decision, approve_decision, reject_decision, freeze_selected_as_official, candidate_comparison

class MPSDecisionCockpitViewSet(viewsets.ReadOnlyModelViewSet):
    queryset=MPSDecisionCockpit.objects.select_related('publication__cycle__plant','optimization_run','baseline_revision','selected_candidate','official_revision').all()
    serializer_class=MPSDecisionCockpitSerializer
    filterset_fields=['publication','optimization_run','status','selected_candidate','official_revision']

    @decorators.action(detail=False,methods=['post'],url_path='create-from-run')
    def create_from_run(self,request):
        run=MPSRevisionOptimizationRun.objects.filter(pk=request.data.get('optimization_run_id')).first()
        if not run:return response.Response({'detail':'optimization_run_id inválido.'},status=status.HTTP_400_BAD_REQUEST)
        try:
            obj=create_decision_cockpit(run,request.user if request.user.is_authenticated else None)
            return response.Response(self.get_serializer(obj).data,status=status.HTTP_201_CREATED)
        except ValueError as e:return response.Response({'detail':str(e)},status=status.HTTP_409_CONFLICT)

    @decorators.action(detail=True,methods=['post'],url_path='select')
    def select(self,request,pk=None):
        c=MPSRevisionOptimizationCandidate.objects.filter(pk=request.data.get('candidate_id')).select_related('simulation').first()
        if not c:return response.Response({'detail':'candidate_id inválido.'},status=status.HTTP_400_BAD_REQUEST)
        try:return response.Response(self.get_serializer(select_candidate(self.get_object(),c,request.user if request.user.is_authenticated else None,request.data.get('rationale',''))).data)
        except ValueError as e:return response.Response({'detail':str(e)},status=status.HTTP_409_CONFLICT)

    @decorators.action(detail=True,methods=['post'],url_path='submit')
    def submit_action(self,request,pk=None):
        try:return response.Response(self.get_serializer(submit_decision(self.get_object(),request.user if request.user.is_authenticated else None)).data)
        except ValueError as e:return response.Response({'detail':str(e)},status=status.HTTP_409_CONFLICT)

    @decorators.action(detail=True,methods=['post'],url_path='approve')
    def approve_action(self,request,pk=None):
        try:return response.Response(self.get_serializer(approve_decision(self.get_object(),request.user if request.user.is_authenticated else None,request.data.get('notes',''))).data)
        except ValueError as e:return response.Response({'detail':str(e)},status=status.HTTP_409_CONFLICT)

    @decorators.action(detail=True,methods=['post'],url_path='reject')
    def reject_action(self,request,pk=None):
        try:return response.Response(self.get_serializer(reject_decision(self.get_object(),request.user if request.user.is_authenticated else None,request.data.get('notes',''))).data)
        except ValueError as e:return response.Response({'detail':str(e)},status=status.HTTP_409_CONFLICT)

    @decorators.action(detail=True,methods=['post'],url_path='freeze-official')
    def freeze_official(self,request,pk=None):
        try:return response.Response(self.get_serializer(freeze_selected_as_official(self.get_object(),request.user if request.user.is_authenticated else None)).data)
        except ValueError as e:return response.Response({'detail':str(e)},status=status.HTTP_409_CONFLICT)

    @decorators.action(detail=True,methods=['get'],url_path='compare')
    def compare_action(self,request,pk=None):
        return response.Response(candidate_comparison(self.get_object(),request.query_params.get('left'),request.query_params.get('right')))

class MPSDecisionCandidateReviewViewSet(viewsets.ModelViewSet):
    queryset=MPSDecisionCandidateReview.objects.select_related('cockpit','candidate','reviewed_by').all()
    serializer_class=MPSDecisionCandidateReviewSerializer
    filterset_fields=['cockpit','candidate','shortlisted']
    http_method_names=['get','post','patch','head','options']

    def perform_create(self,serializer):
        serializer.save(reviewed_by=self.request.user if self.request.user.is_authenticated else None,reviewed_at=dj_timezone.now())


# 0.9.1 — formal decision minutes / approvals API
from .models import MPSDecisionGovernancePolicy,MPSDecisionMeeting,MPSDecisionParticipant,MPSDecisionComment,MPSDecisionRiskAcceptance,MPSDecisionCondition,MPSDecisionAreaApproval,MPSDecisionAttachment
from .serializers import MPSDecisionGovernancePolicySerializer,MPSDecisionMeetingSerializer,MPSDecisionParticipantSerializer,MPSDecisionCommentSerializer,MPSDecisionRiskAcceptanceSerializer,MPSDecisionConditionSerializer,MPSDecisionAreaApprovalSerializer,MPSDecisionAttachmentSerializer
from .mps_decision_governance import initialize_governance,record_area_decision,governance_check,formal_minutes_snapshot
class MPSDecisionGovernancePolicyViewSet(viewsets.ModelViewSet):
    queryset=MPSDecisionGovernancePolicy.objects.select_related('plant').all(); serializer_class=MPSDecisionGovernancePolicySerializer; filterset_fields=['plant','is_active']
class MPSDecisionMeetingViewSet(viewsets.ModelViewSet):
    queryset=MPSDecisionMeeting.objects.select_related('cockpit').all(); serializer_class=MPSDecisionMeetingSerializer; filterset_fields=['cockpit']
    @decorators.action(detail=True,methods=['post'],url_path='close')
    def close(self,request,pk=None):
        o=self.get_object(); o.closed_by=request.user if request.user.is_authenticated else None; o.closed_at=dj_timezone.now(); o.save(); return response.Response(self.get_serializer(o).data)
class MPSDecisionParticipantViewSet(viewsets.ModelViewSet):
    queryset=MPSDecisionParticipant.objects.select_related('meeting','user').all(); serializer_class=MPSDecisionParticipantSerializer; filterset_fields=['meeting','area','attended','is_decision_maker']
class MPSDecisionCommentViewSet(viewsets.ModelViewSet):
    queryset=MPSDecisionComment.objects.select_related('cockpit','author').all(); serializer_class=MPSDecisionCommentSerializer; filterset_fields=['cockpit','area','is_resolved']
    def perform_create(self,s): s.save(author=self.request.user if self.request.user.is_authenticated else None)
class MPSDecisionRiskAcceptanceViewSet(viewsets.ModelViewSet):
    queryset=MPSDecisionRiskAcceptance.objects.select_related('cockpit','owner','accepted_by').all(); serializer_class=MPSDecisionRiskAcceptanceSerializer; filterset_fields=['cockpit','category','status']
    @decorators.action(detail=True,methods=['post'],url_path='accept')
    def accept(self,request,pk=None):
        o=self.get_object(); o.status=MPSDecisionRiskAcceptance.Status.ACCEPTED; o.accepted_by=request.user if request.user.is_authenticated else None; o.accepted_at=dj_timezone.now(); o.save();
        from .mps_decision_audit import append_audit_event
        append_audit_event(o.cockpit, 'RISK_ACCEPTED', request.user if request.user.is_authenticated else None, {'risk_id':o.id,'category':o.category,'status':o.status})
        return response.Response(self.get_serializer(o).data)
class MPSDecisionConditionViewSet(viewsets.ModelViewSet):
    queryset=MPSDecisionCondition.objects.select_related('cockpit','owner').all(); serializer_class=MPSDecisionConditionSerializer; filterset_fields=['cockpit','status','owner']
class MPSDecisionAreaApprovalViewSet(viewsets.ReadOnlyModelViewSet):
    queryset=MPSDecisionAreaApproval.objects.select_related('cockpit','approver').all(); serializer_class=MPSDecisionAreaApprovalSerializer; filterset_fields=['cockpit','area','decision','is_required']
    @decorators.action(detail=True,methods=['post'],url_path='decide')
    def decide(self,request,pk=None):
        o=self.get_object()
        try: row=record_area_decision(o.cockpit,o.area,request.data.get('decision'),request.user if request.user.is_authenticated else None,request.data.get('comment','')); return response.Response(self.get_serializer(row).data)
        except ValueError as e:return response.Response({'detail':str(e)},status=status.HTTP_409_CONFLICT)
class MPSDecisionAttachmentViewSet(viewsets.ModelViewSet):
    queryset=MPSDecisionAttachment.objects.select_related('cockpit','uploaded_by').all(); serializer_class=MPSDecisionAttachmentSerializer; filterset_fields=['cockpit']
    def perform_create(self,s): s.save(uploaded_by=self.request.user if self.request.user.is_authenticated else None)


# 0.9.2 — authority matrix / electronic approval API
from .models import MPSDecisionApprovalMatrix,MPSDecisionApprovalRequirement,MPSDecisionElectronicSignature
from .serializers import MPSDecisionApprovalMatrixSerializer,MPSDecisionApprovalRequirementSerializer,MPSDecisionElectronicSignatureSerializer
from .mps_decision_authority import sign_requirement,authority_check,initialize_authority_requirements
class MPSDecisionApprovalMatrixViewSet(viewsets.ModelViewSet):
    queryset=MPSDecisionApprovalMatrix.objects.select_related('plant').all(); serializer_class=MPSDecisionApprovalMatrixSerializer; filterset_fields=['plant','level','is_default','is_active']
class MPSDecisionApprovalRequirementViewSet(viewsets.ReadOnlyModelViewSet):
    queryset=MPSDecisionApprovalRequirement.objects.select_related('cockpit','matrix_rule').prefetch_related('signatures').all(); serializer_class=MPSDecisionApprovalRequirementSerializer; filterset_fields=['cockpit','level','status']
    @decorators.action(detail=True,methods=['post'],url_path='sign')
    def sign(self,request,pk=None):
        try:
            sig=sign_requirement(self.get_object(),request.user if request.user.is_authenticated else None,password=request.data.get('password'),confirmation=request.data.get('confirmation',''),client_ip=request.META.get('REMOTE_ADDR'),user_agent=request.META.get('HTTP_USER_AGENT',''))
            return response.Response(MPSDecisionElectronicSignatureSerializer(sig).data,status=status.HTTP_201_CREATED)
        except ValueError as e:return response.Response({'detail':str(e)},status=status.HTTP_409_CONFLICT)
    @decorators.action(detail=False,methods=['post'],url_path='rebuild')
    def rebuild(self,request):
        c=MPSDecisionCockpit.objects.filter(pk=request.data.get('cockpit_id')).first()
        if not c:return response.Response({'detail':'cockpit_id inválido.'},status=status.HTTP_400_BAD_REQUEST)
        r=initialize_authority_requirements(c); return response.Response(self.get_serializer(r).data if r else {'detail':'Nenhuma regra de alçada aplicável.'})
class MPSDecisionElectronicSignatureViewSet(viewsets.ReadOnlyModelViewSet):
    queryset=MPSDecisionElectronicSignature.objects.select_related('requirement','signer').all(); serializer_class=MPSDecisionElectronicSignatureSerializer; filterset_fields=['requirement','signer','authentication_method']

# 0.9.3 — tamper-evident audit/evidence API
from .models import MPSDecisionAuditEvent, MPSDecisionEvidenceExport
from .serializers import MPSDecisionAuditEventSerializer, MPSDecisionEvidenceExportSerializer
from .mps_decision_audit import verify_audit_chain, build_evidence_zip
from django.http import HttpResponse
class MPSDecisionAuditEventViewSet(viewsets.ReadOnlyModelViewSet):
    queryset=MPSDecisionAuditEvent.objects.select_related('cockpit','actor').all(); serializer_class=MPSDecisionAuditEventSerializer; filterset_fields=['cockpit','event_type','actor']
    @decorators.action(detail=False,methods=['get'],url_path='verify')
    def verify(self,request):
        c=MPSDecisionCockpit.objects.filter(pk=request.query_params.get('cockpit_id')).first()
        if not c:return response.Response({'detail':'cockpit_id inválido.'},status=status.HTTP_400_BAD_REQUEST)
        return response.Response(verify_audit_chain(c))
class MPSDecisionEvidenceExportViewSet(viewsets.ReadOnlyModelViewSet):
    queryset=MPSDecisionEvidenceExport.objects.select_related('cockpit','generated_by').all(); serializer_class=MPSDecisionEvidenceExportSerializer; filterset_fields=['cockpit','verification_ok']
    @decorators.action(detail=False,methods=['post'],url_path='generate')
    def generate(self,request):
        c=MPSDecisionCockpit.objects.filter(pk=request.data.get('cockpit_id')).first()
        if not c:return response.Response({'detail':'cockpit_id inválido.'},status=status.HTTP_400_BAD_REQUEST)
        filename,raw,sha,manifest=build_evidence_zip(c,request.user if request.user.is_authenticated else None)
        resp=HttpResponse(raw,content_type='application/zip'); resp['Content-Disposition']=f'attachment; filename="{filename}"'; resp['X-Package-SHA256']=sha; return resp

# 0.9.4 — external integrity anchors API
from .models import MPSDecisionAuditAnchor
from .serializers import MPSDecisionAuditAnchorSerializer
from .mps_decision_anchor import publish_external_anchor, verify_external_anchor, verify_cockpit_against_latest_anchor
class MPSDecisionAuditAnchorViewSet(viewsets.ReadOnlyModelViewSet):
    queryset=MPSDecisionAuditAnchor.objects.select_related('cockpit','created_by').all(); serializer_class=MPSDecisionAuditAnchorSerializer; filterset_fields=['cockpit','provider','status']
    @decorators.action(detail=False,methods=['post'],url_path='publish')
    def publish(self,request):
        c=MPSDecisionCockpit.objects.filter(pk=request.data.get('cockpit_id')).first()
        if not c:return response.Response({'detail':'cockpit_id inválido.'},status=status.HTTP_400_BAD_REQUEST)
        try:
            a=publish_external_anchor(c,request.user if request.user.is_authenticated else None,provider=request.data.get('provider') or MPSDecisionAuditAnchor.Provider.FILE_APPEND_ONLY,external_reference=request.data.get('external_reference',''))
            return response.Response(self.get_serializer(a).data,status=status.HTTP_201_CREATED)
        except Exception as exc:return response.Response({'detail':str(exc)},status=status.HTTP_400_BAD_REQUEST)
    @decorators.action(detail=True,methods=['post'],url_path='verify')
    def verify_anchor(self,request,pk=None):
        return response.Response(verify_external_anchor(self.get_object(),request.user if request.user.is_authenticated else None,append_event=True))
    @decorators.action(detail=False,methods=['get'],url_path='verify-latest')
    def verify_latest(self,request):
        c=MPSDecisionCockpit.objects.filter(pk=request.query_params.get('cockpit_id')).first()
        if not c:return response.Response({'detail':'cockpit_id inválido.'},status=status.HTTP_400_BAD_REQUEST)
        return response.Response(verify_cockpit_against_latest_anchor(c))


# 0.9.5 — automatic anchor policy and protection dashboard API
from .models import MPSDecisionAnchorPolicy
from .serializers import MPSDecisionAnchorPolicySerializer
from .mps_anchor_policy import protection_dashboard, run_anchor_policy, protection_status
class MPSDecisionAnchorPolicyViewSet(viewsets.ModelViewSet):
    queryset=MPSDecisionAnchorPolicy.objects.select_related('plant').all()
    serializer_class=MPSDecisionAnchorPolicySerializer
    filterset_fields=['plant','is_active','cadence']
    @decorators.action(detail=False,methods=['post'],url_path='run-now')
    def run_now(self,request):
        return response.Response({'rows':run_anchor_policy(request.user if request.user.is_authenticated else None)})
    @decorators.action(detail=False,methods=['get'],url_path='protection-dashboard')
    def dashboard(self,request):
        rows=[]
        for x in protection_dashboard():
            rows.append({'cockpit_id':x['cockpit'].id,'plant':x['plant'].code,'cockpit_status':x['cockpit'].status,'protection':x['protection']})
        return response.Response({'rows':rows})

# 0.9.6 — Security & Compliance Center API
from .models import MPSDecisionCompliancePolicy,MPSDecisionComplianceIncident,MPSDecisionComplianceSnapshot
from .serializers import MPSDecisionCompliancePolicySerializer,MPSDecisionComplianceIncidentSerializer,MPSDecisionComplianceSnapshotSerializer
from .mps_security_compliance import run_security_compliance, compliance_dashboard
class MPSDecisionCompliancePolicyViewSet(viewsets.ModelViewSet):
    queryset=MPSDecisionCompliancePolicy.objects.select_related('plant').all(); serializer_class=MPSDecisionCompliancePolicySerializer; filterset_fields=['plant','is_active','auto_export_evidence','send_email_alerts']
    @decorators.action(detail=False,methods=['post'],url_path='run-now')
    def run_now(self,request):
        return response.Response({'rows':run_security_compliance(request.user if request.user.is_authenticated else None,remediate=True)})
    @decorators.action(detail=False,methods=['get'],url_path='dashboard')
    def dashboard(self,request):
        rows,snaps=compliance_dashboard()
        return response.Response({'rows':[{'cockpit_id':r['cockpit'].id,'plant':r['plant'].code,'criticality':r['criticality'],'sla_hours':r['sla_hours'],'protection':r['protection'],'open_incidents':[i.id for i in r['open_incidents']]} for r in rows], 'snapshots':MPSDecisionComplianceSnapshotSerializer(snaps,many=True).data})
class MPSDecisionComplianceIncidentViewSet(viewsets.ReadOnlyModelViewSet):
    queryset=MPSDecisionComplianceIncident.objects.select_related('cockpit','acknowledged_by').all(); serializer_class=MPSDecisionComplianceIncidentSerializer; filterset_fields=['cockpit','category','severity','status']
    @decorators.action(detail=True,methods=['post'])
    def acknowledge(self,request,pk=None):
        obj=self.get_object(); obj.status='ACKNOWLEDGED'; obj.acknowledged_by=request.user if request.user.is_authenticated else None; obj.acknowledged_at=timezone.now(); obj.save(update_fields=['status','acknowledged_by','acknowledged_at','updated_at']); return response.Response(self.get_serializer(obj).data)
class MPSDecisionComplianceSnapshotViewSet(viewsets.ReadOnlyModelViewSet):
    queryset=MPSDecisionComplianceSnapshot.objects.select_related('plant').all(); serializer_class=MPSDecisionComplianceSnapshotSerializer; filterset_fields=['plant','snapshot_date']

# 0.9.7 — Compliance SLA & Escalation Engine API
from .models import MPSComplianceEscalationPolicy,MPSComplianceEscalationRule,MPSComplianceOnCallContact,MPSComplianceEscalationEvent
from .serializers import MPSComplianceEscalationPolicySerializer,MPSComplianceEscalationRuleSerializer,MPSComplianceOnCallContactSerializer,MPSComplianceEscalationEventSerializer
from .mps_compliance_escalation import run_escalation_engine, escalation_metrics
class MPSComplianceEscalationPolicyViewSet(viewsets.ModelViewSet):
    queryset=MPSComplianceEscalationPolicy.objects.select_related('plant').all(); serializer_class=MPSComplianceEscalationPolicySerializer; filterset_fields=['plant','is_active','repeat_notifications','send_email']
    @decorators.action(detail=False,methods=['post'],url_path='run-now')
    def run_now(self,request):
        plant_id=request.data.get('plant_id'); plant=Plant.objects.filter(pk=plant_id).first() if plant_id else None
        return response.Response({'rows':run_escalation_engine(plant=plant,send_notifications=True)})
    @decorators.action(detail=False,methods=['get'],url_path='metrics')
    def metrics(self,request):
        plant=Plant.objects.filter(pk=request.query_params.get('plant_id')).first()
        if not plant:return response.Response({'detail':'plant_id inválido.'},status=status.HTTP_400_BAD_REQUEST)
        return response.Response(escalation_metrics(plant,int(request.query_params.get('days',30))))
class MPSComplianceEscalationRuleViewSet(viewsets.ModelViewSet):
    queryset=MPSComplianceEscalationRule.objects.select_related('policy__plant').all(); serializer_class=MPSComplianceEscalationRuleSerializer; filterset_fields=['policy','level','is_active']
class MPSComplianceOnCallContactViewSet(viewsets.ModelViewSet):
    queryset=MPSComplianceOnCallContact.objects.select_related('plant').all(); serializer_class=MPSComplianceOnCallContactSerializer; filterset_fields=['plant','is_active']
class MPSComplianceEscalationEventViewSet(viewsets.ReadOnlyModelViewSet):
    queryset=MPSComplianceEscalationEvent.objects.select_related('incident__cockpit','rule').all(); serializer_class=MPSComplianceEscalationEventSerializer; filterset_fields=['incident','rule','level','status']


# 0.9.8 — corporate escalation calendar/channels
from .models import MPSComplianceHoliday,MPSComplianceOnCallAbsence,MPSComplianceOnCallSubstitution,MPSComplianceNotificationDelivery
from .serializers import MPSComplianceHolidaySerializer,MPSComplianceOnCallAbsenceSerializer,MPSComplianceOnCallSubstitutionSerializer,MPSComplianceNotificationDeliverySerializer
class MPSComplianceHolidayViewSet(viewsets.ModelViewSet):
    queryset=MPSComplianceHoliday.objects.select_related('plant').all(); serializer_class=MPSComplianceHolidaySerializer; filterset_fields=['plant','date','is_active']
class MPSComplianceOnCallAbsenceViewSet(viewsets.ModelViewSet):
    queryset=MPSComplianceOnCallAbsence.objects.select_related('contact__plant').all(); serializer_class=MPSComplianceOnCallAbsenceSerializer; filterset_fields=['contact','is_active']
class MPSComplianceOnCallSubstitutionViewSet(viewsets.ModelViewSet):
    queryset=MPSComplianceOnCallSubstitution.objects.select_related('primary_contact','substitute_contact').all(); serializer_class=MPSComplianceOnCallSubstitutionSerializer; filterset_fields=['primary_contact','substitute_contact','is_active']
class MPSComplianceNotificationDeliveryViewSet(viewsets.ReadOnlyModelViewSet):
    queryset=MPSComplianceNotificationDelivery.objects.select_related('event__incident').all(); serializer_class=MPSComplianceNotificationDeliverySerializer; filterset_fields=['event','channel','status']

# 0.9.9 — Incident Command & Postmortem API
from .models import (
    MPSIncidentCommandPolicy, MPSMajorIncident, MPSMajorIncidentTimelineEvent,
    MPSMajorIncidentAction, MPSMajorIncidentPostmortem, MPSMajorIncidentLearningAction,
    MPSDecisionComplianceIncident,
)
from .serializers import (
    MPSIncidentCommandPolicySerializer, MPSMajorIncidentSerializer, MPSMajorIncidentTimelineEventSerializer,
    MPSMajorIncidentActionSerializer, MPSMajorIncidentPostmortemSerializer, MPSMajorIncidentLearningActionSerializer,
)
from .mps_incident_command import promote_compliance_incident, resolve_major_incident, close_major_incident, approve_postmortem, incident_command_metrics
class MPSIncidentCommandPolicyViewSet(viewsets.ModelViewSet):
    queryset=MPSIncidentCommandPolicy.objects.select_related('plant').all(); serializer_class=MPSIncidentCommandPolicySerializer; filterset_fields=['plant','is_active']
class MPSMajorIncidentViewSet(viewsets.ModelViewSet):
    queryset=MPSMajorIncident.objects.select_related('plant','commander','closed_by').prefetch_related('compliance_incidents').all(); serializer_class=MPSMajorIncidentSerializer; filterset_fields=['plant','severity','status','commander']; search_fields=['code','title','summary','impact']
    @decorators.action(detail=False,methods=['post'],url_path='promote-compliance')
    def promote_compliance(self,request):
        ci=MPSDecisionComplianceIncident.objects.filter(pk=request.data.get('compliance_incident_id')).first()
        if not ci:return response.Response({'detail':'compliance_incident_id inválido.'},status=status.HTTP_400_BAD_REQUEST)
        obj,created=promote_compliance_incident(ci,request.user if request.user.is_authenticated else None,request.data.get('title',''))
        return response.Response({'created':created,'incident':self.get_serializer(obj).data})
    @decorators.action(detail=True,methods=['post'])
    def resolve(self,request,pk=None):
        try: obj=resolve_major_incident(self.get_object(),request.user if request.user.is_authenticated else None,request.data.get('summary',''))
        except ValueError as exc:return response.Response({'detail':str(exc)},status=status.HTTP_400_BAD_REQUEST)
        return response.Response(self.get_serializer(obj).data)
    @decorators.action(detail=True,methods=['post'])
    def close(self,request,pk=None):
        try: obj=close_major_incident(self.get_object(),request.user if request.user.is_authenticated else None)
        except ValueError as exc:return response.Response({'detail':str(exc)},status=status.HTTP_400_BAD_REQUEST)
        return response.Response(self.get_serializer(obj).data)
    @decorators.action(detail=False,methods=['get'])
    def metrics(self,request):
        plant=Plant.objects.filter(pk=request.query_params.get('plant_id')).first() if request.query_params.get('plant_id') else None
        return response.Response(incident_command_metrics(plant,int(request.query_params.get('days',30))))
class MPSMajorIncidentTimelineEventViewSet(viewsets.ModelViewSet):
    queryset=MPSMajorIncidentTimelineEvent.objects.select_related('incident','actor').all(); serializer_class=MPSMajorIncidentTimelineEventSerializer; filterset_fields=['incident','event_type']
    def perform_create(self,serializer): serializer.save(actor=self.request.user if self.request.user.is_authenticated else None)
class MPSMajorIncidentActionViewSet(viewsets.ModelViewSet):
    queryset=MPSMajorIncidentAction.objects.select_related('incident','owner').all(); serializer_class=MPSMajorIncidentActionSerializer; filterset_fields=['incident','action_type','status','owner']
    @decorators.action(detail=True,methods=['post'])
    def complete(self,request,pk=None):
        obj=self.get_object(); obj.status='DONE'; obj.completed_at=timezone.now(); obj.verification=request.data.get('verification',obj.verification); obj.save(update_fields=['status','completed_at','verification','updated_at']); return response.Response(self.get_serializer(obj).data)
class MPSMajorIncidentPostmortemViewSet(viewsets.ModelViewSet):
    queryset=MPSMajorIncidentPostmortem.objects.select_related('incident','prepared_by','approved_by').all(); serializer_class=MPSMajorIncidentPostmortemSerializer; filterset_fields=['incident','status','root_cause_category']
    @decorators.action(detail=True,methods=['post'])
    def approve(self,request,pk=None): return response.Response(self.get_serializer(approve_postmortem(self.get_object(),request.user if request.user.is_authenticated else None)).data)
class MPSMajorIncidentLearningActionViewSet(viewsets.ModelViewSet):
    queryset=MPSMajorIncidentLearningAction.objects.select_related('postmortem__incident','owner').all(); serializer_class=MPSMajorIncidentLearningActionSerializer; filterset_fields=['postmortem','target_type','status','owner']
    @decorators.action(detail=True,methods=['post'])
    def apply(self,request,pk=None):
        obj=self.get_object(); obj.status='APPLIED'; obj.applied_at=timezone.now(); obj.evidence=request.data.get('evidence',obj.evidence); obj.save(update_fields=['status','applied_at','evidence','updated_at']); return response.Response(self.get_serializer(obj).data)
