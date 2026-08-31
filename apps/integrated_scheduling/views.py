from datetime import datetime, timedelta

from django.contrib import messages
from django.contrib.auth.decorators import login_required, permission_required
from django.db.models import Count, Prefetch
from django.http import JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.views.decorators.http import require_POST

from apps.common.models import Plant
from apps.shopfloor.models import Machine
from .models import IntegratedScheduleBlock, IntegratedScheduleScenario, ScheduleOptimizationRun, ScheduleSolverRun
from .services import apply_integrated_scenario, run_integrated_scenario
from .advanced import compare_scenarios, move_schedule_block, run_finite_scenario
from .optimizer import optimize_schedule
from .cp_sat_solver import solve_cp_sat, request_solver_cancel
from .tasks import enqueue_cp_sat_solver
from .solver_compare import compare_solver_methods


def _plant(request):
    pk = request.session.get("ui_plant_id")
    return Plant.objects.filter(pk=pk).first() or Plant.objects.order_by("code").first()


@login_required
def dashboard(request):
    plant = _plant(request)
    scenarios = IntegratedScheduleScenario.objects.filter(plant=plant).order_by("-created_at")[:20] if plant else []
    return render(request, "integrated_scheduling/dashboard.html", {"plant": plant, "scenarios": scenarios})


@login_required
@permission_required("integrated_scheduling.add_integratedschedulescenario", raise_exception=True)
def create_scenario(request):
    if request.method != "POST":
        return redirect("integrated-scheduling:dashboard")
    plant = _plant(request)
    start = timezone.localdate()
    days = int(request.POST.get("days") or 14)
    scenario = IntegratedScheduleScenario.objects.create(
        name=request.POST.get("name") or f"Integrado {start:%d/%m/%Y}",
        plant=plant,
        horizon_start=start,
        horizon_end=start + timedelta(days=max(1, min(days, 90)) - 1),
        scheduling_direction=request.POST.get("direction") if request.POST.get("direction") in {"FORWARD", "BACKWARD"} else "FORWARD",
        finite_by_machine=request.POST.get("finite_by_machine", "1") == "1",
        allow_alternate_resources=request.POST.get("allow_alternate_resources", "1") == "1",
        respect_industrial_calendar=request.POST.get("respect_industrial_calendar", "1") == "1",
        dispatch_rule=request.POST.get("dispatch_rule") if request.POST.get("dispatch_rule") in {"EDD", "SPT", "CR", "PRIORITY", "SETUP_MIN"} else "EDD",
        minimize_setups=request.POST.get("minimize_setups", "1") == "1",
        campaign_mode=request.POST.get("campaign_mode", "0") == "1",
        created_by=request.user,
    )
    run_finite_scenario(scenario=scenario, actor=request.user)
    return redirect("integrated-scheduling:detail", pk=scenario.pk)


@login_required
def detail(request, pk):
    scenario = get_object_or_404(IntegratedScheduleScenario.objects.select_related("plant"), pk=pk)
    blocks = scenario.blocks.select_related("work_center", "machine").all()
    conflicts = scenario.conflicts.select_related("work_center").all()
    centers = {}
    for block in blocks:
        centers.setdefault(block.work_center, []).append(block)
    machines = Machine.objects.filter(plant=scenario.plant, is_active=True).select_related("work_center").order_by("work_center__code", "code")
    return render(request, "integrated_scheduling/detail.html", {"scenario": scenario, "centers": centers, "conflicts": conflicts, "machines": machines})


@login_required
@permission_required("integrated_scheduling.change_integratedschedulescenario", raise_exception=True)
def simulate(request, pk):
    scenario = get_object_or_404(IntegratedScheduleScenario, pk=pk)
    run_finite_scenario(scenario=scenario, actor=request.user)
    messages.success(request, "Cenário recalculado.")
    return redirect("integrated-scheduling:detail", pk=pk)


@login_required
@permission_required("integrated_scheduling.change_integratedschedulescenario", raise_exception=True)
def apply(request, pk):
    scenario = get_object_or_404(IntegratedScheduleScenario, pk=pk)
    try:
        apply_integrated_scenario(scenario=scenario, actor=request.user)
        messages.success(request, "Cenário aplicado às operações de produção.")
    except Exception as exc:
        messages.error(request, str(exc))
    return redirect("integrated-scheduling:detail", pk=pk)


@login_required
@permission_required("integrated_scheduling.change_integratedscheduleblock", raise_exception=True)
def move_block(request, pk, block_pk):
    scenario = get_object_or_404(IntegratedScheduleScenario, pk=pk)
    block = get_object_or_404(IntegratedScheduleBlock, pk=block_pk, scenario=scenario)
    if request.method != "POST":
        return redirect("integrated-scheduling:detail", pk=pk)
    try:
        start = datetime.fromisoformat(request.POST["start"])
        end = datetime.fromisoformat(request.POST["end"])
        if timezone.is_naive(start):
            start = timezone.make_aware(start)
        if timezone.is_naive(end):
            end = timezone.make_aware(end)
        machine = None
        if request.POST.get("machine_id"):
            machine = get_object_or_404(Machine, pk=request.POST["machine_id"], plant=scenario.plant)
        move_schedule_block(block=block, start=start, end=end, machine=machine, actor=request.user, lock=True)
        if request.headers.get("HX-Request"):
            return JsonResponse({"ok": True, "block": block.pk})
        messages.success(request, "Bloco movido e travado manualmente.")
    except Exception as exc:
        if request.headers.get("HX-Request"):
            return JsonResponse({"ok": False, "detail": str(exc)}, status=409)
        messages.error(request, str(exc))
    return redirect("integrated-scheduling:detail", pk=pk)


@login_required
def compare(request):
    plant = _plant(request)
    ids = [int(x) for x in request.GET.getlist("scenario") if x.isdigit()]
    qs = IntegratedScheduleScenario.objects.filter(plant=plant, status__in=["COMPLETED", "APPLIED"]).order_by("-created_at")
    selected = list(qs.filter(pk__in=ids)) if ids else list(qs[:4])
    rows = compare_scenarios(selected)
    return render(request, "integrated_scheduling/compare.html", {"plant": plant, "scenarios": qs[:20], "rows": rows, "selected_ids": ids})


@login_required
@permission_required("integrated_scheduling.add_scheduleoptimizationrun", raise_exception=True)
def optimize(request, pk):
    scenario = get_object_or_404(IntegratedScheduleScenario, pk=pk)
    if request.method != "POST":
        return redirect("integrated-scheduling:detail", pk=pk)
    try:
        weights = {
            "lateness": request.POST.get("w_lateness", "0.30"),
            "setup": request.POST.get("w_setup", "0.20"),
            "overtime": request.POST.get("w_overtime", "0.15"),
            "priority_tardiness": request.POST.get("w_priority", "0.15"),
            "utilization_imbalance": request.POST.get("w_utilization", "0.10"),
            "conflicts": request.POST.get("w_conflicts", "0.10"),
        }
        run = optimize_schedule(base_scenario=scenario, candidate_count=request.POST.get("candidate_count", 8), weights=weights, actor=request.user)
        messages.success(request, f"Otimização concluída com {run.candidates.count()} candidatos.")
        return redirect("integrated-scheduling:optimization-detail", run_pk=run.pk)
    except Exception as exc:
        messages.error(request, str(exc))
        return redirect("integrated-scheduling:detail", pk=pk)


@login_required
def optimization_detail(request, run_pk):
    run = get_object_or_404(ScheduleOptimizationRun.objects.select_related("base_scenario", "best_candidate__scenario"), pk=run_pk)
    candidates = run.candidates.select_related("scenario").order_by("rank", "objective_score")
    return render(request, "integrated_scheduling/optimization_detail.html", {"run": run, "candidates": candidates})


