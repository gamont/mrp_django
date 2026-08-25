from django.core.management.base import BaseCommand, CommandError
from apps.integrated_scheduling.models import SAndOPCycle
from apps.integrated_scheduling.sop_cycle import publish_cycle_to_mps

class Command(BaseCommand):
    help='Publica um ciclo S&OP aprovado no MPS e cria um PlanningRun MRP em rascunho.'
    def add_arguments(self,p): p.add_argument('--cycle',type=int,required=True); p.add_argument('--no-planning-run',action='store_true')
    def handle(self,*args,**o):
        cycle=SAndOPCycle.objects.filter(pk=o['cycle']).first()
        if not cycle: raise CommandError('Ciclo não encontrado.')
        try: pub=publish_cycle_to_mps(cycle,None,not o['no_planning_run'])
        except Exception as exc: raise CommandError(str(exc))
        self.stdout.write(self.style.SUCCESS(f'{cycle}: MPS={pub.mps_lines}, PlanningRun={pub.planning_run_id or "—"}'))
