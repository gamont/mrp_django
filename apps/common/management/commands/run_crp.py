import json

from django.core.management.base import BaseCommand, CommandError

from apps.planning.capacity import capacity_bottleneck_summary, execute_capacity_scenario
from apps.planning.models import CapacityScenario, PlanningRun


class Command(BaseCommand):
    help = "Executa CRP finito para uma execução MRP existente."

    def add_arguments(self, parser):
        parser.add_argument("--planning-run", type=int, required=True)
        parser.add_argument("--without-open-orders", action="store_true")

    def handle(self, *args, **options):
        try:
            run = PlanningRun.objects.select_related("plant").get(pk=options["planning_run"])
        except PlanningRun.DoesNotExist as exc:
            raise CommandError("Execução MRP não encontrada.") from exc

        scenario = CapacityScenario.objects.create(
            name=f"CRP {run.name}",
            scenario_type=CapacityScenario.ScenarioType.CRP,
            plant=run.plant,
            planning_run=run,
            parameters={"include_open_orders": not options["without_open_orders"]},
        )
        execute_capacity_scenario(scenario)
        scenario.refresh_from_db()
        self.stdout.write(
            self.style.SUCCESS(
                f"Cenário {scenario.pk}: feasible={scenario.feasible}, promised={scenario.promised_date}"
            )
        )
        self.stdout.write(json.dumps(capacity_bottleneck_summary(scenario), indent=2, ensure_ascii=False))
