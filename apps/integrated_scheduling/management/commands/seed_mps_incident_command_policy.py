from django.core.management.base import BaseCommand, CommandError
from apps.common.models import Plant
from apps.integrated_scheduling.models import MPSIncidentCommandPolicy

class Command(BaseCommand):
    help='Cria/atualiza a política 0.9.9 de Incident Command para uma planta.'
    def add_arguments(self,parser): parser.add_argument('--plant',required=True)
    def handle(self,*args,**opts):
        plant=Plant.objects.filter(code=opts['plant']).first()
        if not plant: raise CommandError('Planta não encontrada.')
        obj,_=MPSIncidentCommandPolicy.objects.update_or_create(plant=plant,defaults={'is_active':True,'auto_promote_levels':['EXECUTIVE'],'auto_promote_severities':['CRITICAL'],'require_postmortem_for':['SEV1','SEV2']})
        self.stdout.write(self.style.SUCCESS(f'{plant.code}: policy #{obj.id}'))