@login_required
@permission_required("integrated_scheduling.add_schedulesolverrun", raise_exception=True)
def solve_cp_sat_view(request, pk):
    scenario = get_object_or_404(IntegratedScheduleScenario, pk=pk)
    if request.method != "POST":
        return redirect("integrated-scheduling:detail", pk=pk)
    try:
        weights = {
            "tardiness": request.POST.get("w_tardiness", 100),
            "priority_tardiness": request.POST.get("w_priority_tardiness", 150),
            "makespan": request.POST.get("w_makespan", 2),
            "setup": request.POST.get("w_setup", 10),
            "alternate_resource": request.POST.get("w_alternate", 5),
            "labor_cost": request.POST.get("w_labor_cost", 1),
        }
        params = dict(
            scenario=scenario, actor=request.user,
            time_limit_seconds=request.POST.get("time_limit", 30), workers=request.POST.get("workers", 8),
            granularity_minutes=request.POST.get("granularity", 5), weights=weights, apply_to_scenario=True,
            relative_gap_limit=request.POST.get("relative_gap_limit", 0),
            warm_start=request.POST.get("warm_start", "1") == "1",
            preemptive_operations=request.POST.get("preemptive_operations", "0") == "1",
            max_consecutive_minutes=request.POST.get("max_consecutive_minutes", 240),
            handoff_penalty=request.POST.get("handoff_penalty", 5),
            use_labor_constraints=request.POST.get("use_labor_constraints", "1") == "1",
        )
        if request.POST.get("async_mode", "0") == "1":
            run = enqueue_cp_sat_solver(**params)
            messages.success(request, f"CP-SAT enfileirado no Celery: execução {run.pk}.")
        else:
            run = solve_cp_sat(**params)
            messages.success(request, f"CP-SAT concluído: {run.status} em {run.wall_time_seconds}s.")
        return redirect("integrated-scheduling:solver-detail", run_pk=run.pk)
    except Exception as exc:
        messages.error(request, str(exc))
        return redirect("integrated-scheduling:detail", pk=pk)


@login_required
def solver_detail(request, run_pk):
    run = get_object_or_404(ScheduleSolverRun.objects.select_related("scenario", "scenario__plant", "warm_start_scenario"), pk=run_pk)
    assignments = run.assignments.select_related("operation__work_order", "work_center", "machine").prefetch_related("segments", "labor_assignments__labor_resource", "labor_assignments__skill").all()
    incumbents = run.incumbents.all()
    return render(request, "integrated_scheduling/solver_detail.html", {"run": run, "assignments": assignments, "incumbents": incumbents})


@login_required
@permission_required("integrated_scheduling.change_schedulesolverrun", raise_exception=True)
def cancel_solver(request, run_pk):
    run = get_object_or_404(ScheduleSolverRun, pk=run_pk)
    if request.method == "POST" and run.status in {ScheduleSolverRun.Status.DRAFT, ScheduleSolverRun.Status.RUNNING}:
        request_solver_cancel(run, reason=request.POST.get("reason") or "Cancelado pela interface")
        messages.warning(request, "Cancelamento solicitado. O worker interromperá no próximo incumbent do solver.")
    return redirect("integrated-scheduling:solver-detail", run_pk=run.pk)


@login_required
def solver_compare(request, pk):
    scenario = get_object_or_404(IntegratedScheduleScenario, pk=pk)
    rows = compare_solver_methods(scenario)
    return render(request, "integrated_scheduling/solver_compare.html", {"scenario": scenario, "rows": rows})


from .models import ProductionSchedulePublication
from .execution import publish_solver_run, sync_execution_actuals, planned_vs_actual, create_rescheduling_trigger, prepare_rescheduling_scenario

@login_required
def publication_dashboard(request):
    plant = _plant(request)
    pubs = ProductionSchedulePublication.objects.filter(plant=plant).select_related("scenario", "solver_run").order_by("-version")[:20] if plant else []
    return render(request, "integrated_scheduling/publications.html", {"plant": plant, "publications": pubs})

@login_required
def publication_detail(request, pk):
    pub = get_object_or_404(ProductionSchedulePublication.objects.select_related("plant", "scenario", "solver_run"), pk=pk)
    if request.GET.get("sync") == "1":
        sync_execution_actuals(publication=pub)
    pav = planned_vs_actual(pub)
    return render(request, "integrated_scheduling/publication_detail.html", {"publication": pub, "pav": pav, "slots": pub.slots.select_related("operation__work_order", "machine", "work_center")})

@login_required
@permission_required("integrated_scheduling.add_productionschedulepublication", raise_exception=True)
def publish_solver_view(request, run_pk):
    run = get_object_or_404(ScheduleSolverRun, pk=run_pk)
    if request.method != "POST":
        return redirect("integrated-scheduling:solver-detail", run_pk=run_pk)
    try:
        pub = publish_solver_run(run=run, actor=request.user, frozen_hours=request.POST.get("frozen_hours", 24), notes=request.POST.get("notes", ""))
        messages.success(request, f"Cronograma oficial v{pub.version} publicado.")
        return redirect("integrated-scheduling:publication-detail", pk=pub.pk)
    except Exception as exc:
        messages.error(request, str(exc))
        return redirect("integrated-scheduling:solver-detail", run_pk=run_pk)

@login_required
@permission_required("integrated_scheduling.add_reschedulingtrigger", raise_exception=True)
def trigger_reschedule_view(request):
    if request.method != "POST":
        return redirect("integrated-scheduling:publications")
    plant = _plant(request)
    try:
        t = create_rescheduling_trigger(plant=plant, trigger_type=request.POST.get("trigger_type", "MANUAL"), source_type=request.POST.get("source_type", ""), source_id=request.POST.get("source_id", ""), payload={"reason": request.POST.get("reason", "")}, actor=request.user)
        s = prepare_rescheduling_scenario(trigger=t, actor=request.user, horizon_days=request.POST.get("days", 14))
        messages.success(request, f"Evento registrado; cenário de replanejamento #{s.pk} preparado.")
        return redirect("integrated-scheduling:detail", pk=s.pk)
    except Exception as exc:
        messages.error(request, str(exc))
        return redirect("integrated-scheduling:publications")

@login_required
def recovery_compare_view(request, pk):
    from .models import ReschedulingTrigger
    from .recovery import build_recovery_comparison
    trigger=get_object_or_404(ReschedulingTrigger.objects.select_related('publication','resulting_solver_run','plant'), pk=pk)
    return render(request, 'integrated_scheduling/recovery_compare.html', {'trigger':trigger,'comparison':build_recovery_comparison(trigger)})

@login_required
@require_POST
def publish_recovery_view(request, pk):
    from .models import ReschedulingTrigger
    from .recovery import publish_recovery
    trigger=get_object_or_404(ReschedulingTrigger, pk=pk)
    pub=publish_recovery(trigger, actor=request.user, notes=request.POST.get('notes',''))
    messages.success(request, f'Plano recuperado publicado como v{pub.version}.')
    return redirect('integrated-scheduling:publication-detail', pk=pub.pk)


@login_required
def recovery_control_center(request):
    from .models import ReschedulingTrigger, RecoveryPolicy
    from .control_center import calculate_trigger_impact
    plant = _plant(request)
    triggers = list(ReschedulingTrigger.objects.filter(plant=plant).select_related("publication", "resulting_solver_run").prefetch_related("recovery_plans")[:100]) if plant else []
    for tr in triggers:
        if not tr.impact_summary:
            try: calculate_trigger_impact(tr)
            except Exception: pass
    policy = RecoveryPolicy.objects.filter(plant=plant).first() if plant else None
    return render(request, "integrated_scheduling/recovery_control_center.html", {"plant": plant, "triggers": triggers, "policy": policy})

