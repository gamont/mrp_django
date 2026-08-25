from django.core.management.base import BaseCommand, CommandError
from apps.common.models import Plant
from apps.integrated_scheduling.models import IntegratedScheduleScenario
from apps.integrated_scheduling.optimizer import optimize_schedule

class Command(BaseCommand):
    help = "Gera e ranqueia cenários multicritério 0.6.4."

    def add_arguments(self, parser):
        parser.add_argument("--scenario", type=int, required=True)
        parser.add_argument("--candidates", type=int, default=8)
        parser.add_argument("--w-lateness", default="0.30")
        parser.add_argument("--w-setup", default="0.20")
        parser.add_argument("--w-overtime", default="0.15")
        parser.add_argument("--w-priority", default="0.15")
        parser.add_argument("--w-utilization", default="0.10")
        parser.add_argument("--w-conflicts", default="0.10")

    def handle(self, *args, **opts):
        scenario = IntegratedScheduleScenario.objects.filter(pk=opts["scenario"]).first()
        if not scenario:
            raise CommandError("Cenário não encontrado.")
        weights = {
            "lateness": opts["w_lateness"], "setup": opts["w_setup"], "overtime": opts["w_overtime"],
            "priority_tardiness": opts["w_priority"], "utilization_imbalance": opts["w_utilization"],
            "conflicts": opts["w_conflicts"],
        }
        run = optimize_schedule(base_scenario=scenario, candidate_count=opts["candidates"], weights=weights)
        self.stdout.write(self.style.SUCCESS(f"Otimização {run.pk}: {run.summary}"))
