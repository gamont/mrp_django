from django.test import TestCase
from apps.integrated_scheduling.models import MPSDecisionGovernancePolicy,MPSDecisionAreaApproval

class Governance091ContractTests(TestCase):
    def test_default_required_areas_cover_cross_functional_review(self):
        self.assertEqual(MPSDecisionGovernancePolicy.DEFAULT_AREAS,["PLANNING","PRODUCTION","PURCHASING","SALES","FINANCE"])
    def test_area_decision_values(self):
        self.assertIn("APPROVED",MPSDecisionAreaApproval.Decision.values)
        self.assertIn("REJECTED",MPSDecisionAreaApproval.Decision.values)
