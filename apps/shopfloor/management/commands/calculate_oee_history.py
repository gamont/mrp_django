from datetime import date, timedelta

from django.core.management.base import BaseCommand, CommandError

from apps.common.models import Plant
from apps.shopfloor.oee import calculate_plant_oee


class Command(BaseCommand):
    help = "Recalcula snapshots diários e por turno de OEE para um intervalo." 

    def add_arguments(self, parser):
        parser.add_argument("--plant", required=True)
        parser.add_argument("--from", dest="date_from", required=True)
        parser.add_argument("--to", dest="date_to", required=True)
        parser.add_argument("--no-shifts", action="store_true")

    def handle(self, *args, **options):
        try:
            plant = Plant.objects.get(code=options["plant"])
        except Plant.DoesNotExist as exc:
            raise CommandError("Planta não encontrada.") from exc
        try:
            date_from = date.fromisoformat(options["date_from"])
            date_to = date.fromisoformat(options["date_to"])
        except ValueError as exc:
            raise CommandError("Datas inválidas. Use YYYY-MM-DD.") from exc
        if date_from > date_to:
            raise CommandError("A data inicial deve ser menor ou igual à final.")
        if (date_to - date_from).days > 3660:
            raise CommandError("Intervalo máximo: 10 anos por execução.")

        current = date_from
        total_days = 0
        total_machines = 0
        while current <= date_to:
            snapshots = calculate_plant_oee(
                plant=plant,
                metric_date=current,
                include_shifts=not options["no_shifts"],
            )
            total_days += 1
            total_machines += len(snapshots)
            self.stdout.write(f"{current}: {len(snapshots)} máquina(s)")
            current += timedelta(days=1)
        self.stdout.write(self.style.SUCCESS(f"{total_days} dia(s), {total_machines} snapshots diários processados."))
