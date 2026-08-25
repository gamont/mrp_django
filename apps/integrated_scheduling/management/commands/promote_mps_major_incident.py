from django.core.management.base import BaseCommand, CommandError
from apps.integrated_scheduling.models import MPSDecisionComplianceIncident
from apps.integrated_scheduling.mps_incident_command import promote_compliance_incident

class Command(BaseCommand):
    help='Promove um incidente de compliance a Major Incident 0.9.9.'
    def add_arguments(self,parser): parser.add_argument('--incident',type=int,required=True); parser.add_argument('--title',default='')
    def handle(self,*args,**opts):
        ci=MPSDecisionComplianceIncident.objects.filter(pk=opts['incident']).first()
        if not ci: raise CommandError('Incidente de compliance não encontrado.')
        obj,created=promote_compliance_incident(ci,title=opts['title'])
        self.stdout.write(self.style.SUCCESS(f'{obj.code} created={created}'))
