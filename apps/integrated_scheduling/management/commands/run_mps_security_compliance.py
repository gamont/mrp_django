from django.core.management.base import BaseCommand
from apps.integrated_scheduling.mps_security_compliance import run_security_compliance
class Command(BaseCommand):
    help='Executa o Security & Compliance Center 0.9.6, remedia âncoras/evidências e gera snapshots.'
    def add_arguments(self,p): p.add_argument('--no-remediate',action='store_true')
    def handle(self,*a,**o):
        rows=run_security_compliance(remediate=not o['no_remediate'])
        for r in rows:
            if r.get('summary'): self.stdout.write(f"plant={r['plant']} snapshot={r['snapshot_id']} alerts={r['alerts_sent']}")
            else: self.stdout.write(f"cockpit={r.get('cockpit_id')} criticality={r.get('criticality')} protection={r.get('protection',{}).get('status')} incidents={r.get('active_incidents')}")
