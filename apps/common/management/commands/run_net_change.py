from datetime import timedelta

from django.core.management.base import BaseCommand, CommandError
from django.utils import timezone

from apps.common.models import Plant
from apps.planning.net_change import execute_net_change_run


class Command(BaseCommand):
    help = "Executa MRP net-change usando os eventos pendentes de uma planta."

    def add_arguments(self, parser):
        parser.add_argument("--plant", required=True)
        parser.add_argument("--days", type=int, default=90)
        parser.add_argument("--include-sales-orders", action="store_true")
        parser.add_argument("--include-forecasts", action="store_true")

    def handle(self, *args, **options):
        try:
            plant = Plant.objects.get(code=options["plant"])
        except Plant.DoesNotExist as exc:
            raise CommandError("Planta não encontrada.") from exc

        today = timezone.localdate()
        run = execute_net_change_run(
            plant=plant,
            horizon_start=today,
            horizon_end=today + timedelta(days=options["days"]),
            name=f"Net-change {plant.code} {today}",
            parameters={
                "include_sales_orders": options["include_sales_orders"],
                "include_forecasts": options["include_forecasts"],
            },
        )
        self.stdout.write(
            self.style.SUCCESS(
                f"Execução {run.pk} concluída: {run.planned_orders.count()} ordens planejadas."
            )
        )
