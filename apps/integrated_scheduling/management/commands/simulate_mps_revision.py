from django.core.management.base import BaseCommand, CommandError
from apps.integrated_scheduling.models import MPSRevision
from apps.integrated_scheduling.mps_whatif import create_simulation, run_simulation

class Command(BaseCommand):
    help='Executa MRP what-if de uma revisão MPS e compara com outra revisão/baseline.'
    def add_arguments(self,p):
        p.add_argument('--revision',type=int,required=True)
        p.add_argument('--compare',type=int)
    def handle(self,*args,**opts):
        rev=MPSRevision.objects.filter(pk=opts['revision']).first()
        if not rev: raise CommandError('Revisão não encontrada.')
        comp=MPSRevision.objects.filter(pk=opts['compare']).first() if opts.get('compare') else None
        sim=run_simulation(create_simulation(rev,comp))
        self.stdout.write(self.style.SUCCESS(f'Simulação #{sim.id}: r{sim.revision.number} vs r{sim.compare_revision.number} — {sim.status}'))
        self.stdout.write(str(sim.diff_summary))
