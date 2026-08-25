from django.core.management.base import BaseCommand, CommandError
from apps.integrated_scheduling.models import OperationalMPSPublication, MPSRevision
from apps.integrated_scheduling.mps_revision import capture_revision, compare_revisions, rollback_to_revision

class Command(BaseCommand):
    help='Captura, compara ou faz rollback de revisões do MPS operacional.'
    def add_arguments(self,p):
        p.add_argument('--publication',type=int,required=True)
        p.add_argument('--capture',action='store_true')
        p.add_argument('--compare',nargs=2,type=int,metavar=('LEFT','RIGHT'))
        p.add_argument('--rollback',type=int)
        p.add_argument('--label',default='Revisão CLI')
        p.add_argument('--reason',default='')
    def handle(self,*args,**o):
        pub=OperationalMPSPublication.objects.filter(pk=o['publication']).first()
        if not pub: raise CommandError('Publicação não encontrada.')
        if o['capture']:
            r=capture_revision(pub,label=o['label'],notes=o['reason']); self.stdout.write(f'r{r.number} capturada [{r.status}]'); return
        if o['compare']:
            a=MPSRevision.objects.get(publication=pub,number=o['compare'][0]); b=MPSRevision.objects.get(publication=pub,number=o['compare'][1]); d=compare_revisions(a,b)
            self.stdout.write(str(d['estimated_mrp_impact'])); self.stdout.write(str(d['rccp_impact'])); return
        if o['rollback']:
            t=MPSRevision.objects.get(publication=pub,number=o['rollback']); r=rollback_to_revision(pub,t,reason=o['reason']); self.stdout.write(f'rollback -> r{r.number} [{r.status}]'); return
        raise CommandError('Use --capture, --compare LEFT RIGHT ou --rollback REV.')
