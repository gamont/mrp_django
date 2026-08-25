from django.core.management.base import BaseCommand
from apps.integrated_scheduling.tasks import auto_process_rescheduling_trigger_task
class Command(BaseCommand):
    help='Prepara cenário e executa recovery CP-SAT para um trigger.'
    def add_arguments(self,p): p.add_argument('--trigger',type=int,required=True); p.add_argument('--days',type=int,default=14)
    def handle(self,*a,**o): self.stdout.write(str(auto_process_rescheduling_trigger_task(o['trigger'],o['days'])))
