from django.core.management.base import BaseCommand, CommandError
from apps.integrated_scheduling.models import SalesOrderPromise, SalesOrderCommercialContact
from apps.integrated_scheduling.commercial_confirmation import send_promise_to_customer

class Command(BaseCommand):
    help = "Envia uma promessa comercial aprovada ao contato do cliente."
    def add_arguments(self, parser):
        parser.add_argument("--promise", type=int, required=True)
        parser.add_argument("--contact", type=int)
        parser.add_argument("--channel", choices=["EMAIL","API","MANUAL"])
    def handle(self, *args, **opts):
        promise = SalesOrderPromise.objects.filter(pk=opts["promise"]).first()
        if not promise: raise CommandError("Promise não encontrada.")
        contact = SalesOrderCommercialContact.objects.filter(pk=opts.get("contact")).first() if opts.get("contact") else None
        obj = send_promise_to_customer(promise, contact=contact, channel=opts.get("channel"))
        self.stdout.write(self.style.SUCCESS(f"Comunicação #{obj.pk}: {obj.status}"))
