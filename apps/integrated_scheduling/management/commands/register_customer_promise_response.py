from django.core.management.base import BaseCommand, CommandError
from django.utils.dateparse import parse_date
from apps.integrated_scheduling.models import SalesOrderPromise
from apps.integrated_scheduling.commercial_confirmation import record_customer_response

class Command(BaseCommand):
    help = "Registra aceite, rejeição ou contraproposta do cliente."
    def add_arguments(self, parser):
        parser.add_argument("--promise", type=int, required=True)
        parser.add_argument("--response", choices=["ACCEPTED","REJECTED","COUNTERPROPOSED"], required=True)
        parser.add_argument("--date")
        parser.add_argument("--notes", default="")
        parser.add_argument("--no-reevaluate", action="store_true")
    def handle(self, *args, **opts):
        promise=SalesOrderPromise.objects.filter(pk=opts["promise"]).first()
        if not promise: raise CommandError("Promise não encontrada.")
        d=parse_date(opts["date"]) if opts.get("date") else None
        obj=record_customer_response(promise, response=opts["response"], confirmed_date=d if opts["response"]=="ACCEPTED" else None, counterproposed_date=d if opts["response"]=="COUNTERPROPOSED" else None, notes=opts["notes"], reevaluate=not opts["no_reevaluate"])
        self.stdout.write(self.style.SUCCESS(f"Resposta #{obj.pk}: {obj.response}"))
