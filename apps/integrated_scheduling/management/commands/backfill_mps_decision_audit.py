from django.core.management.base import BaseCommand
from apps.integrated_scheduling.models import MPSDecisionCockpit
from apps.integrated_scheduling.mps_decision_audit import append_audit_event
class Command(BaseCommand):
    help="Inicia a cadeia 0.9.3 em cockpits legados sem inventar eventos históricos."
    def add_arguments(self,p): p.add_argument('--cockpit',type=int)
    def handle(self,*args,**o):
        qs=MPSDecisionCockpit.objects.all();
        if o.get('cockpit'): qs=qs.filter(pk=o['cockpit'])
        n=0
        for c in qs:
            if c.audit_events.exists(): continue
            append_audit_event(c,'LEGACY_BOOTSTRAP',None,{'legacy_version':'<=0.9.2','status':c.status,'selected_candidate_id':c.selected_candidate_id,'official_revision_id':c.official_revision_id,'decision_snapshot':c.decision_snapshot or {}}); n+=1
        self.stdout.write(self.style.SUCCESS(f'{n} cockpit(s) inicializado(s).'))
