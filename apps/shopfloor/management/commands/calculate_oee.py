from datetime import date

from django.core.management.base import BaseCommand, CommandError
from django.utils import timezone

from apps.common.models import Plant
from apps.shopfloor.oee import calculate_plant_oee


class Command(BaseCommand):
    help = "Calcula e persiste OEE, MTBF e MTTR das máquinas de uma planta."

    def add_arguments(self, parser):
        parser.add_argument("--plant", required=True)
        parser.add_argument("--date", dest="metric_date")
        parser.add_argument("--include-shifts", action="store_true")

    def handle(self, *args, **options):
        try:
            plant = Plant.objects.get(code=options["plant"])
        except Plant.DoesNotExist as exc:
            raise CommandError("Planta não encontrada.") from exc
        metric_date = timezone.localdate()
        if options.get("metric_date"):
            try:
                metric_date = date.fromisoformat(options["metric_date"])
            except ValueError as exc:
                raise CommandError("Data inválida. Use YYYY-MM-DD.") from exc
        snapshots = calculate_plant_oee(plant=plant, metric_date=metric_date, include_shifts=options["include_shifts"])
        for snapshot in snapshots:
            self.stdout.write(
                f"{snapshot.machine.code}: OEE={snapshot.oee_pct:.1f}% "
                f"A={snapshot.availability_pct:.1f}% P={snapshot.performance_pct:.1f}% "
                f"Q={snapshot.quality_pct:.1f}% MTBF={snapshot.mtbf_minutes}m MTTR={snapshot.mttr_minutes}m"
            )
        self.stdout.write(self.style.SUCCESS(f"{len(snapshots)} máquina(s) calculadas para {metric_date}."))
