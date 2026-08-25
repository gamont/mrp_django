from django.core.management.base import BaseCommand, CommandError
from apps.integrated_scheduling.models import MPSRevisionOptimizationRun
from apps.integrated_scheduling.mps_decision_cockpit import create_decision_cockpit

class Command(BaseCommand):
    help='0.9.0: cria um cockpit executivo a partir de uma otimização Pareto concluída.'
    def add_arguments(self,parser): parser.add_argument('--run',type=int,required=True)
    def handle(self,*args,**opts):
        run=MPSRevisionOptimizationRun.objects.filter(pk=opts['run']).first()
        if not run: raise CommandError('Run não encontrado.')
        try: obj=create_decision_cockpit(run); self.stdout.write(self.style.SUCCESS(f'Cockpit #{obj.id} criado para run #{run.id}.'))
        except ValueError as exc: raise CommandError(str(exc))
