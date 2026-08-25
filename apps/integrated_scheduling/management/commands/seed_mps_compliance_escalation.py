from django.core.management.base import BaseCommand, CommandError
from apps.common.models import Plant
from apps.integrated_scheduling.models import MPSComplianceEscalationPolicy,MPSComplianceEscalationRule

class Command(BaseCommand):
    help='Cria política demonstrativa de escalonamento 0.9.7.'
    def add_arguments(self,p):
        p.add_argument('--plant',required=True)
        p.add_argument('--email',action='append',default=[])
    def handle(self,*args,**o):
        plant=Plant.objects.filter(code=o['plant']).first()
        if not plant: raise CommandError('Planta não encontrada.')
        policy,_=MPSComplianceEscalationPolicy.objects.get_or_create(plant=plant)
        defs=[
            (10,'Equipe', 'TEAM',0,['HIGH','CRITICAL']),
            (20,'Gerente 30 min','MANAGER',30,['HIGH','CRITICAL']),
            (30,'Diretor 60 min','DIRECTOR',60,['CRITICAL']),
            (40,'Executivo 120 min','EXECUTIVE',120,['CRITICAL']),
        ]
        for order,name,level,mins,sevs in defs:
            MPSComplianceEscalationRule.objects.update_or_create(policy=policy,order=order,defaults={'name':name,'level':level,'after_minutes':mins,'severities':sevs,'recipient_emails':o['email'],'is_active':True})
        self.stdout.write(self.style.SUCCESS(f'Política 0.9.7 criada para {plant.code} com {len(defs)} regra(s).'))
