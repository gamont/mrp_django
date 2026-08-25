from django.core.management.base import BaseCommand,CommandError
from apps.common.models import Plant
from apps.integrated_scheduling.models import MPSDecisionCompliancePolicy
class Command(BaseCommand):
    help='Cria/atualiza política inicial do Security & Compliance Center 0.9.6.'
    def add_arguments(self,p):
        p.add_argument('--plant',required=True); p.add_argument('--email',action='append',default=[])
        p.add_argument('--standard-sla',type=int,default=24); p.add_argument('--high-sla',type=int,default=12); p.add_argument('--critical-sla',type=int,default=4)
    def handle(self,*a,**o):
        plant=Plant.objects.filter(code=o['plant']).first()
        if not plant: raise CommandError('Planta não encontrada.')
        obj,_=MPSDecisionCompliancePolicy.objects.update_or_create(plant=plant,defaults={'alert_recipients':o['email'],'standard_sla_hours':o['standard_sla'],'high_sla_hours':o['high_sla'],'critical_sla_hours':o['critical_sla']})
        self.stdout.write(self.style.SUCCESS(f'{plant.code}: compliance policy #{obj.id} criada/atualizada.'))
