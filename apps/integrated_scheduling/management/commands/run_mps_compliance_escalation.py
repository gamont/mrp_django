from django.core.management.base import BaseCommand,CommandError
from apps.common.models import Plant
from apps.integrated_scheduling.mps_compliance_escalation import run_escalation_engine
class Command(BaseCommand):
    help='Executa o Compliance SLA & Escalation Engine 0.9.7.'
    def add_arguments(self,p):
        p.add_argument('--plant'); p.add_argument('--no-email',action='store_true')
    def handle(self,*args,**o):
        plant=None
        if o['plant']:
            plant=Plant.objects.filter(code=o['plant']).first()
            if not plant: raise CommandError('Planta não encontrada.')
        rows=run_escalation_engine(plant=plant,send_notifications=not o['no_email'])
        self.stdout.write(self.style.SUCCESS(f'{len(rows)} incidente(s) avaliado(s).'))
