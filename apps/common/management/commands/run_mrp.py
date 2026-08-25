from datetime import timedelta
from django.core.management.base import BaseCommand, CommandError
from django.utils import timezone

from apps.common.models import Plant
from apps.planning.models import PlanningRun
from apps.planning.services import execute_planning_run


class Command(BaseCommand):
    help = "Executa o MRP para uma planta."

    def add_arguments(self, parser):
        parser.add_argument("--plant", default="SP01")
        parser.add_argument("--days", type=int, default=90)

    def handle(self, *args, **options):
        try:
            plant = Plant.objects.get(code=options["plant"])
        except Plant.DoesNotExist as exc:
            raise CommandError("Planta não encontrada. Execute seed_demo ou informe --plant.") from exc

        today = timezone.localdate()
        run = PlanningRun.objects.create(
            name=f"MRP {plant.code} {today}",
            plant=plant,
            horizon_start=today,
            horizon_end=today + timedelta(days=options["days"]),
        )
        execute_planning_run(run)
        self.stdout.write(
            self.style.SUCCESS(
                f"MRP concluído: {run.planned_orders.count()} ordens, "
                f"{run.messages.count()} mensagens, run_id={run.id}."
            )
        )
