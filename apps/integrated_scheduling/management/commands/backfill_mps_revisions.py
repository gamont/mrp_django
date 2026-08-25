from django.core.management.base import BaseCommand
from apps.integrated_scheduling.models import OperationalMPSPublication
from apps.integrated_scheduling.mps_revision import capture_revision

class Command(BaseCommand):
    help = 'Cria revisão baseline 0.8.2 para MPS operacionais antigos que ainda não possuem histórico.'
    def handle(self, *args, **options):
        count=0
        for pub in OperationalMPSPublication.objects.filter(revisions__isnull=True).distinct():
            if not pub.weekly_buckets.exists():
                continue
            capture_revision(pub,kind='BASELINE',label='Baseline migrado 0.8.2',notes='Snapshot criado após upgrade da 0.8.1.',auto_approve=True)
            count+=1
        self.stdout.write(self.style.SUCCESS(f'{count} publicação(ões) receberam baseline de revisão.'))
