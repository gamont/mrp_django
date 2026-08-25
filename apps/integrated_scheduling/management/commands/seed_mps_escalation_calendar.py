from datetime import date
from django.core.management.base import BaseCommand, CommandError
from apps.common.models import Plant
from apps.integrated_scheduling.models import MPSComplianceHoliday
class Command(BaseCommand):
    help='Cadastra feriados corporativos do Compliance Escalation 0.9.8.'
    def add_arguments(self,p):
        p.add_argument('--plant',required=True); p.add_argument('--date',required=True); p.add_argument('--name',required=True)
    def handle(self,*args,**o):
        plant=Plant.objects.filter(code=o['plant']).first()
        if not plant: raise CommandError('Planta não encontrada.')
        d=date.fromisoformat(o['date'])
        obj,_=MPSComplianceHoliday.objects.update_or_create(plant=plant,date=d,defaults={'name':o['name'],'is_active':True})
        self.stdout.write(self.style.SUCCESS(f'{plant.code} {obj.date} {obj.name}'))
