from django.test import TestCase
from django.utils import timezone
from apps.common.models import Plant
from apps.integrated_scheduling.models import RecoveryPolicy, ReschedulingTrigger
from apps.integrated_scheduling.control_center import get_policy, calculate_trigger_impact

class RecoveryControlCenter072Tests(TestCase):
    def setUp(self):
        self.plant = Plant.objects.create(code="T072", name="Test 072")
    def test_default_policy_is_safe(self):
        p = get_policy(self.plant)
        self.assertFalse(p.auto_publish_enabled)
        self.assertEqual(p.candidate_count, 3)
    def test_trigger_receives_severity_and_eta(self):
        t = ReschedulingTrigger.objects.create(plant=self.plant, trigger_type="MANUAL", affected_from=timezone.now(), idempotency_key="t072-manual")
        impact = calculate_trigger_impact(t)
        t.refresh_from_db()
        self.assertIn(t.severity, {"LOW","MEDIUM","HIGH","CRITICAL"})
        self.assertGreater(t.recovery_eta_seconds, 0)
        self.assertEqual(impact["affected_work_orders"], 0)
