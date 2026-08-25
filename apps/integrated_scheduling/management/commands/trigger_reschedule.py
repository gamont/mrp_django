from django.core.management.base import BaseCommand, CommandError
from django.utils import timezone
from apps.common.models import Plant
from apps.integrated_scheduling.execution import create_rescheduling_trigger, prepare_rescheduling_scenario
class Command(BaseCommand):
    help = "Registra uma ruptura operacional e prepara cenário de reprogramação."
    def add_arguments(self,p):
        p.add_argument("--plant", required=True); p.add_argument("--type", default="MANUAL"); p.add_argument("--source-type", default=""); p.add_argument("--source-id", default=""); p.add_argument("--days", type=int, default=14)
    def handle(self,*a,**o):
        plant=Plant.objects.filter(code=o["plant"]).first()
        if not plant: raise CommandError("Planta não encontrada.")
        t=create_rescheduling_trigger(plant=plant, trigger_type=o["type"], source_type=o["source_type"], source_id=o["source_id"], affected_from=timezone.now())
        s=prepare_rescheduling_scenario(trigger=t, horizon_days=o["days"])
        self.stdout.write(self.style.SUCCESS(f"Trigger {t.pk}; cenário {s.pk} preparado."))
