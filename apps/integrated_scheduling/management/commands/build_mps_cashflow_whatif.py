from django.core.management.base import BaseCommand, CommandError
from apps.integrated_scheduling.models import MPSRevisionSimulation
from apps.integrated_scheduling.mps_cashflow_whatif import build_cashflow_impact

class Command(BaseCommand):
    help='Gera/regera cash-flow temporal budget × baseline × revisão para uma simulação MPS.'
    def add_arguments(self,p):
        p.add_argument('--simulation',type=int,required=True)
        p.add_argument('--budget',type=int)
        p.add_argument('--bucket-type',choices=['WEEKLY','MONTHLY'])
    def handle(self,*args,**o):
        sim=MPSRevisionSimulation.objects.filter(pk=o['simulation']).first()
        if not sim: raise CommandError('Simulação não encontrada.')
        try: result=build_cashflow_impact(sim,o.get('budget'),o.get('bucket_type'))
        except Exception as exc: raise CommandError(str(exc))
        self.stdout.write(self.style.SUCCESS(f"Cash-flow 0.8.5 gerado para simulação {sim.id}: {result['bucket_type']} / budget={result['budget_code'] or 'sem budget'}"))
