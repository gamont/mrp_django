from django.core.management.base import BaseCommand,CommandError
from apps.common.models import Plant
from apps.integrated_scheduling.mps_security_compliance import build_compliance_snapshot
class Command(BaseCommand):
    help='Gera/atualiza o snapshot diário de compliance de uma planta.'
    def add_arguments(self,p): p.add_argument('--plant',required=True)
    def handle(self,*a,**o):
        plant=Plant.objects.filter(code=o['plant']).first()
        if not plant: raise CommandError('Planta não encontrada.')
        s=build_compliance_snapshot(plant)
        self.stdout.write(self.style.SUCCESS(f'{plant.code} {s.snapshot_date}: protected={s.protected_percent}% evidence={s.evidence_current_percent}%'))
