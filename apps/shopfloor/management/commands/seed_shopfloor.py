from django.core.management.base import BaseCommand, CommandError
from django.utils import timezone

from apps.common.models import Plant
from apps.masterdata.models import WorkCenter
from apps.shopfloor.models import DowntimeReason, Machine, OEETarget, TerminalStation


class Command(BaseCommand):
    help = "Cria máquinas, estação e motivos de parada demonstrativos para uma planta."

    def add_arguments(self, parser):
        parser.add_argument("--plant", default="SP01")

    def handle(self, *args, **options):
        try:
            plant = Plant.objects.get(code=options["plant"])
        except Plant.DoesNotExist as exc:
            raise CommandError("Planta não encontrada. Execute seed_demo primeiro.") from exc
        work_centers = list(WorkCenter.objects.filter(plant=plant, is_active=True).order_by("code"))
        if not work_centers:
            raise CommandError("A planta não possui centros de trabalho ativos.")
        for index, wc in enumerate(work_centers[:4], start=1):
            machine, _ = Machine.objects.get_or_create(plant=plant, code=f"M-{wc.code}-01", defaults={"name": f"Máquina {wc.name}", "work_center": wc, "planned_minutes_per_day": 480, "ideal_cycle_seconds": 60})
            if machine.work_center_id != wc.pk:
                machine.work_center = wc
                machine.save(update_fields=["work_center", "updated_at"])
            TerminalStation.objects.get_or_create(plant=plant, code=f"T-{wc.code}-01", defaults={"name": f"Terminal {wc.name}", "work_center": wc, "machine": machine})
        reasons = [
            ("FALHA", "Falha de equipamento", "UNPLANNED"),
            ("MATERIAL", "Falta de material", "MATERIAL"),
            ("QUAL", "Problema de qualidade", "QUALITY"),
            ("FERR", "Ajuste ou falta de ferramental", "TOOLING"),
            ("PREV", "Manutenção preventiva", "PLANNED"),
        ]
        for code, description, category in reasons:
            DowntimeReason.objects.get_or_create(plant=plant, code=code, defaults={"description": description, "category": category})
        OEETarget.objects.get_or_create(plant=plant, work_center=None, machine=None, effective_from=timezone.localdate(), defaults={"oee_target": "0.8500", "availability_target": "0.9000", "performance_target": "0.9500", "quality_target": "0.9900"})
        self.stdout.write(self.style.SUCCESS(f"Chão de fábrica demonstrativo criado para {plant.code}."))
