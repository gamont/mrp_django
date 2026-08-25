from django.core.management.base import BaseCommand, CommandError
from apps.integrated_scheduling.models import MPSRevisionSimulation
from apps.integrated_scheduling.mps_financial_whatif import build_financial_impact

class Command(BaseCommand):
    help='Recalcula somente a camada financeira de uma simulação MRP what-if concluída.'

    def add_arguments(self, parser):
        parser.add_argument('--simulation', type=int, required=True)

    def handle(self, *args, **opts):
        sim=MPSRevisionSimulation.objects.filter(pk=opts['simulation']).select_related('revision__publication__cycle','target_planning_run','compare_planning_run').first()
        if not sim:
            raise CommandError('Simulação não encontrada.')
        if not sim.target_planning_run_id or not sim.compare_planning_run_id:
            raise CommandError('A simulação ainda não possui os dois PlanningRun necessários.')
        summary=build_financial_impact(sim)
        self.stdout.write(self.style.SUCCESS(f"Simulação #{sim.id}: financeiro={summary['status']} versão={summary.get('cost_version_code') or '—'} cobertura={summary['valuation_item_coverage_pct']}%"))
