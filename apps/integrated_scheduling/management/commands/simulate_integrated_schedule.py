from datetime import timedelta
from django.core.management.base import BaseCommand, CommandError
from django.utils import timezone
from apps.common.models import Plant
from apps.integrated_scheduling.models import IntegratedScheduleScenario
from apps.integrated_scheduling.services import run_integrated_scenario

class Command(BaseCommand):
    help = "Simula capacidade integrada de produção e manutenção."
    def add_arguments(self, parser):
        parser.add_argument("--plant", required=True)
        parser.add_argument("--days", type=int, default=14)
        parser.add_argument("--name", default="CLI integrated what-if")
    def handle(self, *args, **opts):
        plant = Plant.objects.filter(code=opts["plant"]).first()
        if not plant:
            raise CommandError("Planta não encontrada.")
        start = timezone.localdate()
        scenario = IntegratedScheduleScenario.objects.create(name=opts["name"], plant=plant, horizon_start=start, horizon_end=start + timedelta(days=max(1, opts["days"]) - 1))
        run_integrated_scenario(scenario=scenario)
        self.stdout.write(self.style.SUCCESS(f"Scenario {scenario.pk}: {scenario.simulated_summary}"))
