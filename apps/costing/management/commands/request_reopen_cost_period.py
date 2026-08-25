from django.core.management.base import BaseCommand, CommandError
from apps.costing.models import AccountingPeriod
from apps.costing.services.period_close import request_reopen

class Command(BaseCommand):
    help = "Solicita reabertura controlada de período de custos."
    def add_arguments(self, parser):
        parser.add_argument("--plant", required=True); parser.add_argument("--period", required=True); parser.add_argument("--reason", required=True)
    def handle(self, *args, **opts):
        period=AccountingPeriod.objects.filter(plant__code=opts["plant"], code=opts["period"]).first()
        if not period: raise CommandError("Período não encontrado.")
        req=request_reopen(period, opts["reason"])
        self.stdout.write(self.style.SUCCESS(f"Solicitação criada: {req.pk}"))
