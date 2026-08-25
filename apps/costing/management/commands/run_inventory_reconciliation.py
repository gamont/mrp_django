from django.core.management.base import BaseCommand
from apps.common.models import Plant
from apps.costing.models import AccountingPeriod
from apps.costing.services.reconciliation import reconcile_inventory

class Command(BaseCommand):
    help = "Concilia quantidades e valores físico x financeiro do estoque."
    def add_arguments(self, parser):
        parser.add_argument("--plant", required=True)
        parser.add_argument("--period")
    def handle(self, *args, **opts):
        plant = Plant.objects.get(code=opts["plant"])
        period = AccountingPeriod.objects.filter(plant=plant, code=opts.get("period")).first() if opts.get("period") else None
        run = reconcile_inventory(plant=plant, period=period)
        self.stdout.write(self.style.SUCCESS(f"Reconciliação {run.pk}: qtd={run.quantity_variance} valor={run.value_variance}"))
