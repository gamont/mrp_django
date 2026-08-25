from datetime import timedelta
from django.core.management.base import BaseCommand
from django.utils import timezone
from apps.common.models import Plant
from apps.integrated_scheduling.models import IntegratedScheduleScenario
from apps.integrated_scheduling.advanced import run_finite_scenario


class Command(BaseCommand):
    help = "Cria e executa um cenário de programação finita por máquina (forward/backward)."

    def add_arguments(self, parser):
        parser.add_argument("--plant", required=True)
        parser.add_argument("--days", type=int, default=14)
        parser.add_argument("--name", default="Finite schedule")
        parser.add_argument("--direction", choices=["FORWARD", "BACKWARD"], default="FORWARD")
        parser.add_argument("--no-alternates", action="store_true")
        parser.add_argument("--ignore-calendar", action="store_true", help="Usa o scheduler contínuo legado 0.6.1.")

    def handle(self, *args, **opts):
        plant = Plant.objects.get(code=opts["plant"])
        start = timezone.localdate()
        days = max(1, min(opts["days"], 90))
        scenario = IntegratedScheduleScenario.objects.create(
            name=opts["name"], plant=plant, horizon_start=start,
            horizon_end=start + timedelta(days=days - 1),
            scheduling_direction=opts["direction"], finite_by_machine=True,
            allow_alternate_resources=not opts["no_alternates"],
            respect_industrial_calendar=not opts["ignore_calendar"],
        )
        run_finite_scenario(scenario=scenario)
        s = scenario.simulated_summary
        self.stdout.write(self.style.SUCCESS(
            f"Scenario {scenario.pk}: direction={scenario.scheduling_direction} "
            f"critical={s.get('critical_conflicts', 0)} conflicts={s.get('conflicts', 0)} "
            f"late_hours={s.get('late_hours', 0)} shifted={s.get('shifted_operations', 0)} "
            f"alternates={s.get('alternate_resource_operations', 0)} "
            f"segments={s.get('segments', 0)} overtime={s.get('overtime_effective_hours', 0)} "
            f"unscheduled={s.get('unscheduled_operations', 0)}"
        ))
