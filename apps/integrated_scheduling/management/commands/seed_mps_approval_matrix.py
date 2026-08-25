from django.core.management.base import BaseCommand
from apps.masterdata.models import Plant
from apps.integrated_scheduling.models import MPSDecisionApprovalMatrix as M
class Command(BaseCommand):
    help='Cria matriz inicial de alçadas MPS 0.9.2.'
    def add_arguments(self,p): p.add_argument('--plant',required=True)
    def handle(self,*a,**o):
        plant=Plant.objects.get(code=o['plant'])
        rows=[('Gerência padrão',M.Level.MANAGER,10,True,'0','0','0','0',['MPS Managers'],1),('Diretoria',M.Level.DIRECTOR,20,False,'1000000','1500000','500000','10',['MPS Directors'],1),('Comitê executivo',M.Level.EXECUTIVE_COMMITTEE,30,False,'5000000','5000000','2000000','25',['Executive Committee'],2)]
        for name,level,prio,default,pur,wc,fin,risk,groups,sigs in rows:
            M.objects.update_or_create(plant=plant,name=name,defaults={'level':level,'priority':prio,'is_default':default,'min_purchase_spend':pur,'min_peak_working_capital':wc,'min_peak_financing_need':fin,'min_service_risk_proxy':risk,'required_groups':groups,'required_signatures':sigs,'is_active':True})
        self.stdout.write(self.style.SUCCESS(f'Matriz 0.9.2 criada para {plant.code}. Ajuste grupos/limites antes do uso produtivo.'))
