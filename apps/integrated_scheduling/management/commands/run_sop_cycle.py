from datetime import date
from django.core.management.base import BaseCommand, CommandError
from apps.common.models import Plant
from apps.integrated_scheduling.sop_cycle import create_sop_cycle, build_supply_review, advance_cycle

class Command(BaseCommand):
    help='Cria uma nova versão mensal do ciclo S&OP e carrega baseline/supply review.'
    def add_arguments(self,p):
        p.add_argument('--plant',required=True); p.add_argument('--month',required=True,help='YYYY-MM')
        p.add_argument('--horizon-end',required=True,help='YYYY-MM-DD'); p.add_argument('--advance-pre-sop',action='store_true')
    def handle(self,*args,**o):
        plant=Plant.objects.filter(code=o['plant']).first()
        if not plant: raise CommandError('Planta não encontrada.')
        try:
            y,m=map(int,o['month'].split('-')); cm=date(y,m,1); end=date.fromisoformat(o['horizon_end'])
            cycle=create_sop_cycle(plant,cm,end); build_supply_review(cycle)
            if o['advance_pre_sop']: advance_cycle(cycle)
        except Exception as exc: raise CommandError(str(exc))
        self.stdout.write(self.style.SUCCESS(f'{cycle} status={cycle.status}'))
