from django.test import TestCase
from django.utils import timezone
from apps.common.models import Plant
from apps.integrated_scheduling.models import ReschedulingTrigger
from apps.integrated_scheduling.execution import create_rescheduling_trigger

class Recovery071Tests(TestCase):
    def test_trigger_new_statuses_and_summary(self):
        plant=Plant.objects.create(code='SP01',name='SP')
        tr=create_rescheduling_trigger(plant=plant,trigger_type=ReschedulingTrigger.TriggerType.MANUAL,idempotency_key='071-manual')
        self.assertEqual(tr.status, ReschedulingTrigger.Status.NEW)
        tr.recovery_summary={'moved_operations':3}; tr.save(update_fields=['recovery_summary'])
        tr.refresh_from_db(); self.assertEqual(tr.recovery_summary['moved_operations'],3)
