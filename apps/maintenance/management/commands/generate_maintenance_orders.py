from datetime import date

from django.core.management.base import BaseCommand, CommandError

from apps.common.models import Plant
from apps.maintenance.services import generate_preventive_orders


class Command(BaseCommand):
    help = "Gera ordens preventivas vencidas por calendário ou medidor."

    def add_arguments(self, parser):
        parser.add_argument("--plant", required=True)
        parser.add_argument("--through")

    def handle(self, *args, **options):
        try: plant = Plant.objects.get(code=options["plant"])
        except Plant.DoesNotExist as exc: raise CommandError("Planta não encontrada.") from exc
        through = date.fromisoformat(options["through"]) if options.get("through") else None
        created = generate_preventive_orders(plant=plant, through_date=through)
        for wo in created: self.stdout.write(f"{wo.number} · {wo.asset.code} · {wo.title}")
        self.stdout.write(self.style.SUCCESS(f"{len(created)} ordem(ns) gerada(s)."))
