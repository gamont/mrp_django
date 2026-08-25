from datetime import timedelta

from django.core.management.base import BaseCommand, CommandError
from django.utils import timezone

from apps.common.models import Plant
from apps.masterdata.models import WorkCenter
from apps.shopfloor.models import Machine
from apps.integrated_scheduling.calendar_engine import resource_windows
from apps.integrated_scheduling.models import IntegratedScheduleScenario


class Command(BaseCommand):
    help = "Exibe as janelas efetivas do calendário industrial usadas pelo scheduler 0.6.2."

    def add_arguments(self, parser):
        parser.add_argument("--plant", required=True)
        parser.add_argument("--center", required=True)
        parser.add_argument("--machine")
        parser.add_argument("--days", type=int, default=7)

    def handle(self, *args, **opts):
        plant = Plant.objects.filter(code=opts["plant"]).first()
        if not plant:
            raise CommandError("Planta não encontrada.")
        center = WorkCenter.objects.filter(plant=plant, code=opts["center"]).first()
        if not center:
            raise CommandError("Centro de trabalho não encontrado.")
        machine = None
        if opts.get("machine"):
            machine = Machine.objects.filter(plant=plant, work_center=center, code=opts["machine"]).first()
            if not machine:
                raise CommandError("Máquina não encontrada no centro informado.")
        start = timezone.localdate()
        days = max(1, min(opts["days"], 90))
        scenario = IntegratedScheduleScenario(
            name="calendar-preview", plant=plant, horizon_start=start,
            horizon_end=start + timedelta(days=days - 1), respect_industrial_calendar=True,
        )
        rows = resource_windows(scenario=scenario, work_center=center, machine=machine)
        if not rows:
            self.stdout.write(self.style.WARNING("Nenhuma janela útil no período."))
            return
        total = 0.0
        for begin, end, factor, kind in rows:
            elapsed = (end - begin).total_seconds() / 3600
            effective = elapsed * float(factor)
            total += effective
            self.stdout.write(f"{begin:%Y-%m-%d %H:%M} -> {end:%Y-%m-%d %H:%M} | {kind:8} | fator={factor} | capacidade efetiva={effective:.2f}h")
        self.stdout.write(self.style.SUCCESS(f"Capacidade efetiva total: {total:.2f} h"))
