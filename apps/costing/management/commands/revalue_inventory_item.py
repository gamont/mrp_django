from django.core.management.base import BaseCommand
from apps.common.models import Plant
from apps.masterdata.models import Item
from apps.costing.models import AccountingPeriod
from apps.costing.services.revaluation import revalue_item

class Command(BaseCommand):
    help = "Reavalia o saldo financeiro de um item sem alterar sua quantidade física."
    def add_arguments(self, parser):
        parser.add_argument("--plant", required=True)
        parser.add_argument("--item", required=True)
        parser.add_argument("--unit-cost", required=True)
        parser.add_argument("--reason", required=True)
        parser.add_argument("--period")
        parser.add_argument("--key", required=True)
    def handle(self, *args, **opts):
        plant = Plant.objects.get(code=opts["plant"])
        item = Item.objects.get(code=opts["item"])
        period = AccountingPeriod.objects.filter(plant=plant, code=opts.get("period")).first() if opts.get("period") else None
        obj, created = revalue_item(plant=plant, item=item, new_unit_cost=opts["unit_cost"], reason=opts["reason"], period=period, idempotency_key=opts["key"])
        self.stdout.write(self.style.SUCCESS(f"Reavaliação {obj.pk} ({'nova' if created else 'existente'}): {obj.variance_value}"))
