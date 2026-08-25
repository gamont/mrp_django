from django.core.management.base import BaseCommand
from apps.common.models import Plant
from apps.integrated_scheduling.models import ReschedulingTrigger
from apps.integrated_scheduling.control_center import calculate_trigger_impact, get_policy

class Command(BaseCommand):
    help = "Resumo do Recovery Control Center 0.7.2"
    def add_arguments(self, parser):
        parser.add_argument("--plant", required=True)
        parser.add_argument("--limit", type=int, default=20)
    def handle(self, *args, **o):
        plant = Plant.objects.get(code=o["plant"])
        policy = get_policy(plant)
        self.stdout.write(f"{plant.code} | auto_publish={policy.auto_publish_enabled} | candidates={policy.candidate_count}")
        for tr in ReschedulingTrigger.objects.filter(plant=plant)[:o["limit"]]:
            impact = calculate_trigger_impact(tr)
            self.stdout.write(f"#{tr.pk} {tr.trigger_type:18} {tr.severity:8} {tr.status:10} OPs={impact['affected_work_orders']} Pedidos={impact['impacted_sales_orders']} ETA={tr.recovery_eta_seconds}s")
