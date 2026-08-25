from django.core.management.base import BaseCommand, CommandError
from apps.costing.models import AccountingPeriod
from apps.costing.services.period_close import final_close_period

class Command(BaseCommand):
    help = "Executa o fechamento industrial definitivo de um período de custos."
    def add_arguments(self, parser):
        parser.add_argument("--plant", required=True)
        parser.add_argument("--period", required=True)
        parser.add_argument("--strict-reconciliation", action="store_true")
    def handle(self, *args, **opts):
        period = AccountingPeriod.objects.filter(plant__code=opts["plant"], code=opts["period"]).first()
        if not period: raise CommandError("Período não encontrado.")
        run = final_close_period(period, strict_reconciliation=opts["strict_reconciliation"])
        self.stdout.write(self.style.SUCCESS(f"Fechamento {run.status}: período={period.code} run={run.pk}"))