@login_required
def recovery_control_detail(request, pk):
    from .models import ReschedulingTrigger
    from .control_center import calculate_trigger_impact, rank_recovery_plans
    trigger = get_object_or_404(ReschedulingTrigger.objects.select_related("plant", "publication", "resulting_solver_run").prefetch_related("recovery_plans__solver_run"), pk=pk)
    impact = calculate_trigger_impact(trigger)
    plans = rank_recovery_plans(trigger) or list(trigger.recovery_plans.all())
    return render(request, "integrated_scheduling/recovery_control_detail.html", {"trigger": trigger, "impact": impact, "plans": plans})

@login_required
@require_POST
def generate_recovery_plans_view(request, pk):
    from .models import ReschedulingTrigger
    from .tasks import build_recovery_control_center_task
    trigger = get_object_or_404(ReschedulingTrigger, pk=pk)
    count = int(request.POST.get("candidate_count") or 3)
    try:
        build_recovery_control_center_task.delay(trigger.pk, candidate_count=count)
        messages.success(request, f"Geração de {count} plano(s) de recuperação enfileirada.")
    except Exception as exc:
        messages.error(request, str(exc))
    return redirect("integrated-scheduling:recovery-control-detail", pk=trigger.pk)

@login_required
@require_POST
def publish_recovery_plan_view(request, pk, plan_pk):
    from .models import ReschedulingTrigger, RecoveryPlan
    from .recovery import publish_recovery
    trigger = get_object_or_404(ReschedulingTrigger, pk=pk)
    plan = get_object_or_404(RecoveryPlan, pk=plan_pk, trigger=trigger, status=RecoveryPlan.Status.READY)
    trigger.resulting_scenario = plan.scenario; trigger.resulting_solver_run = plan.solver_run
    trigger.save(update_fields=["resulting_scenario", "resulting_solver_run", "updated_at"])
    pub = publish_recovery(trigger, actor=request.user, notes=request.POST.get("notes", "") or f"Recovery Control Center · {plan.name}")
    plan.status = RecoveryPlan.Status.PUBLISHED; plan.save(update_fields=["status", "updated_at"])
    messages.success(request, f"{plan.name} publicado como v{pub.version}.")
    return redirect("integrated-scheduling:publication-detail", pk=pub.pk)

@login_required
def commercial_recovery_center(request):
    from .models import RecoveryCommercialImpact, CommercialPromiseAlert
    plant = _plant(request)
    impacts = RecoveryCommercialImpact.objects.filter(trigger__plant=plant).select_related(
        "trigger", "recovery_plan", "sales_order_line__sales_order", "sales_order_line__item"
    ).order_by("sales_order_line__requested_date", "sales_order_line__sales_order__number")[:300] if plant else []
    alerts = CommercialPromiseAlert.objects.filter(trigger__plant=plant, status=CommercialPromiseAlert.Status.OPEN).select_related(
        "trigger", "recovery_plan", "sales_order_line__sales_order", "sales_order_line__item"
    )[:100] if plant else []
    return render(request, "integrated_scheduling/commercial_recovery_center.html", {"plant": plant, "impacts": impacts, "alerts": alerts})

@login_required
@require_POST
def rebuild_commercial_impact_view(request, pk):
    from .models import ReschedulingTrigger
    from .commercial_pegging import rebuild_recovery_commercial_impact
    trigger = get_object_or_404(ReschedulingTrigger, pk=pk)
    result = rebuild_recovery_commercial_impact(trigger)
    if result["exact"]:
        messages.success(request, f"Pegging comercial exato reconstruído: {len(result['rows'])} linha(s).")
    else:
        messages.warning(request, "Este trigger pertence a um MRP legado sem source-aware pegging; o sistema não o apresenta como atribuição comercial exata.")
    return redirect("integrated-scheduling:recovery-control-detail", pk=pk)


@login_required
def commercial_promise_center(request):
    from .models import SalesOrderPromise, CommercialServiceCase
    plant = _plant(request)
    promises = SalesOrderPromise.objects.filter(sales_order_line__sales_order__plant=plant).select_related(
        "sales_order_line__sales_order", "sales_order_line__item", "trigger", "recovery_plan"
    ).prefetch_related("customer_responses", "communications", "sales_order_line__sales_order__commercial_contacts").order_by("-created_at")[:300] if plant else []
    cases = CommercialServiceCase.objects.filter(sales_order_line__sales_order__plant=plant).select_related(
        "sales_order_line__sales_order", "sales_order_line__item", "promise", "owner"
    ).exclude(status=CommercialServiceCase.Status.CLOSED).order_by("priority", "created_at")[:200] if plant else []
    return render(request, "integrated_scheduling/commercial_promise_center.html", {"plant": plant, "promises": promises, "cases": cases})

@login_required
@require_POST
def approve_sales_promise_view(request, pk):
    from .models import SalesOrderPromise
    from .commercial_promising import approve_promise
    promise=get_object_or_404(SalesOrderPromise, pk=pk)
    try:
        approve_promise(promise, actor=request.user)
        messages.success(request, f"Nova promessa {promise.proposed_date} aprovada.")
    except Exception as exc:
        messages.error(request, str(exc))
    return redirect("integrated-scheduling:commercial-promise-center")

@login_required
@require_POST
def reject_sales_promise_view(request, pk):
    from .models import SalesOrderPromise
    from .commercial_promising import reject_promise
    promise=get_object_or_404(SalesOrderPromise, pk=pk)
    try:
        reject_promise(promise, actor=request.user, reason=request.POST.get("reason", ""))
        messages.success(request, "Proposta de promessa rejeitada.")
    except Exception as exc:
        messages.error(request, str(exc))
    return redirect("integrated-scheduling:commercial-promise-center")

@login_required
@require_POST
def send_sales_promise_view(request, pk):
    from .models import SalesOrderPromise, SalesOrderCommercialContact
    from .commercial_confirmation import send_promise_to_customer
    promise = get_object_or_404(SalesOrderPromise, pk=pk)
    contact = SalesOrderCommercialContact.objects.filter(pk=request.POST.get("contact_id")).first() if request.POST.get("contact_id") else None
    try:
        send_promise_to_customer(promise, contact=contact, actor=request.user, channel=request.POST.get("channel") or None)
        messages.success(request, "Nova promessa comunicada ao cliente.")
    except Exception as exc:
        messages.error(request, str(exc))
    return redirect("integrated-scheduling:commercial-promise-center")

@login_required
@require_POST
def customer_promise_response_view(request, pk):
    from .models import SalesOrderPromise
    from .commercial_confirmation import record_customer_response
    from django.utils.dateparse import parse_date
    promise = get_object_or_404(SalesOrderPromise, pk=pk)
    try:
        record_customer_response(
            promise,
            response=request.POST.get("response"), actor=request.user,
            channel=request.POST.get("channel", "MANUAL"),
            confirmed_date=parse_date(request.POST.get("confirmed_date")) if request.POST.get("confirmed_date") else None,
            counterproposed_date=parse_date(request.POST.get("counterproposed_date")) if request.POST.get("counterproposed_date") else None,
            notes=request.POST.get("notes", ""), reevaluate=request.POST.get("reevaluate", "1") != "0",
        )
        messages.success(request, "Resposta do cliente registrada.")
    except Exception as exc:
        messages.error(request, str(exc))
    return redirect("integrated-scheduling:commercial-promise-center")


@login_required
def service_level_dashboard(request):
    from .models import OTIFLineResult
    from .service_level import service_level_summary
    reference=request.GET.get("reference","CUSTOMER_ACCEPTED")
    qs=OTIFLineResult.objects.select_related("sales_order_line__sales_order","sales_order_line__item").filter(reference=reference)
    plant_id=request.GET.get("plant")
    if plant_id: qs=qs.filter(sales_order_line__sales_order__plant_id=plant_id)
    summary=service_level_summary(qs)
    return render(request,"integrated_scheduling/service_level.html",{"rows":qs[:250],"summary":summary,"reference":reference})

