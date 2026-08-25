from datetime import datetime, timedelta
from django.core.management.base import BaseCommand
from django.utils import timezone
from apps.common.models import Plant
from apps.maintenance.models import MaintenanceWorkOrder
from apps.maintenance.services import maintenance_part_availability, sla_status

class Command(BaseCommand):
    help = "Exibe backlog de manutenção com disponibilidade de peças e SLA."
    def add_arguments(self, parser):
        parser.add_argument("--plant", required=True)
    def handle(self, *args, **options):
        plant = Plant.objects.get(code=options["plant"])
        qs = MaintenanceWorkOrder.objects.filter(plant=plant).exclude(status__in=[MaintenanceWorkOrder.Status.COMPLETED, MaintenanceWorkOrder.Status.CANCELLED]).select_related("asset").order_by("priority", "requested_at")
        for wo in qs:
            parts_ok, _ = maintenance_part_availability(wo)
            sla = sla_status(wo)
            flags = []
            if not parts_ok: flags.append("PEÇAS")
            if sla["response_breached"]: flags.append("SLA-RESPOSTA")
            if sla["resolution_breached"]: flags.append("SLA-RESOLUÇÃO")
            self.stdout.write(f"{wo.number} | {wo.asset.code} | {wo.get_priority_display()} | {wo.get_status_display()} | {'/'.join(flags) or 'OK'}")
