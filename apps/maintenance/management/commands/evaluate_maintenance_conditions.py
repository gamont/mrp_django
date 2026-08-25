from django.core.management.base import BaseCommand
from apps.common.models import Plant
from apps.maintenance.models import ConditionReading
from apps.maintenance.services import evaluate_condition_reading

class Command(BaseCommand):
    help = "Avalia as últimas leituras de condição e gera OMs preditivas quando necessário."
    def add_arguments(self, parser):
        parser.add_argument("--plant", required=True)
    def handle(self, *args, **options):
        plant = Plant.objects.get(code=options["plant"])
        created = set()
        assets = plant.maintenance_assets.filter(is_active=True)
        for asset in assets:
            metrics = asset.condition_readings.values_list("metric", "metric_name").distinct()
            for metric, name in metrics:
                reading = asset.condition_readings.filter(metric=metric, metric_name=name).order_by("-reading_at").first()
                if reading:
                    for wo in evaluate_condition_reading(reading=reading):
                        created.add(wo.pk)
        self.stdout.write(self.style.SUCCESS(f"{len(created)} OM(s) preditiva(s) ativa(s)/gerada(s)."))
