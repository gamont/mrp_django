from django.core.management.base import BaseCommand, CommandError
from apps.integrated_scheduling.models import MPSDecisionCockpit, MPSDecisionAuditAnchor
from apps.integrated_scheduling.mps_decision_anchor import publish_external_anchor, verify_cockpit_against_latest_anchor
class Command(BaseCommand):
    help='Publica ou verifica a âncora externa da cadeia de auditoria MPS (0.9.4).'
    def add_arguments(self,p):
        p.add_argument('--cockpit',type=int,required=True); p.add_argument('--verify',action='store_true'); p.add_argument('--provider',default='FILE_APPEND_ONLY'); p.add_argument('--external-reference',default='')
    def handle(self,*a,**o):
        c=MPSDecisionCockpit.objects.filter(pk=o['cockpit']).first()
        if not c: raise CommandError('Cockpit não encontrado.')
        if o['verify']:
            r=verify_cockpit_against_latest_anchor(c); self.stdout.write(str(r));
            if not r['ok']: raise CommandError('Verificação da âncora falhou.')
            return
        a=publish_external_anchor(c,None,o['provider'],o['external_reference'])
        self.stdout.write(self.style.SUCCESS(f'Anchor #{a.id}: seq={a.anchored_sequence} head={a.anchored_head_hash} ref={a.external_reference}'))
