from django.core.management.base import BaseCommand, CommandError
from apps.costing.models import AccountingPeriod
from apps.costing.services.valuation import create_wip_snapshot

class Command(BaseCommand):
    help = "Gera o snapshot de WIP de um período."
    def add_arguments(self, parser):
        parser.add_argument("--plant", required=True)
        parser.add_argument("--period", required=True)
    def handle(self, *args, **opts):
        try:
            period = AccountingPeriod.objects.get(plant__code=opts["plant"], code=opts["period"])
            snapshot = create_wip_snapshot(period)
        except AccountingPeriod.DoesNotExist as exc:
            raise CommandError("Período não encontrado.") from exc
        except ValueError as exc:
            raise CommandError(str(exc)) from exc
        self.stdout.write(self.style.SUCCESS(f"WIP valorizado: {snapshot.total_value}"))
