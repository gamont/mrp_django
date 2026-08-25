from django.core.management.base import BaseCommand
from django.utils import timezone
from apps.common.models import Plant
from apps.integrated_scheduling.models import ServiceLevelTarget
class Command(BaseCommand):
    help='Cria meta gerencial inicial de nível de serviço por planta.'
    def add_arguments(self,p): p.add_argument('--plant',required=True)
    def handle(self,*a,**o):
        plant=Plant.objects.get(code=o['plant'])
        obj,created=ServiceLevelTarget.objects.get_or_create(plant=plant,scope='PLANT',scope_key='',effective_from=timezone.localdate().replace(day=1),defaults={'scope_label':plant.name,'otif_target_pct':95,'on_time_target_pct':97,'in_full_target_pct':98,'fill_rate_target_pct':98,'perfect_order_target_pct':95})
        self.stdout.write(self.style.SUCCESS(f'{"Criada" if created else "Existente"}: meta {plant.code} OTIF={obj.otif_target_pct}%'))
