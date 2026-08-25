from django.core.management.base import BaseCommand
from apps.common.models import Plant
from apps.costing.services.moving_average import rebuild_moving_average

class Command(BaseCommand):
    help = "Reconstrói custo médio móvel a partir das movimentações de estoque."
    def add_arguments(self, parser): parser.add_argument("--plant", required=True)
    def handle(self, *args, **opts):
        plant=Plant.objects.get(code=opts["plant"])
        count=rebuild_moving_average(plant)
        self.stdout.write(self.style.SUCCESS(f"{count} movimentações processadas."))