@login_required
def service_level_management_dashboard(request):
    from datetime import date
    from .models import ServiceLevelPeriodSnapshot, ServiceLevelTarget
    scope = request.GET.get("scope", "CUSTOMER")
    reference = request.GET.get("reference", "CUSTOMER_ACCEPTED")
    plant = _plant(request)
    qs = ServiceLevelPeriodSnapshot.objects.filter(plant=plant, reference=reference, scope=scope).order_by("-period_start", "scope_label")
    latest_period = qs.values_list("period_start", flat=True).first()
    latest = qs.filter(period_start=latest_period) if latest_period else qs.none()
    trend = ServiceLevelPeriodSnapshot.objects.filter(plant=plant, reference=reference, scope="PLANT").order_by("period_start")[:24]
    targets = ServiceLevelTarget.objects.filter(plant=plant, is_active=True).order_by("scope", "scope_key")
    return render(request, "integrated_scheduling/service_level_management.html", {
        "plant": plant, "scope": scope, "reference": reference, "latest": latest[:250], "trend": trend,
        "targets": targets, "latest_period": latest_period,
    })


# 0.7.8 — Executive S&OP dashboard
@login_required
def executive_sop_dashboard(request):
    from datetime import date
    from .models import ExecutiveSAndOPSnapshot, SAndOPScenario
    from .sop import build_executive_snapshot
    plant=_plant(request)
    today=timezone.localdate(); year=int(request.GET.get('year',today.year)); month=int(request.GET.get('month',today.month))
    from .sop import month_bounds
    start,end=month_bounds(year,month)
    snap=build_executive_snapshot(plant,start,end) if plant else None
    trend=ExecutiveSAndOPSnapshot.objects.filter(plant=plant).order_by('period_start')[:24] if plant else []
    scenarios=SAndOPScenario.objects.filter(plant=plant).order_by('-created_at')[:50] if plant else []
    return render(request,'integrated_scheduling/executive_sop.html',{'plant':plant,'snapshot':snap,'trend':trend,'scenarios':scenarios,'year':year,'month':month})

@login_required
@require_POST
def create_sop_scenario_view(request):
    from django.utils.dateparse import parse_date
    from .models import SAndOPScenario
    from .sop import simulate_sop_scenario
    plant=_plant(request)
    try:
        obj=SAndOPScenario.objects.create(plant=plant,name=request.POST.get('name') or 'S&OP what-if',horizon_start=parse_date(request.POST['horizon_start']),horizon_end=parse_date(request.POST['horizon_end']),
            demand_change_pct=request.POST.get('demand_change_pct') or 0,capacity_change_pct=request.POST.get('capacity_change_pct') or 0,inventory_change_pct=request.POST.get('inventory_change_pct') or 0,created_by=request.user)
        simulate_sop_scenario(obj); messages.success(request,'Cenário S&OP simulado.')
    except Exception as exc: messages.error(request,str(exc))
    return redirect('integrated-scheduling:executive-sop')

# 0.7.9 — ciclo S&OP mensal formal
@login_required
def sop_cycle_dashboard(request):
    from .models import SAndOPCycle
    plant=_plant(request)
    cycles=SAndOPCycle.objects.filter(plant=plant).select_related('plant','approved_by','published_by').order_by('-cycle_month','-version')[:50] if plant else []
    return render(request,'integrated_scheduling/sop_cycle_dashboard.html',{'plant':plant,'cycles':cycles})

@login_required
@require_POST
def sop_cycle_create_view(request):
    from django.utils.dateparse import parse_date
    from .sop_cycle import create_sop_cycle
    plant=_plant(request)
    try:
        obj=create_sop_cycle(plant,parse_date(request.POST['cycle_month']),parse_date(request.POST['horizon_end']),user=request.user,meeting_date=parse_date(request.POST.get('meeting_date','')))
        messages.success(request,f'{obj} criado e baseline de demanda carregado.')
        return redirect('integrated-scheduling:sop-cycle-detail',pk=obj.pk)
    except Exception as exc:
        messages.error(request,str(exc)); return redirect('integrated-scheduling:sop-cycle-dashboard')

@login_required
def sop_cycle_detail(request,pk):
    from .models import SAndOPCycle
    cycle=get_object_or_404(SAndOPCycle.objects.select_related('plant','approved_by','published_by','published_planning_run'),pk=pk)
    return render(request,'integrated_scheduling/sop_cycle_detail.html',{
        'cycle':cycle,
        'demand_lines':cycle.demand_lines.select_related('item').all(),
        'supply_lines':cycle.supply_lines.select_related('item').all(),
        'constraints':cycle.constraints_register.select_related('owner').all(),
        'decisions':cycle.decisions.select_related('owner').all(),
    })

@login_required
@require_POST
def sop_cycle_action_view(request,pk,action):
    from .models import SAndOPCycle
    from .sop_cycle import refresh_demand_baseline,build_supply_review,advance_cycle,approve_cycle,publish_cycle_to_mps
    cycle=get_object_or_404(SAndOPCycle,pk=pk)
    try:
        if action=='refresh-demand': refresh_demand_baseline(cycle)
        elif action=='build-supply': build_supply_review(cycle)
        elif action=='advance': advance_cycle(cycle)
        elif action=='approve': approve_cycle(cycle,request.user)
        elif action=='publish':
            pub=publish_cycle_to_mps(cycle,request.user,True)
            messages.success(request,f'Publicado no MPS: {pub.mps_lines} linha(s); PlanningRun #{pub.planning_run_id} criado.')
            return redirect('integrated-scheduling:sop-cycle-detail',pk=pk)
        else: raise ValueError('Ação S&OP desconhecida.')
        messages.success(request,f'{cycle.code}: ação {action} concluída.')
    except Exception as exc: messages.error(request,str(exc))
    return redirect('integrated-scheduling:sop-cycle-detail',pk=pk)


# 0.8.0 — operational weekly MPS
@login_required
def operational_mps_dashboard(request):
    from .models import SAndOPCycle, OperationalMPSPublication, MPSOperationalPolicy
    plant=_plant(request)
    cycles=SAndOPCycle.objects.filter(plant=plant,status__in=[SAndOPCycle.Status.APPROVED,SAndOPCycle.Status.PUBLISHED]).order_by('-cycle_month','-version')[:20] if plant else []
    publications=OperationalMPSPublication.objects.filter(cycle__plant=plant).select_related('cycle','planning_run').annotate(bucket_count=Count('weekly_buckets')).order_by('-created_at')[:30] if plant else []
    policy=MPSOperationalPolicy.objects.filter(plant=plant).first() if plant else None
    return render(request,'integrated_scheduling/operational_mps_dashboard.html',{'plant':plant,'cycles':cycles,'publications':publications,'policy':policy})

@login_required
@require_POST
def operational_mps_build_view(request):
    from .models import SAndOPCycle
    from .sop_mps import build_operational_mps
    from django.utils.dateparse import parse_date
    try:
        cycle=get_object_or_404(SAndOPCycle,pk=request.POST.get('cycle_id'))
        pub=build_operational_mps(cycle,request.user,parse_date(request.POST.get('as_of_date','')) if request.POST.get('as_of_date') else None)
        messages.success(request,f'MPS operacional {pub.source} construído: {pub.weekly_buckets.count()} buckets.')
        return redirect('integrated-scheduling:operational-mps-detail',pk=pub.pk)
    except Exception as exc:
        messages.error(request,str(exc)); return redirect('integrated-scheduling:operational-mps-dashboard')

