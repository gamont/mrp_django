from django.core.management.base import BaseCommand, CommandError
from apps.integrated_scheduling.models import ProductionSchedulePublication
from apps.integrated_scheduling.execution import sync_execution_actuals
class Command(BaseCommand):
    help = "Sincroniza planned × actual do cronograma oficial."
    def add_arguments(self,p): p.add_argument("--publication", type=int, required=True); p.add_argument("--threshold", type=int, default=15)
    def handle(self,*a,**o):
        pub=ProductionSchedulePublication.objects.filter(pk=o["publication"]).first()
        if not pub: raise CommandError("Publicação não encontrada.")
        self.stdout.write(str(sync_execution_actuals(publication=pub, threshold_minutes=o["threshold"])))
