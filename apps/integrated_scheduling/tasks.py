from celery import shared_task
from django.contrib.auth import get_user_model
from django.utils import timezone

from .cp_sat_solver import solve_cp_sat
from .models import ScheduleSolverRun


@shared_task(bind=True, name="integrated_scheduling.run_cp_sat")
def run_cp_sat_task(self, run_id, params):
    run = ScheduleSolverRun.objects.select_related("scenario", "created_by").get(pk=run_id)
    if run.cancel_requested_at:
        run.status = ScheduleSolverRun.Status.CANCELLED
        run.finished_at = timezone.now()
        run.progress = {"phase": "cancelled-before-start"}
        run.save(update_fields=["status", "finished_at", "progress", "updated_at"])
        return {"run_id": run.pk, "status": run.status}
    run.celery_task_id = self.request.id or run.celery_task_id
    run.save(update_fields=["celery_task_id", "updated_at"])
    actor = run.created_by
    solved = solve_cp_sat(
        scenario=run.scenario,
        actor=actor,
        time_limit_seconds=params.get("time_limit_seconds", run.time_limit_seconds),
        workers=params.get("workers", run.workers),
        granularity_minutes=params.get("granularity_minutes", run.time_granularity_minutes),
        weights=params.get("weights") or run.weights,
        apply_to_scenario=params.get("apply_to_scenario", True),
        relative_gap_limit=params.get("relative_gap_limit", str(run.relative_gap_limit)),
        warm_start=params.get("warm_start", run.warm_start_enabled),
        run=run,
        execution_mode="ASYNC",
        preemptive_operations=params.get("preemptive_operations", run.preemptive_operations),
        max_consecutive_minutes=params.get("max_consecutive_minutes", run.max_consecutive_minutes),
        handoff_penalty=params.get("handoff_penalty", run.handoff_penalty),
        use_labor_constraints=params.get("use_labor_constraints", run.use_labor_constraints),
    )
    return {"run_id": solved.pk, "status": solved.status, "objective_value": str(solved.objective_value)}


def enqueue_cp_sat_solver(*, scenario, actor=None, time_limit_seconds=300, workers=8, granularity_minutes=5,
                          weights=None, apply_to_scenario=True, relative_gap_limit=0, warm_start=True,
                          preemptive_operations=False, max_consecutive_minutes=240, handoff_penalty=5,
                          use_labor_constraints=True):
    run = ScheduleSolverRun.objects.create(
        scenario=scenario,
        status=ScheduleSolverRun.Status.DRAFT,
        execution_mode="ASYNC",
        time_limit_seconds=max(1, min(int(time_limit_seconds), 7200)),
        workers=max(1, min(int(workers), 64)),
        time_granularity_minutes=max(1, min(int(granularity_minutes), 60)),
        weights=weights or {},
        relative_gap_limit=relative_gap_limit or 0,
        warm_start_enabled=bool(warm_start),
        preemptive_operations=bool(preemptive_operations),
        max_consecutive_minutes=max(1, int(max_consecutive_minutes or 240)),
        handoff_penalty=max(0, int(handoff_penalty or 0)),
        use_labor_constraints=bool(use_labor_constraints),
        created_by=actor,
        progress={"phase": "queued"},
    )
    try:
        task = run_cp_sat_task.delay(run.pk, {
            "time_limit_seconds": run.time_limit_seconds,
            "workers": run.workers,
            "granularity_minutes": run.time_granularity_minutes,
            "weights": run.weights,
            "apply_to_scenario": bool(apply_to_scenario),
            "relative_gap_limit": str(run.relative_gap_limit),
            "warm_start": bool(warm_start),
            "preemptive_operations": bool(preemptive_operations),
            "max_consecutive_minutes": max(1, int(max_consecutive_minutes or 240)),
            "handoff_penalty": max(0, int(handoff_penalty or 0)),
            "use_labor_constraints": bool(use_labor_constraints),
        })
        run.celery_task_id = task.id
        run.save(update_fields=["celery_task_id", "updated_at"])
        return run
    except Exception as exc:
        run.status = ScheduleSolverRun.Status.FAILED
        run.error_message = f"Falha ao enfileirar no Celery: {exc}"
        run.finished_at = timezone.now()
        run.progress = {"phase": "queue-failed"}
        run.save(update_fields=["status", "error_message", "finished_at", "progress", "updated_at"])
        raise

