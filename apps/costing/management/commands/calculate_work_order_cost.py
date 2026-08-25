from django.core.management.base import BaseCommand
from apps.production.models import WorkOrder
from apps.costing.services.work_order_cost import calculate_planned_cost, calculate_actual_cost
from apps.costing.services.variances import calculate_variances
class Command(BaseCommand):
    help = "Calcula custo planejado, real e variações de uma ordem de produção."
    def add_arguments(self, parser): parser.add_argument("--work-order", required=True); parser.add_argument("--mode", choices=["planned","actual","all"], default="all")
    def handle(self, *args, **opts):
        wo=WorkOrder.objects.get(number=opts["work_order"])
        if opts["mode"] in {"planned","all"}: calculate_planned_cost(wo)
        if opts["mode"] in {"actual","all"}: calculate_actual_cost(wo)
        if opts["mode"]=="all": calculate_variances(wo)
        self.stdout.write(self.style.SUCCESS(f"Custos calculados para {wo.number}"))
