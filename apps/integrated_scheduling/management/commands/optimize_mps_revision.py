from django.core.management.base import BaseCommand, CommandError
from apps.integrated_scheduling.models import MPSRevision
from apps.integrated_scheduling.mps_optimizer import create_optimization_run, run_optimizer

class Command(BaseCommand):
    help='Gera e avalia alternativas MPS 0.8.8 usando MRP, RCCP e métricas financeiras.'
    def add_arguments(self,parser):
        parser.add_argument('--revision',type=int,required=True)
        parser.add_argument('--compare',type=int)
    def handle(self,*args,**opts):
        rev=MPSRevision.objects.filter(pk=opts['revision']).first()
        if not rev: raise CommandError('Revisão não encontrada.')
        comp=MPSRevision.objects.filter(pk=opts['compare']).first() if opts.get('compare') else None
        try:
            run=run_optimizer(create_optimization_run(rev,comp))
        except Exception as exc: raise CommandError(str(exc))
        self.stdout.write(self.style.SUCCESS(f'Optimization #{run.id} concluída: {run.summary}'))
        for c in run.candidates.order_by('rank'):
            self.stdout.write(f'#{c.rank} {c.strategy} score={c.score} recommended={c.is_recommended} revision={c.generated_revision_id} simulation={c.simulation_id}')
