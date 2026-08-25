from django.core.management.base import BaseCommand, CommandError
from apps.costing.models import AccountingPeriod
from apps.costing.services.valuation import close_accounting_period

class Command(BaseCommand):
    help = "Fecha um período de custos, gerando valorização de estoque e WIP."
    def add_arguments(self, parser):
        parser.add_argument("--plant", required=True)
        parser.add_argument("--period", required=True)
    def handle(self, *args, **opts):
        try:
            period = AccountingPeriod.objects.select_related("plant").get(plant__code=opts["plant"], code=opts["period"])
            close_accounting_period(period)
        except AccountingPeriod.DoesNotExist as exc:
            raise CommandError("Período não encontrado.") from exc
        except ValueError as exc:
            raise CommandError(str(exc)) from exc
        self.stdout.write(self.style.SUCCESS(f"Período {period.plant.code}/{period.code} fechado."))
