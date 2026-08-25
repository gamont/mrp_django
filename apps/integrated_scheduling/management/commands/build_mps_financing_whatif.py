from django.core.management.base import BaseCommand, CommandError
from apps.integrated_scheduling.models import MPSRevisionSimulation
from apps.integrated_scheduling.financing_whatif import build_financing_impact
class Command(BaseCommand):
    help='Reconstrói a análise de capacidade financeira 0.8.7 de uma simulação MPS.'
    def add_arguments(self,p): p.add_argument('--simulation',type=int,required=True)
    def handle(self,*a,**o):
        sim=MPSRevisionSimulation.objects.filter(pk=o['simulation']).first()
        if not sim: raise CommandError('Simulação não encontrada.')
        try:r=build_financing_impact(sim)
        except ValueError as e: raise CommandError(str(e))
        self.stdout.write(self.style.SUCCESS(f"Financiamento 0.8.7: limite={r.get('usable_credit_limit','—')} pico={r.get('peak_draw',{}).get('right','—')} não coberto={r.get('peak_uncovered_need',{}).get('right','—')}"))
