from django.core.management.base import BaseCommand, CommandError
from apps.integrated_scheduling.models import MPSRevisionSimulation
from apps.integrated_scheduling.working_capital_whatif import build_working_capital_impact
class Command(BaseCommand):
    help='Gera/regera capital de giro e cash conversion proxy para uma simulação MPS.'
    def add_arguments(self,p):
        p.add_argument('--simulation',type=int,required=True); p.add_argument('--bucket-type',choices=['WEEKLY','MONTHLY'])
    def handle(self,*args,**o):
        sim=MPSRevisionSimulation.objects.filter(pk=o['simulation']).first()
        if not sim: raise CommandError('Simulação não encontrada.')
        try:r=build_working_capital_impact(sim,o.get('bucket_type'))
        except Exception as exc: raise CommandError(str(exc))
        self.stdout.write(self.style.SUCCESS(f"Capital de giro 0.8.6 gerado: pico revisão={r.get('peak_working_capital_need',{}).get('right','—')}"))