@login_required
def operational_mps_detail(request,pk):
    from .models import MPSRevisionSimulation, OperationalMPSPublication

    pub = get_object_or_404(
        OperationalMPSPublication.objects.select_related(
            'cycle',
            'policy',
            'planning_run',
        ),
        pk=pk,
    )

    buckets = list(
        pub.weekly_buckets.select_related('item').all()
    )
    for b in buckets:
        b.delta_quantity = b.quantity - b.baseline_quantity

    bucket_targets = {}
    for bucket in buckets:
        bucket_targets.setdefault(str(bucket.item_id), []).append(
            {
                'id': bucket.pk,
                'bucket_start': bucket.bucket_start.isoformat(),
            }
        )

    exceptions = pub.rccp_exceptions.select_related(
        'work_center',
    ).all()

    changes = pub.bucket_change_requests.select_related(
        'source_bucket__item',
        'target_bucket',
        'decided_by',
    ).all()[:50]

    revisions = (
        pub.revisions
        .select_related(
            'created_by',
            'approved_by',
        )
        .prefetch_related(
            Prefetch(
                'mrp_simulations',
                queryset=MPSRevisionSimulation.objects.order_by('-created_at'),
                to_attr='latest_simulations',
            )
        )
        .order_by('-number')[:30]
    )

    return render(
        request,
        'integrated_scheduling/operational_mps_detail.html',
        {
            'pub': pub,
            'buckets': buckets,
            'bucket_targets': bucket_targets,
            'exceptions': exceptions,
            'changes': changes,
            'revisions': revisions,
        },
    )


@login_required
@require_POST
def operational_mps_bucket_edit(request, pk, bucket_id):
    from decimal import Decimal
    from .models import OperationalMPSPublication, MPSWeeklyBucket
    from .mps_interactive import request_bucket_edit
    pub=get_object_or_404(OperationalMPSPublication,pk=pk); bucket=get_object_or_404(MPSWeeklyBucket,pk=bucket_id,publication=pub)
    try:
        req=request_bucket_edit(bucket, Decimal(request.POST.get('quantity','0')), request.user, request.POST.get('reason',''))
        messages.success(request,'Alteração aplicada.' if req.status=='APPROVED' else 'Alteração em zona congelada enviada para aprovação.')
    except Exception as exc: messages.error(request,str(exc))
    return redirect('integrated-scheduling:operational-mps-detail',pk=pk)

@login_required
@require_POST
def operational_mps_bucket_move(request, pk, bucket_id):
    from decimal import Decimal
    from .models import OperationalMPSPublication, MPSWeeklyBucket
    from .mps_interactive import request_volume_move
    pub=get_object_or_404(OperationalMPSPublication,pk=pk); source=get_object_or_404(MPSWeeklyBucket,pk=bucket_id,publication=pub)
    target=get_object_or_404(MPSWeeklyBucket,pk=request.POST.get('target_bucket_id'),publication=pub,item=source.item)
    try:
        req=request_volume_move(source,target,Decimal(request.POST.get('quantity','0')),request.user,request.POST.get('reason',''))
        messages.success(request,'Volume movido.' if req.status=='APPROVED' else 'Movimentação em zona congelada enviada para aprovação.')
    except Exception as exc: messages.error(request,str(exc))
    return redirect('integrated-scheduling:operational-mps-detail',pk=pk)

@login_required
@require_POST
def operational_mps_change_decide(request, pk, change_id, action):
    from .models import OperationalMPSPublication, MPSBucketChangeRequest
    from .mps_interactive import approve_change,reject_change
    pub=get_object_or_404(OperationalMPSPublication,pk=pk); change=get_object_or_404(MPSBucketChangeRequest,pk=change_id,publication=pub)
    try:
        if action=='approve': approve_change(change,request.user,request.POST.get('notes','')); messages.success(request,'Alteração congelada aprovada e RCCP recalculado.')
        elif action=='reject': reject_change(change,request.user,request.POST.get('notes','')); messages.success(request,'Alteração rejeitada.')
        else: raise ValueError('Decisão desconhecida.')
    except Exception as exc: messages.error(request,str(exc))
    return redirect('integrated-scheduling:operational-mps-detail',pk=pk)

@login_required
@require_POST
def operational_mps_action_view(request,pk,action):
    from .models import OperationalMPSPublication
    from .sop_mps import run_rccp,publish_operational_mps,execute_publication_mrp
    pub=get_object_or_404(OperationalMPSPublication,pk=pk)
    try:
        if action=='validate': run_rccp(pub); messages.success(request,'RCCP recalculado.')
        elif action=='publish': publish_operational_mps(pub,request.user,request.POST.get('force')=='1'); messages.success(request,'MPS semanal publicado e PlanningRun preparado.')
        elif action=='run-mrp':
            run=execute_publication_mrp(pub); messages.success(request,f'MRP #{run.id} finalizado: {run.status}.')
        else: raise ValueError('Ação desconhecida.')
    except Exception as exc: messages.error(request,str(exc))
    return redirect('integrated-scheduling:operational-mps-detail',pk=pk)


# 0.8.2 — revision workflow
@login_required
@require_POST
def operational_mps_revision_capture(request, pk):
    from .models import OperationalMPSPublication
    from .mps_revision import capture_revision
    pub=get_object_or_404(OperationalMPSPublication,pk=pk)
    try:
        rev=capture_revision(pub,request.user,label=request.POST.get('label','Revisão manual'),notes=request.POST.get('notes',''))
        messages.success(request,f'Revisão r{rev.number} capturada.')
    except Exception as exc: messages.error(request,str(exc))
    return redirect('integrated-scheduling:operational-mps-detail',pk=pk)

@login_required
@require_POST
def operational_mps_revision_action(request, pk, revision_id, action):
    from .models import OperationalMPSPublication, MPSRevision
    from .mps_revision import submit_revision, approve_revision, reject_revision, rollback_to_revision
    pub=get_object_or_404(OperationalMPSPublication,pk=pk); rev=get_object_or_404(MPSRevision,pk=revision_id,publication=pub)
    try:
        if action=='submit': submit_revision(rev,request.user); messages.success(request,f'Revisão r{rev.number} enviada para aprovação.')
        elif action=='approve': approve_revision(rev,request.user,request.POST.get('notes','')); messages.success(request,f'Revisão r{rev.number} aprovada.')
        elif action=='reject': reject_revision(rev,request.user,request.POST.get('notes','')); messages.success(request,f'Revisão r{rev.number} rejeitada.')
        elif action=='rollback':
            new=rollback_to_revision(pub,rev,request.user,request.POST.get('reason','')); messages.success(request,f'Rollback aplicado a partir de r{rev.number}; nova revisão r{new.number} criada para aprovação.')
        else: raise ValueError('Ação de revisão desconhecida.')
    except Exception as exc: messages.error(request,str(exc))
    return redirect('integrated-scheduling:operational-mps-detail',pk=pk)

@login_required
def operational_mps_revision_compare(request, pk, revision_id):
    from .models import OperationalMPSPublication, MPSRevision
    from .mps_revision import compare_revisions
    pub=get_object_or_404(OperationalMPSPublication,pk=pk); right=get_object_or_404(MPSRevision,pk=revision_id,publication=pub)
    left_id=request.GET.get('left')
    left=get_object_or_404(MPSRevision,pk=left_id,publication=pub) if left_id else pub.revisions.filter(kind=MPSRevision.Kind.BASELINE).order_by('number').first()
    if not left: left=right.parent or right
    diff=compare_revisions(left,right)
    return render(request,'integrated_scheduling/operational_mps_revision_compare.html',{'pub':pub,'left':left,'right':right,'diff':diff})

