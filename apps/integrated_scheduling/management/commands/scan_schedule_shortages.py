from django.core.management.base import BaseCommand
from apps.integrated_scheduling.tasks import scan_material_shortages_task
class Command(BaseCommand):
    help='Detecta faltas reais de material no cronograma oficial e cria triggers de recovery.'
    def add_arguments(self,p): p.add_argument('--hours',type=int,default=24)
    def handle(self,*a,**o): self.stdout.write(str(scan_material_shortages_task(lookahead_hours=o['hours'])))
