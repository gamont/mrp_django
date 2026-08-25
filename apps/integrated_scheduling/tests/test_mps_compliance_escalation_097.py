from django.test import SimpleTestCase
from apps.integrated_scheduling.models import MPSComplianceEscalationRule, MPSComplianceEscalationEvent

class MPSComplianceEscalation097ContractTests(SimpleTestCase):
    def test_levels_are_progressive(self):
        values=[x[0] for x in MPSComplianceEscalationRule.Level.choices]
        self.assertEqual(values,['TEAM','MANAGER','DIRECTOR','EXECUTIVE'])

    def test_event_status_contract(self):
        values={x[0] for x in MPSComplianceEscalationEvent.Status.choices}
        self.assertEqual(values,{'ACTIVE','STOPPED'})