@shared_task(name="integrated_scheduling.auto_process_rescheduling_trigger")
def auto_process_rescheduling_trigger_task(trigger_id, horizon_days=14):
    from .models import ReschedulingTrigger, ScheduleSolverRun
    from .execution import prepare_rescheduling_scenario
    from .recovery import freeze_baseline_into_scenario, build_recovery_comparison
    trigger=ReschedulingTrigger.objects.select_related('publication','created_by').get(pk=trigger_id)
    if trigger.status in {ReschedulingTrigger.Status.READY, ReschedulingTrigger.Status.PUBLISHED}: return {'trigger_id':trigger.pk,'status':trigger.status}
    try:
        scenario=trigger.resulting_scenario or prepare_rescheduling_scenario(trigger=trigger, actor=trigger.created_by, horizon_days=horizon_days)
        freeze_baseline_into_scenario(trigger, scenario)
        run=ScheduleSolverRun.objects.create(scenario=scenario,status=ScheduleSolverRun.Status.DRAFT,execution_mode='ASYNC',
            time_limit_seconds=int((trigger.payload or {}).get('solver_time_limit',300)),workers=8,time_granularity_minutes=5,
            weights={},relative_gap_limit='0.02',warm_start_enabled=True,preemptive_operations=True,max_consecutive_minutes=240,
            handoff_penalty=5,use_labor_constraints=True,created_by=trigger.created_by,progress={'phase':'queued-recovery'})
        trigger.resulting_solver_run=run; trigger.status=ReschedulingTrigger.Status.SOLVING; trigger.auto_solver_enqueued_at=timezone.now()
        trigger.save(update_fields=['resulting_solver_run','status','auto_solver_enqueued_at','updated_at'])
        result=run_cp_sat_task(run_id=run.pk, params={'time_limit_seconds':run.time_limit_seconds,'workers':run.workers,
            'granularity_minutes':run.time_granularity_minutes,'relative_gap_limit':'0.02','warm_start':True,
            'preemptive_operations':True,'max_consecutive_minutes':240,'handoff_penalty':5,'use_labor_constraints':True,'apply_to_scenario':True})
        run.refresh_from_db()
        if run.status in {ScheduleSolverRun.Status.OPTIMAL,ScheduleSolverRun.Status.FEASIBLE}:
            cmp=build_recovery_comparison(trigger); trigger.recovery_summary=cmp['summary']; trigger.status=ReschedulingTrigger.Status.READY
        else: trigger.status=ReschedulingTrigger.Status.FAILED; trigger.error_message=run.error_message or f'Solver: {run.status}'
        trigger.processed_at=timezone.now(); trigger.save(update_fields=['recovery_summary','status','error_message','processed_at','updated_at'])
        return {'trigger_id':trigger.pk,'status':trigger.status,'run_id':run.pk}
    except Exception as exc:
        trigger.status=ReschedulingTrigger.Status.FAILED; trigger.error_message=str(exc); trigger.processed_at=timezone.now()
        trigger.save(update_fields=['status','error_message','processed_at','updated_at']); raise

@shared_task(name="integrated_scheduling.scan_material_shortages")
def scan_material_shortages_task(lookahead_hours=24):
    from .models import ProductionSchedulePublication, ReschedulingTrigger
    from .execution import create_rescheduling_trigger
    from .recovery import detect_material_shortages
    created=0
    for pub in ProductionSchedulePublication.objects.filter(status=ProductionSchedulePublication.Status.PUBLISHED).select_related('plant'):
        for s in detect_material_shortages(pub, lookahead_hours=lookahead_hours):
            tr=create_rescheduling_trigger(plant=pub.plant,publication=pub,trigger_type=ReschedulingTrigger.TriggerType.MATERIAL_SHORTAGE,
                source_type='WorkOrderMaterial',source_id=f"{s['work_order_id']}:{s['item_id']}",
                idempotency_key=f"material-shortage:{pub.pk}:{s['work_order_id']}:{s['item_id']}",payload=s)
            if tr.status==ReschedulingTrigger.Status.NEW:
                created+=1
                try: auto_process_rescheduling_trigger_task.delay(tr.pk)
                except Exception: pass
    return {'created':created}


