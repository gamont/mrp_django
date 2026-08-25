from django.core.management.base import BaseCommand, CommandError
from apps.common.models import Plant
from apps.integrated_scheduling.models import MPSOperationalPolicy
class Command(BaseCommand):
    help='Cria/atualiza política padrão do MPS operacional.'
    def add_arguments(self,p): p.add_argument('--plant',required=True); p.add_argument('--dtf',type=int,default=14); p.add_argument('--ptf',type=int,default=42)
    def handle(self,*args,**o):
        plant=Plant.objects.filter(code=o['plant']).first()
        if not plant: raise CommandError('Planta não encontrada.')
        obj,_=MPSOperationalPolicy.objects.update_or_create(plant=plant,defaults={'demand_time_fence_days':o['dtf'],'planning_time_fence_days':o['ptf']})
        self.stdout.write(self.style.SUCCESS(f'{plant.code}: DTF={obj.demand_time_fence_days}d PTF={obj.planning_time_fence_days}d'))
