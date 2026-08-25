from django.core.management.base import BaseCommand, CommandError
from apps.common.models import Plant
from apps.integrated_scheduling.sop import month_bounds, build_executive_snapshot
class Command(BaseCommand):
    help='Calcula snapshot executivo S&OP 0.7.8.'
    def add_arguments(self,p): p.add_argument('--plant',required=True); p.add_argument('--year',type=int,required=True); p.add_argument('--month',type=int,required=True)
    def handle(self,*a,**o):
        plant=Plant.objects.filter(code=o['plant']).first()
        if not plant: raise CommandError('Planta não encontrada.')
        start,end=month_bounds(o['year'],o['month']); x=build_executive_snapshot(plant,start,end)
        self.stdout.write(self.style.SUCCESS(f'{plant.code} {start:%Y-%m}: OTIF={x.otif_pct}% ForecastAcc={x.forecast_accuracy_pct}% OEE={x.oee_pct}% Capacity={x.capacity_utilization_pct}%'))
