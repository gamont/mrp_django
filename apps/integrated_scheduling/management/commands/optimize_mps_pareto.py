from django.core.management.base import BaseCommand
from apps.integrated_scheduling.models import MPSRevision
from apps.integrated_scheduling.mps_optimizer import create_optimization_run
from apps.integrated_scheduling.mps_pareto_optimizer import run_pareto_optimizer
class Command(BaseCommand):
    help='0.8.9: gera e avalia fronteira Pareto CP-SAT para uma revisão MPS.'
    def add_arguments(self,p):
        p.add_argument('--revision',type=int,required=True); p.add_argument('--compare',type=int)
    def handle(self,*a,**o):
        rev=MPSRevision.objects.get(pk=o['revision']); comp=MPSRevision.objects.get(pk=o['compare']) if o.get('compare') else None
        run=create_optimization_run(rev,comp); run.optimizer_mode='CP_SAT_PARETO'; run.save(update_fields=['optimizer_mode','updated_at']); run=run_pareto_optimizer(run)
        self.stdout.write(self.style.SUCCESS(f'Run #{run.id}: {run.summary.get("candidate_count")} candidatos; fronteira={run.summary.get("pareto_frontier_count")}'))
        for c in run.candidates.order_by('pareto_rank','rank'): self.stdout.write(f'F{c.pareto_rank} #{c.rank} {c.name} pareto={c.is_pareto} vector={c.objective_vector}')
