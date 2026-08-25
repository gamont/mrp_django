from django.core.management.base import BaseCommand, CommandError
from apps.common.models import Plant
from apps.integrated_scheduling.models import MPSDecisionAnchorPolicy, MPSDecisionAuditAnchor
class Command(BaseCommand):
    help='0.9.5: cria/atualiza política padrão de âncora por planta.'
    def add_arguments(self,p):
        p.add_argument('--plant',required=True); p.add_argument('--max-age-hours',type=int,default=24); p.add_argument('--secondary',action='store_true')
    def handle(self,*a,**o):
        plant=Plant.objects.filter(code=o['plant']).first()
        if not plant:raise CommandError('Planta não encontrada.')
        providers=[MPSDecisionAuditAnchor.Provider.FILE_APPEND_ONLY]
        if o['secondary']:providers.append(MPSDecisionAuditAnchor.Provider.FILE_SECONDARY)
        obj,_=MPSDecisionAnchorPolicy.objects.update_or_create(plant=plant,defaults={'is_active':True,'cadence':'BOTH','required_providers':providers,'max_anchor_age_hours':o['max_age_hours'],'retention_days':3650,'verify_after_publish':True})
        self.stdout.write(self.style.SUCCESS(f'{plant.code}: {obj.cadence}, providers={obj.required_providers}'))
