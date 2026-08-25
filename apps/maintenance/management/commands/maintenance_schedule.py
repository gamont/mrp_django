from django.core.management.base import BaseCommand, CommandError
from apps.common.models import Plant
from apps.maintenance.models import MaintenanceWorkOrder
from apps.maintenance.services import refresh_priority_scores, maintenance_priority_score


class Command(BaseCommand):
    help = "Atualiza score de prioridade e lista backlog de manutenção ordenado para programação."

    def add_arguments(self, parser):
        parser.add_argument("--plant", required=True)
        parser.add_argument("--limit", type=int, default=30)

    def handle(self, *args, **opts):
        try:
            plant = Plant.objects.get(code=opts["plant"])
        except Plant.DoesNotExist as exc:
            raise CommandError("Planta não encontrada.") from exc
        refresh_priority_scores(plant=plant)
        qs = MaintenanceWorkOrder.objects.filter(
            plant=plant,
            status__in=["PLANNED", "WAITING_PARTS", "RELEASED"],
        ).select_related("asset").order_by("-priority_score", "requested_at")[: opts["limit"]]
        for wo in qs:
            self.stdout.write(
                f"{wo.number} | {wo.asset.code} | {wo.get_priority_display():10} | score={wo.priority_score:>6} | {wo.get_status_display()}"
            )
