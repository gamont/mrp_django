from django.core.management.base import BaseCommand, CommandError
from apps.common.models import Plant
from apps.integrated_scheduling.models import IntegratedScheduleScenario
from apps.integrated_scheduling.cp_sat_solver import solve_cp_sat
from apps.integrated_scheduling.tasks import enqueue_cp_sat_solver


class Command(BaseCommand):
    help = "Resolve um cenário de programação integrada com Google OR-Tools CP-SAT."

    def add_arguments(self, parser):
        parser.add_argument("--scenario", type=int, required=True)
        parser.add_argument("--time-limit", type=int, default=30)
        parser.add_argument("--workers", type=int, default=8)
        parser.add_argument("--granularity", type=int, default=5)
        parser.add_argument("--no-apply-to-scenario", action="store_true")
        parser.add_argument("--relative-gap", type=float, default=0.02)
        parser.add_argument("--no-warm-start", action="store_true")
        parser.add_argument("--async", dest="async_mode", action="store_true")
        parser.add_argument("--preemptive", action="store_true", help="Permite segmentar operações entre janelas/turnos.")
        parser.add_argument("--max-consecutive-minutes", type=int, default=240)
        parser.add_argument("--handoff-penalty", type=int, default=5)
        parser.add_argument("--no-labor", action="store_true", help="Ignora restrições de mão de obra finita.")
        parser.add_argument("--w-labor-cost", type=int, default=1, help="Peso do custo/preferência de mão de obra no objetivo.")

    def handle(self, *args, **opts):
        scenario = IntegratedScheduleScenario.objects.filter(pk=opts["scenario"]).first()
        if not scenario:
            raise CommandError("Cenário não encontrado.")
        kwargs = dict(
            scenario=scenario,
            time_limit_seconds=opts["time_limit"],
            workers=opts["workers"],
            granularity_minutes=opts["granularity"],
            apply_to_scenario=not opts["no_apply_to_scenario"],
            relative_gap_limit=opts["relative_gap"],
            warm_start=not opts["no_warm_start"],
            preemptive_operations=opts["preemptive"],
            max_consecutive_minutes=opts["max_consecutive_minutes"],
            handoff_penalty=opts["handoff_penalty"],
            use_labor_constraints=not opts["no_labor"],
            weights={"labor_cost": opts["w_labor_cost"]},
        )
        run = enqueue_cp_sat_solver(**kwargs) if opts["async_mode"] else solve_cp_sat(**kwargs)
        self.stdout.write(self.style.SUCCESS(
            f"Run {run.pk}: {run.status} | objetivo={run.objective_value} | bound={run.best_bound} | "
            f"tempo={run.wall_time_seconds}s | assignments={run.assignments.count()}"
        ))
