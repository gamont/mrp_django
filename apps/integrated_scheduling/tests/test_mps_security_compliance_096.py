from django.test import SimpleTestCase
from apps.integrated_scheduling.models import MPSDecisionComplianceIncident
from apps.integrated_scheduling.mps_security_compliance import _severity_for

class MPSDecisionCompliance096ContractTests(SimpleTestCase):
    def test_integrity_mismatch_is_always_critical(self):
        self.assertEqual(_severity_for('MISMATCH','STANDARD'), MPSDecisionComplianceIncident.Severity.CRITICAL)
    def test_high_criticality_escalates_stale(self):
        self.assertEqual(_severity_for('STALE','CRITICAL'), MPSDecisionComplianceIncident.Severity.CRITICAL)
    def test_unprotected_is_at_least_high(self):
        self.assertEqual(_severity_for('UNPROTECTED','STANDARD'), MPSDecisionComplianceIncident.Severity.HIGH)