# 0.8.3 — MRP what-if before revision approval
@login_required
@require_POST
def operational_mps_revision_whatif(request, pk, revision_id):
    from .models import OperationalMPSPublication, MPSRevision
    from .mps_whatif import create_simulation, run_simulation
    pub=get_object_or_404(OperationalMPSPublication,pk=pk)
    rev=get_object_or_404(MPSRevision,pk=revision_id,publication=pub)
    compare_id=request.POST.get('compare_revision_id')
    compare=get_object_or_404(MPSRevision,pk=compare_id,publication=pub) if compare_id else None
    try:
        sim=create_simulation(rev,compare,request.user)
        if request.POST.get('async')=='1':
            from .tasks import run_mps_revision_whatif_task
            run_mps_revision_whatif_task.delay(sim.id)
            messages.success(request,f'Simulação MRP what-if #{sim.id} enfileirada.')
            return redirect('integrated-scheduling:operational-mps-detail',pk=pk)
        run_simulation(sim)
        messages.success(request,f'Simulação MRP what-if #{sim.id} concluída.')
        return redirect('integrated-scheduling:operational-mps-revision-whatif-report',pk=pk,simulation_id=sim.id)
    except Exception as exc:
        messages.error(request,str(exc)); return redirect('integrated-scheduling:operational-mps-detail',pk=pk)

@login_required
def operational_mps_revision_whatif_report(request, pk, simulation_id):
    from .models import OperationalMPSPublication, MPSRevisionSimulation
    pub=get_object_or_404(OperationalMPSPublication,pk=pk)
    sim=get_object_or_404(MPSRevisionSimulation.objects.select_related('revision','compare_revision','target_planning_run','compare_planning_run'),pk=simulation_id,revision__publication=pub)
    groups={k:list(sim.diff_lines.filter(diff_type=k).select_related('item')) for k in ['MAKE','PURCHASE','SHORTAGE','PEGGING']}
    financial_groups={k:list(sim.financial_lines.filter(category=k).select_related('item')) for k in ['PURCHASE_SPEND','MATERIAL_COST','LABOR_COST','MACHINE_COST','OVERHEAD_COST','INVENTORY_EXPOSURE','WIP_PROXY','CASH_OUTFLOW_PROXY']}
    cashflow=list(sim.cashflow_buckets.select_related('budget').all())
    working_capital=list(sim.working_capital_buckets.all())
    financing=list(sim.financing_buckets.all())
    return render(request,'integrated_scheduling/operational_mps_revision_whatif.html',{'pub':pub,'sim':sim,'groups':groups,'financial_groups':financial_groups,'cashflow':cashflow,'working_capital':working_capital,'financing':financing})

# 0.8.8 — MPS multi-criteria optimizer UI
@login_required
@require_POST
def operational_mps_optimize_088(request, pk, revision_id):
    from .models import OperationalMPSPublication, MPSRevision
    from .mps_optimizer import create_optimization_run, run_optimizer
    pub=get_object_or_404(OperationalMPSPublication,pk=pk)
    rev=get_object_or_404(MPSRevision,pk=revision_id,publication=pub)
    try:
        obj=create_optimization_run(rev,user=request.user)
        if request.POST.get('async')=='1':
            from .tasks import run_mps_optimizer_task
            run_mps_optimizer_task.delay(obj.id); messages.success(request,f'Otimizador 0.8.8 #{obj.id} enfileirado.')
            return redirect('integrated-scheduling:operational-mps-detail',pk=pk)
        run_optimizer(obj); messages.success(request,f'Otimizador 0.8.8 #{obj.id} concluído.')
        return redirect('integrated-scheduling:operational-mps-optimizer-report-088',pk=pk,run_id=obj.id)
    except Exception as exc:
        messages.error(request,str(exc)); return redirect('integrated-scheduling:operational-mps-detail',pk=pk)

@login_required
def operational_mps_optimizer_report_088(request, pk, run_id):
    from .models import OperationalMPSPublication, MPSRevisionOptimizationRun
    pub=get_object_or_404(OperationalMPSPublication,pk=pk)
    obj=get_object_or_404(MPSRevisionOptimizationRun.objects.select_related('revision','compare_revision'),pk=run_id,revision__publication=pub)
    return render(request,'integrated_scheduling/operational_mps_optimizer_088.html',{'pub':pub,'run':obj,'candidates':obj.candidates.select_related('simulation').prefetch_related('actions').order_by('rank','id')})

@login_required
@require_POST
def operational_mps_optimizer_adopt_088(request, pk, candidate_id):
    from .models import OperationalMPSPublication, MPSRevisionOptimizationCandidate
    from .mps_optimizer import adopt_candidate
    pub=get_object_or_404(OperationalMPSPublication,pk=pk)
    candidate=get_object_or_404(MPSRevisionOptimizationCandidate,pk=candidate_id,optimization_run__revision__publication=pub)
    try:
        rev=adopt_candidate(candidate,request.user,request.POST.get('reason',''))
        messages.success(request,f'Candidato #{candidate.id} adotado como revisão r{rev.number}; ainda requer aprovação formal.')
    except Exception as exc: messages.error(request,str(exc))
    return redirect('integrated-scheduling:operational-mps-detail',pk=pk)


# 0.8.9 — CP-SAT Pareto optimizer UI
@login_required
@require_POST
def operational_mps_optimize_089(request, pk, revision_id):
    from .models import OperationalMPSPublication, MPSRevision
    from .mps_optimizer import create_optimization_run
    from .mps_pareto_optimizer import run_pareto_optimizer
    pub=get_object_or_404(OperationalMPSPublication,pk=pk); rev=get_object_or_404(MPSRevision,pk=revision_id,publication=pub)
    try:
        obj=create_optimization_run(rev,user=request.user); obj.optimizer_mode='CP_SAT_PARETO'; obj.save(update_fields=['optimizer_mode','updated_at'])
        if request.POST.get('async')=='1':
            from .tasks import run_mps_pareto_optimizer_task
            run_mps_pareto_optimizer_task.delay(obj.id); messages.success(request,f'Otimizador Pareto 0.8.9 #{obj.id} enfileirado.')
            return redirect('integrated-scheduling:operational-mps-detail',pk=pk)
        run_pareto_optimizer(obj); return redirect('integrated-scheduling:operational-mps-pareto-report-089',pk=pk,run_id=obj.id)
    except Exception as exc: messages.error(request,str(exc)); return redirect('integrated-scheduling:operational-mps-detail',pk=pk)

@login_required
def operational_mps_pareto_report_089(request, pk, run_id):
    from .models import OperationalMPSPublication, MPSRevisionOptimizationRun
    pub=get_object_or_404(OperationalMPSPublication,pk=pk)
    obj=get_object_or_404(MPSRevisionOptimizationRun.objects.select_related('revision','compare_revision'),pk=run_id,revision__publication=pub)
    cands=obj.candidates.select_related('simulation').prefetch_related('actions').order_by('pareto_rank','rank','id')
    return render(request,'integrated_scheduling/operational_mps_pareto_089.html',{'pub':pub,'run':obj,'candidates':cands})

# 0.9.0 — cockpit executivo de decisão MRP/MPS
@login_required
def mps_decision_cockpit_dashboard_090(request):
    from .models import MPSDecisionCockpit, MPSRevisionOptimizationRun
    cockpits = MPSDecisionCockpit.objects.select_related('publication__cycle__plant','optimization_run','selected_candidate','official_revision').all()[:100]
    completed_runs = MPSRevisionOptimizationRun.objects.filter(status='COMPLETED', optimizer_mode='CP_SAT_PARETO', decision_cockpit__isnull=True).select_related('revision__publication__cycle__plant','compare_revision').order_by('-created_at')[:50]
    return render(request,'integrated_scheduling/mps_decision_cockpit_dashboard_090.html',{'cockpits':cockpits,'completed_runs':completed_runs})

@login_required
@require_POST
def mps_decision_cockpit_create_090(request, run_id):
    from .models import MPSRevisionOptimizationRun
    from .mps_decision_cockpit import create_decision_cockpit
    run=get_object_or_404(MPSRevisionOptimizationRun,pk=run_id)
    try:
        cockpit=create_decision_cockpit(run,request.user)
        messages.success(request,f'Cockpit executivo #{cockpit.id} criado.')
        return redirect('integrated-scheduling:mps-decision-cockpit-detail-090',pk=cockpit.id)
    except Exception as exc:
        messages.error(request,str(exc)); return redirect('integrated-scheduling:mps-decision-cockpit-dashboard-090')

