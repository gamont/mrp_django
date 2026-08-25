from django.core.management.base import BaseCommand, CommandError
from apps.demand.models import SalesOrder
from apps.integrated_scheduling.commercial_promising import evaluate_line_atp_ctp

class Command(BaseCommand):
    help = "0.7.4: calcula ATP/CTP e cria propostas de promessa para as linhas abertas de um pedido."
    def add_arguments(self, parser):
        parser.add_argument("--order", required=True)
        parser.add_argument("--no-ctp", action="store_true")
    def handle(self, *args, **opts):
        order = SalesOrder.objects.filter(number=opts["order"]).prefetch_related("lines__item").first()
        if not order: raise CommandError("Pedido não encontrado.")
        count=0
        for line in order.lines.all():
            if line.open_quantity <= 0: continue
            p=evaluate_line_atp_ctp(line, run_ctp=not opts["no_ctp"])
            self.stdout.write(f"{order.number}/{line.line_number} {line.item.code}: {p.proposed_date} [{p.status}]")
            count += 1
        self.stdout.write(self.style.SUCCESS(f"{count} proposta(s) criada(s)."))
