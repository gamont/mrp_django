from django.test import TestCase
from apps.integrated_scheduling.models import RecoveryCommercialImpact, CommercialPromiseAlert

class CommercialRecoveryModelTest(TestCase):
    def test_status_contract(self):
        self.assertEqual(RecoveryCommercialImpact.PromiseStatus.LATE, "LATE")
        self.assertEqual(CommercialPromiseAlert.Status.OPEN, "OPEN")
