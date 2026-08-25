from django.core.management.base import BaseCommand, CommandError
from apps.integrated_scheduling.models import ReschedulingTrigger
from apps.integrated_scheduling.commercial_pegging import rebuild_recovery_commercial_impact

class Command(BaseCommand):
    help = "Reconstrói o impacto comercial exato de um trigger usando source-aware MRP pegging."
    def add_arguments(self, parser):
        parser.add_argument("--trigger", type=int, required=True)
    def handle(self, *args, **opts):
        trigger = ReschedulingTrigger.objects.filter(pk=opts["trigger"]).first()
        if not trigger: raise CommandError("Trigger não encontrado")
        result = rebuild_recovery_commercial_impact(trigger)
        if not result["exact"]:
            self.stdout.write(self.style.WARNING("Sem pegging exato: MRP legado ou ordens sem planned_order_id.")); return
        self.stdout.write(self.style.SUCCESS(f"{len(result['rows'])} linha(s) comerciais reconstruídas; pedidos impactados={result['impacted_sales_orders']}."))
