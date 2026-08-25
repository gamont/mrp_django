from django.core.management.base import BaseCommand
from apps.common.models import Plant
from apps.integrated_scheduling.service_level_analytics import build_monthly_snapshots
class Command(BaseCommand):
    help='Gera snapshots mensais gerenciais de OTIF/fill rate por planta, cliente, família e item.'
    def add_arguments(self,p):
        p.add_argument('--plant',required=True); p.add_argument('--year',type=int,required=True); p.add_argument('--month',type=int,required=True)
        p.add_argument('--reference',default='CUSTOMER_ACCEPTED',choices=['REQUESTED','APPROVED_PROMISE','CUSTOMER_ACCEPTED'])
    def handle(self,*args,**o):
        plant=Plant.objects.get(code=o['plant']); rows=build_monthly_snapshots(plant,o['year'],o['month'],o['reference'])
        self.stdout.write(self.style.SUCCESS(f'{len(rows)} snapshot(s) gerados para {plant.code} {o["year"]}-{o["month"]:02d}.'))
