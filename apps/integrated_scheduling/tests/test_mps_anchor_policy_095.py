from django.test import SimpleTestCase
from apps.integrated_scheduling.models import MPSDecisionAnchorPolicy, MPSDecisionAuditAnchor

class AnchorPolicy095ContractTests(SimpleTestCase):
    def test_policy_cadences(self):
        self.assertEqual(MPSDecisionAnchorPolicy.Cadence.BOTH, "BOTH")
        self.assertIn("DAILY", MPSDecisionAnchorPolicy.Cadence.values)

    def test_independent_file_provider_exists(self):
        self.assertIn("FILE_SECONDARY", MPSDecisionAuditAnchor.Provider.values)
