from django.test import TestCase
from django.contrib.auth import get_user_model
from apps.common.models import Plant
from apps.integrated_scheduling.models import (
    MPSDecisionCockpit, MPSDecisionCandidateReview,
    MPSRevisionOptimizationRun, MPSRevisionOptimizationCandidate,
)


class DecisionCockpitModelTest(TestCase):
    def test_status_contract(self):
        self.assertIn(("FROZEN", "Congelado como plano oficial"), MPSDecisionCockpit.Status.choices)
        self.assertTrue(hasattr(MPSRevisionOptimizationCandidate, "objective_vector"))

    def test_review_unique_contract(self):
        names=[c.name for c in MPSDecisionCandidateReview._meta.constraints]
        self.assertIn("uq_mpsdec_cockpit_candidate", names)