@login_required
def mps_decision_cockpit_detail_090(request, pk):
    import json
    from .models import MPSDecisionCockpit
    from .mps_decision_cockpit import candidate_comparison
    cockpit=get_object_or_404(MPSDecisionCockpit.objects.select_related('publication__cycle__plant','optimization_run__revision','baseline_revision','selected_candidate','official_revision','selected_by','approved_by'),pk=pk)
    reviews=list(cockpit.candidate_reviews.select_related('candidate__simulation').prefetch_related('candidate__actions').all())
    chart=[]
    for r in reviews:
        c=r.candidate; ov=c.objective_vector or {}
        chart.append({'id':c.id,'name':c.name,'rank':c.rank,'pareto_rank':c.pareto_rank,'is_pareto':c.is_pareto,'shortlisted':r.shortlisted,
            'service_risk_proxy':str(ov.get('service_risk_proxy',0)),'rccp_overload_hours':str(ov.get('rccp_overload_hours',0)),
            'peak_uncovered_financing':str(ov.get('peak_uncovered_financing',0)),'interest_cost':str(ov.get('interest_cost',0)),
            'inventory_exposure':str(ov.get('inventory_exposure',0)),'purchase_spend':str(ov.get('purchase_spend',0))})
    comparison=candidate_comparison(cockpit,request.GET.get('left'),request.GET.get('right'))
    return render(request,'integrated_scheduling/mps_decision_cockpit_090.html',{
        'cockpit':cockpit,'reviews':reviews,'chart_data':chart,'comparison':comparison,
    })

@login_required
@require_POST
def mps_decision_review_candidate_090(request, pk, candidate_id):
    from .models import MPSDecisionCockpit, MPSRevisionOptimizationCandidate
    from .mps_decision_cockpit import review_candidate
    cockpit=get_object_or_404(MPSDecisionCockpit,pk=pk); candidate=get_object_or_404(MPSRevisionOptimizationCandidate,pk=candidate_id)
    try:
        review_candidate(cockpit,candidate,request.user,shortlisted=request.POST.get('shortlisted')=='1',business_label=request.POST.get('business_label',''),executive_note=request.POST.get('executive_note',''),priority=request.POST.get('priority') or 0)
        messages.success(request,'Avaliação do candidato atualizada.')
    except Exception as exc: messages.error(request,str(exc))
    return redirect('integrated-scheduling:mps-decision-cockpit-detail-090',pk=pk)

@login_required
@require_POST
def mps_decision_select_candidate_090(request, pk, candidate_id):
    from .models import MPSDecisionCockpit, MPSRevisionOptimizationCandidate
    from .mps_decision_cockpit import select_candidate
    cockpit=get_object_or_404(MPSDecisionCockpit,pk=pk); candidate=get_object_or_404(MPSRevisionOptimizationCandidate.objects.select_related('simulation'),pk=candidate_id)
    try:
        select_candidate(cockpit,candidate,request.user,request.POST.get('rationale',''))
        messages.success(request,f'Cenário #{candidate.id} selecionado para decisão executiva.')
    except Exception as exc: messages.error(request,str(exc))
    return redirect('integrated-scheduling:mps-decision-cockpit-detail-090',pk=pk)

@login_required
@require_POST
def mps_decision_action_090(request, pk, action):
    from .models import MPSDecisionCockpit
    from .mps_decision_cockpit import submit_decision, approve_decision, reject_decision, freeze_selected_as_official
    cockpit=get_object_or_404(MPSDecisionCockpit,pk=pk)
    try:
        if action=='submit': submit_decision(cockpit,request.user); messages.success(request,'Decisão enviada para aprovação executiva.')
        elif action=='approve': approve_decision(cockpit,request.user,request.POST.get('notes','')); messages.success(request,'Decisão executiva aprovada.')
        elif action=='reject': reject_decision(cockpit,request.user,request.POST.get('notes','')); messages.success(request,'Decisão executiva rejeitada.')
        elif action=='freeze':
            obj=freeze_selected_as_official(cockpit,request.user); messages.success(request,f'Cenário congelado como revisão oficial r{obj.official_revision.number}. Publicação/MRP continuam ações separadas.')
        else: raise ValueError('Ação inválida.')
    except Exception as exc: messages.error(request,str(exc))
    return redirect('integrated-scheduling:mps-decision-cockpit-detail-090',pk=pk)


@login_required
def mps_decision_minutes_091(request,pk):
    from .models import MPSDecisionCockpit
    from .mps_decision_governance import initialize_governance,governance_check
    c=get_object_or_404(MPSDecisionCockpit.objects.select_related('publication__cycle__plant','selected_candidate','official_revision'),pk=pk)
    meeting=initialize_governance(c,request.user)
    from .mps_decision_authority import authority_check
    authority_req=c.authority_requirements.filter(status__in=['PENDING','SATISFIED']).order_by('-created_at').first()
    return render(request,'integrated_scheduling/mps_decision_minutes_091.html',{'cockpit':c,'meeting':meeting,'check':governance_check(c),'authority_check':authority_check(c),'authority_requirement':authority_req,'participants':meeting.participants.all(),'approvals':c.area_approvals.all(),'risks':c.risk_acceptances.all(),'conditions':c.approval_conditions.all(),'comments':c.formal_comments.all(),'attachments':c.attachments_091.all()})

@login_required
@require_POST
def mps_decision_area_decide_091(request,pk,approval_id):
    from .models import MPSDecisionCockpit,MPSDecisionAreaApproval
    from .mps_decision_governance import record_area_decision
    c=get_object_or_404(MPSDecisionCockpit,pk=pk); a=get_object_or_404(MPSDecisionAreaApproval,pk=approval_id,cockpit=c)
    try: record_area_decision(c,a.area,request.POST.get('decision'),request.user,request.POST.get('comment','')); messages.success(request,f'Decisão da área {a.area} registrada.')
    except Exception as exc: messages.error(request,str(exc))
    return redirect('integrated-scheduling:mps-decision-minutes-091',pk=pk)

@login_required
@require_POST
def mps_decision_authority_sign_092(request,pk,requirement_id):
    from .models import MPSDecisionCockpit,MPSDecisionApprovalRequirement
    from .mps_decision_authority import sign_requirement
    c=get_object_or_404(MPSDecisionCockpit,pk=pk)
    r=get_object_or_404(MPSDecisionApprovalRequirement,pk=requirement_id,cockpit=c)
    try:
        sign_requirement(r,request.user,password=request.POST.get('password'),confirmation=request.POST.get('confirmation',''),client_ip=request.META.get('REMOTE_ADDR'),user_agent=request.META.get('HTTP_USER_AGENT',''))
        messages.success(request,'Assinatura eletrônica 0.9.2 registrada.')
    except Exception as exc: messages.error(request,str(exc))
    return redirect('integrated-scheduling:mps-decision-minutes-091',pk=pk)

# 0.9.3 audit/evidence views
from django.http import HttpResponse
from .mps_decision_audit import verify_audit_chain, build_evidence_zip
@login_required
def mps_decision_audit_093(request,pk):
    from .models import MPSDecisionCockpit
    c=get_object_or_404(MPSDecisionCockpit,pk=pk)
    return render(request,'integrated_scheduling/mps_decision_audit_093.html',{'cockpit':c,'verification':verify_audit_chain(c),'events':c.audit_events.select_related('actor').all(),'exports':c.evidence_exports.select_related('generated_by').all()[:20],'anchors':c.audit_anchors.select_related('created_by').all()[:20],'anchor_verification':verify_cockpit_against_latest_anchor(c)})
