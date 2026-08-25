from django.test import SimpleTestCase
from apps.integrated_scheduling.models import MPSComplianceEscalationRule, MPSComplianceNotificationDelivery
class EscalationCalendar098ContractTests(SimpleTestCase):
    def test_acknowledged_clock_is_available(self):
        self.assertEqual(MPSComplianceEscalationRule.ClockBasis.ACKNOWLEDGED,'ACKNOWLEDGED')
    def test_delivery_channels(self):
        self.assertIn(('SLACK','Slack webhook'), MPSComplianceNotificationDelivery.Channel.choices)
        self.assertIn(('TEAMS','Teams webhook'), MPSComplianceNotificationDelivery.Channel.choices)
