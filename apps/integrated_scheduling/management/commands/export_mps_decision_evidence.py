from pathlib import Path
from django.core.management.base import BaseCommand, CommandError
from apps.integrated_scheduling.models import MPSDecisionCockpit
from apps.integrated_scheduling.mps_decision_audit import build_evidence_zip, verify_audit_chain
class Command(BaseCommand):
    help='Verifica a cadeia 0.9.3 e exporta o pacote de evidências de um cockpit MPS.'
    def add_arguments(self,p): p.add_argument('--cockpit',type=int,required=True); p.add_argument('--output',default='')
    def handle(self,*args,**o):
        c=MPSDecisionCockpit.objects.filter(pk=o['cockpit']).first()
        if not c: raise CommandError('Cockpit não encontrado.')
        before=verify_audit_chain(c)
        if not before['ok']: raise CommandError(f'Cadeia inválida: {before["errors"]}')
        name,raw,sha,_=build_evidence_zip(c,None); out=Path(o['output'] or name); out.write_bytes(raw)
        self.stdout.write(self.style.SUCCESS(f'{out} sha256={sha}'))