@login_required
@require_POST
def mps_decision_evidence_export_093(request,pk):
    from .models import MPSDecisionCockpit
    c=get_object_or_404(MPSDecisionCockpit,pk=pk)
    filename,raw,sha,_=build_evidence_zip(c,request.user)
    resp=HttpResponse(raw,content_type='application/zip'); resp['Content-Disposition']=f'attachment; filename="{filename}"'; resp['X-Package-SHA256']=sha; return resp

# 0.9.4 external audit anchor views
from .mps_decision_anchor import publish_external_anchor, verify_cockpit_against_latest_anchor
@login_required
@require_POST
def mps_decision_anchor_publish_094(request,pk):
    from .models import MPSDecisionCockpit,MPSDecisionAuditAnchor
    c=get_object_or_404(MPSDecisionCockpit,pk=pk)
    try:
        a=publish_external_anchor(c,request.user,provider=request.POST.get('provider') or MPSDecisionAuditAnchor.Provider.FILE_APPEND_ONLY,external_reference=request.POST.get('external_reference',''))
        messages.success(request,f'Âncora externa 0.9.4 publicada no evento {a.anchored_sequence}.')
    except Exception as exc: messages.error(request,str(exc))
    return redirect('integrated-scheduling:mps-decision-audit-093',pk=pk)

@login_required
@require_POST
def mps_decision_anchor_verify_094(request,pk):
    from .models import MPSDecisionCockpit
    c=get_object_or_404(MPSDecisionCockpit,pk=pk)
    r=verify_cockpit_against_latest_anchor(c)
    if r.get('ok'): messages.success(request,'Cadeia do banco e última âncora externa conferem.')
    else: messages.error(request,'Falha na verificação cadeia × âncora externa: '+', '.join(r.get('errors') or ['inconsistência detectada']))
    return redirect('integrated-scheduling:mps-decision-audit-093',pk=pk)


# 0.9.5 automatic anchor policy / integrity dashboard
from .mps_anchor_policy import protection_dashboard, run_anchor_policy
@login_required
def mps_decision_integrity_dashboard_095(request):
    rows=protection_dashboard()
    counts={'PROTECTED':0,'STALE':0,'UNPROTECTED':0,'MISMATCH':0}
    for row in rows: counts[row['protection']['status']]=counts.get(row['protection']['status'],0)+1
    return render(request,'integrated_scheduling/mps_decision_integrity_095.html',{'rows':rows,'counts':counts})
@login_required
@require_POST
def mps_decision_integrity_run_policy_095(request):
    rows=run_anchor_policy(request.user)
    messages.success(request,f'Política 0.9.5 executada para {len(rows)} cockpit(s).')
    return redirect('integrated-scheduling:mps-decision-integrity-dashboard-095')

# 0.9.6 Security & Compliance Center
from .mps_security_compliance import compliance_dashboard, run_security_compliance
@login_required
def mps_security_compliance_center_096(request):
    rows,snapshots=compliance_dashboard()
    counts={'PROTECTED':0,'STALE':0,'UNPROTECTED':0,'MISMATCH':0}
    incident_counts={'OPEN':0,'ACKNOWLEDGED':0,'RESOLVED':0}
    for row in rows:
        counts[row['protection']['status']]=counts.get(row['protection']['status'],0)+1
        for inc in row['open_incidents']:
            incident_counts[inc.status]=incident_counts.get(inc.status,0)+1
    return render(request,'integrated_scheduling/mps_security_compliance_096.html',{
        'rows':rows,'snapshots':snapshots,'counts':counts,'incident_counts':incident_counts,
    })

@login_required
@require_POST
def mps_security_compliance_run_096(request):
    rows=run_security_compliance(request.user,remediate=True)
    cockpit_rows=[r for r in rows if not r.get('summary')]
    messages.success(request,f'Security & Compliance 0.9.6 executado para {len(cockpit_rows)} cockpit(s).')
    return redirect('integrated-scheduling:mps-security-compliance-center-096')

@login_required
@require_POST
def mps_security_compliance_ack_096(request,incident_id):
    from .models import MPSDecisionComplianceIncident
    inc=get_object_or_404(MPSDecisionComplianceIncident,pk=incident_id)
    inc.status=MPSDecisionComplianceIncident.Status.ACKNOWLEDGED
    inc.acknowledged_by=request.user; inc.acknowledged_at=timezone.now()
    inc.save(update_fields=['status','acknowledged_by','acknowledged_at','updated_at'])
    messages.success(request,f'Incidente #{inc.id} reconhecido.')
    return redirect('integrated-scheduling:mps-security-compliance-center-096')

# 0.9.7 — Compliance SLA & Escalation Center
@login_required
def mps_compliance_escalation_center_097(request):
    from .mps_compliance_escalation import escalation_dashboard
    return render(request,'integrated_scheduling/mps_compliance_escalation_097.html',{'rows':escalation_dashboard()})

@login_required
def mps_compliance_escalation_center_098(request):
    from .mps_compliance_escalation import escalation_dashboard
    return render(request,'integrated_scheduling/mps_compliance_escalation_098.html',{'rows':escalation_dashboard()})

@login_required
@require_POST
def mps_compliance_escalation_run_098(request):
    from .mps_compliance_escalation import run_escalation_engine
    rows=run_escalation_engine(send_notifications=True)
    messages.success(request,f'Escalation Engine 0.9.8 executado para {len(rows)} incidente(s).')
    return redirect('integrated-scheduling:mps-compliance-escalation-center-098')

@login_required
@require_POST
def mps_compliance_escalation_run_097(request):
    from .mps_compliance_escalation import run_escalation_engine
    rows=run_escalation_engine(send_notifications=True)
    messages.success(request,f'Escalation Engine 0.9.7 executado para {len(rows)} incidente(s).')
    return redirect('integrated-scheduling:mps-compliance-escalation-center-097')

# 0.9.9 — Incident Command & Postmortem UI
@login_required
def mps_incident_command_center_099(request):
    from .mps_incident_command import incident_command_dashboard
    return render(request,'integrated_scheduling/mps_incident_command_099.html',{'rows':incident_command_dashboard()})

@login_required
def mps_major_incident_detail_099(request, pk):
    from .models import MPSMajorIncident, MPSMajorIncidentPostmortem
    incident=get_object_or_404(MPSMajorIncident.objects.select_related('plant','commander','closed_by').prefetch_related('timeline','actions','compliance_incidents'),pk=pk)
    postmortem=MPSMajorIncidentPostmortem.objects.filter(incident=incident).first()
    return render(request,'integrated_scheduling/mps_major_incident_detail_099.html',{'incident':incident,'postmortem':postmortem})

@login_required
@require_POST
def mps_major_incident_promote_099(request, incident_id):
    from .models import MPSDecisionComplianceIncident
    from .mps_incident_command import promote_compliance_incident
    ci=get_object_or_404(MPSDecisionComplianceIncident,pk=incident_id)
    major,_=promote_compliance_incident(ci,request.user,request.POST.get('title',''))
    return redirect('integrated-scheduling:mps-major-incident-detail-099',pk=major.pk)

@login_required
@require_POST
def mps_major_incident_resolve_099(request, pk):
    from .models import MPSMajorIncident
    from .mps_incident_command import resolve_major_incident
    incident=get_object_or_404(MPSMajorIncident,pk=pk)
    try: resolve_major_incident(incident,request.user,request.POST.get('summary',''))
    except ValueError: pass
    return redirect('integrated-scheduling:mps-major-incident-detail-099',pk=pk)

@login_required
@require_POST
def mps_major_incident_close_099(request, pk):
    from .models import MPSMajorIncident
    from .mps_incident_command import close_major_incident
    incident=get_object_or_404(MPSMajorIncident,pk=pk)
    try: close_major_incident(incident,request.user)
    except ValueError: pass
    return redirect('integrated-scheduling:mps-major-incident-detail-099',pk=pk)