@shared_task(name="integrated_scheduling.solve_recovery_plan")
def solve_recovery_plan_task(plan_id):
    from .models import RecoveryPlan, ScheduleSolverRun
    from .control_center import get_policy, score_plan, rank_recovery_plans, maybe_auto_publish
    plan = RecoveryPlan.objects.select_related("trigger__plant", "scenario", "trigger__created_by").get(pk=plan_id)
    policy = get_policy(plan.trigger.plant)
    plan.status = RecoveryPlan.Status.SOLVING
    plan.save(update_fields=["status", "updated_at"])
    weights = (plan.metrics or {}).get("weights") or {}
    run = ScheduleSolverRun.objects.create(
        scenario=plan.scenario, status=ScheduleSolverRun.Status.DRAFT, execution_mode="ASYNC",
        time_limit_seconds=policy.solver_time_limit_seconds, workers=8, time_granularity_minutes=5, weights=weights,
        relative_gap_limit="0.02", warm_start_enabled=True, preemptive_operations=True, max_consecutive_minutes=240,
        handoff_penalty=5, use_labor_constraints=True, created_by=plan.trigger.created_by, progress={"phase":"queued-recovery-plan"},
    )
    plan.solver_run = run
    plan.save(update_fields=["solver_run", "updated_at"])
    try:
        solved = solve_cp_sat(
            scenario=plan.scenario, actor=plan.trigger.created_by, time_limit_seconds=policy.solver_time_limit_seconds,
            workers=8, granularity_minutes=5, weights=weights, apply_to_scenario=True, relative_gap_limit="0.02",
            warm_start=True, run=run, execution_mode="ASYNC", preemptive_operations=True, max_consecutive_minutes=240,
            handoff_penalty=5, use_labor_constraints=True,
        )
        if solved.status in {ScheduleSolverRun.Status.OPTIMAL, ScheduleSolverRun.Status.FEASIBLE}:
            score_plan(plan)
        else:
            plan.status = RecoveryPlan.Status.FAILED; plan.error_message = solved.error_message or solved.status
            plan.save(update_fields=["status", "error_message", "updated_at"])
    except Exception as exc:
        plan.status = RecoveryPlan.Status.FAILED; plan.error_message = str(exc)
        plan.save(update_fields=["status", "error_message", "updated_at"]); raise
    trigger = plan.trigger
    finished = not trigger.recovery_plans.filter(status__in=[RecoveryPlan.Status.QUEUED, RecoveryPlan.Status.SOLVING, RecoveryPlan.Status.DRAFT]).exists()
    if finished:
        rank_recovery_plans(trigger)
        best = trigger.recovery_plans.filter(status=RecoveryPlan.Status.READY).order_by("rank").first()
        if best:
            trigger.resulting_scenario = best.scenario; trigger.resulting_solver_run = best.solver_run; trigger.status = trigger.Status.READY
            trigger.recovery_summary = best.metrics or {}; trigger.processed_at = timezone.now()
            trigger.save(update_fields=["resulting_scenario", "resulting_solver_run", "status", "recovery_summary", "processed_at", "updated_at"])
            maybe_auto_publish(trigger)
    return {"plan_id": plan.pk, "status": plan.status, "run_id": plan.solver_run_id}


@shared_task(name="integrated_scheduling.build_recovery_control_center")
def build_recovery_control_center_task(trigger_id, candidate_count=None, horizon_days=14):
    from .models import ReschedulingTrigger
    from .control_center import create_recovery_plans
    trigger = ReschedulingTrigger.objects.get(pk=trigger_id)
    plans = create_recovery_plans(trigger, candidate_count=candidate_count, horizon_days=horizon_days)
    queued = []
    for plan in plans:
        if plan.status == plan.Status.QUEUED:
            task = solve_recovery_plan_task.delay(plan.pk)
            queued.append({"plan_id": plan.pk, "task_id": task.id})
    return {"trigger_id": trigger.pk, "queued": queued}

@shared_task(name="integrated_scheduling.run_mps_revision_whatif")
def run_mps_revision_whatif_task(simulation_id):
    from .models import MPSRevisionSimulation
    from .mps_whatif import run_simulation
    sim=MPSRevisionSimulation.objects.get(pk=simulation_id)
    sim=run_simulation(sim)
    return {"simulation_id":sim.id,"status":sim.status,"target_run_id":sim.target_planning_run_id,"compare_run_id":sim.compare_planning_run_id}

@shared_task(name="integrated_scheduling.run_mps_optimizer")
def run_mps_optimizer_task(optimization_run_id):
    from .models import MPSRevisionOptimizationRun
    from .mps_optimizer import run_optimizer
    return run_optimizer(MPSRevisionOptimizationRun.objects.get(pk=optimization_run_id)).id


@shared_task(name="integrated_scheduling.run_mps_pareto_optimizer")
def run_mps_pareto_optimizer_task(optimization_run_id):
    from .models import MPSRevisionOptimizationRun
    from .mps_pareto_optimizer import run_pareto_optimizer
    return run_pareto_optimizer(MPSRevisionOptimizationRun.objects.get(pk=optimization_run_id)).id


@shared_task(name="integrated_scheduling.run_mps_anchor_policy")
def run_mps_anchor_policy_task():
    from .mps_anchor_policy import run_anchor_policy
    return run_anchor_policy()

@shared_task(name="integrated_scheduling.run_mps_security_compliance")
def run_mps_security_compliance_task():
    from .mps_security_compliance import run_security_compliance
    return run_security_compliance(remediate=True)

@shared_task(name="integrated_scheduling.run_mps_compliance_escalation")
def run_mps_compliance_escalation_task():
    from .mps_compliance_escalation import run_escalation_engine
    return run_escalation_engine(send_notifications=True)
