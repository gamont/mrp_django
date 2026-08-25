from datetime import timedelta
from decimal import Decimal

from django.core.management.base import BaseCommand, CommandError
from django.utils import timezone

from apps.common.models import Plant
from apps.maintenance.models import MaintenanceAsset, MaintenancePlan
from apps.shopfloor.models import Machine


class Command(BaseCommand):
    help = "Cria ativos e planos preventivos demonstrativos a partir das máquinas da planta."

    def add_arguments(self, parser): parser.add_argument("--plant", required=True)

    def handle(self, *args, **options):
        try: plant = Plant.objects.get(code=options["plant"])
        except Plant.DoesNotExist as exc: raise CommandError("Planta não encontrada.") from exc
        count = 0
        for machine in Machine.objects.filter(plant=plant, is_active=True).select_related("work_center"):
            asset, _ = MaintenanceAsset.objects.get_or_create(plant=plant, code=machine.code, defaults={"name": machine.name, "machine": machine, "work_center": machine.work_center, "criticality": MaintenanceAsset.Criticality.HIGH})
            if not asset.machine_id:
                asset.machine = machine; asset.work_center = machine.work_center; asset.save(update_fields=["machine", "work_center", "updated_at"])
            MaintenancePlan.objects.get_or_create(asset=asset, code="PREV-30D", defaults={"title": "Preventiva mensal", "strategy": MaintenancePlan.Strategy.CALENDAR, "interval_days": 30, "planned_duration_hours": Decimal("2.00"), "next_due_date": timezone.localdate() + timedelta(days=30), "instructions": "Inspecionar, limpar, reapertar e lubrificar conforme manual do equipamento."})
            count += 1
        self.stdout.write(self.style.SUCCESS(f"{count} ativo(s) sincronizado(s) com manutenção."))
