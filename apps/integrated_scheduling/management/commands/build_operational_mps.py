from django.core.management.base import BaseCommand, CommandError
from django.utils.dateparse import parse_date
from apps.common.models import Plant
from apps.integrated_scheduling.models import SAndOPCycle
from apps.integrated_scheduling.sop_mps import build_operational_mps, publish_operational_mps, execute_publication_mrp

class Command(BaseCommand):
    help='Constrói MPS operacional semanal 0.8.0 a partir de ciclo S&OP aprovado.'
    def add_arguments(self,p):
        p.add_argument('--plant',required=True); p.add_argument('--cycle',required=True,help='Código, ex SOP-2026-08')
        p.add_argument('--version',type=int); p.add_argument('--as-of'); p.add_argument('--publish',action='store_true'); p.add_argument('--run-mrp',action='store_true'); p.add_argument('--force',action='store_true')
    def handle(self,*args,**o):
        plant=Plant.objects.filter(code=o['plant']).first()
        if not plant: raise CommandError('Planta não encontrada.')
        qs=SAndOPCycle.objects.filter(plant=plant,code=o['cycle'])
        cycle=qs.filter(version=o['version']).first() if o.get('version') else qs.order_by('-version').first()
        if not cycle: raise CommandError('Ciclo S&OP não encontrado.')
        pub=build_operational_mps(cycle,as_of_date=parse_date(o['as_of']) if o.get('as_of') else None)
        self.stdout.write(f'{pub.source}: {pub.weekly_buckets.count()} buckets; status={pub.status}; RCCP={pub.rccp_exceptions.count()}')
        if o['publish']:
            pub=publish_operational_mps(pub,force=o['force']); self.stdout.write(self.style.SUCCESS(f'Publicado; PlanningRun={pub.planning_run_id}'))
        if o['run_mrp']:
            if pub.status != pub.Status.PUBLISHED: pub=publish_operational_mps(pub,force=o['force'])
            run=execute_publication_mrp(pub); self.stdout.write(self.style.SUCCESS(f'MRP #{run.id}: {run.status}'))
