from django.core.management.base import BaseCommand
from apps.integrated_scheduling.mps_anchor_policy import run_anchor_policy
class Command(BaseCommand):
    help='0.9.5: aplica política automática de âncoras e mostra proteção dos cockpits.'
    def handle(self,*args,**options):
        rows=run_anchor_policy()
        for r in rows:self.stdout.write(f"cockpit={r['cockpit_id']} created={r['created']} status={r['status']}")
        self.stdout.write(self.style.SUCCESS(f"{len(rows)} cockpit(s) avaliados."))
