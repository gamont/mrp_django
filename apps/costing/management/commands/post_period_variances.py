from django.core.management.base import BaseCommand
from apps.costing.models import AccountingPeriod
from apps.costing.services.accounting import post_period_variances

class Command(BaseCommand):
    help = "Consolida e contabiliza variações do período no subledger de custos."
    def add_arguments(self, parser):
        parser.add_argument("--plant", required=True); parser.add_argument("--period", required=True)
    def handle(self, *args, **opts):
        period=AccountingPeriod.objects.select_related("plant").get(plant__code=opts["plant"], code=opts["period"])
        rows=post_period_variances(period)
        self.stdout.write(self.style.SUCCESS(f"{len(rows)} tipos de variação contabilizados."))
