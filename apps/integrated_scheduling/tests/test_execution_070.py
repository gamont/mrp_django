from django.test import TestCase
from django.utils import timezone

from apps.common.models import Plant
from apps.integrated_scheduling.execution import create_rescheduling_trigger, prepare_rescheduling_scenario
from apps.integrated_scheduling.models import ReschedulingTrigger


class ScheduleExecution070Tests(TestCase):
    def setUp(self):
        self.plant = Plant.objects.create(code="SP01", name="São Paulo")

    def test_rescheduling_trigger_is_idempotent(self):
        now = timezone.now()
        a = create_rescheduling_trigger(
            plant=self.plant,
            trigger_type=ReschedulingTrigger.TriggerType.MACHINE_BREAKDOWN,
            affected_from=now,
            source_type="Machine",
            source_id="10",
            idempotency_key="breakdown-10-001",
        )
        b = create_rescheduling_trigger(
            plant=self.plant,
            trigger_type=ReschedulingTrigger.TriggerType.MACHINE_BREAKDOWN,
            affected_from=now,
            source_type="Machine",
            source_id="10",
            idempotency_key="breakdown-10-001",
        )
        self.assertEqual(a.pk, b.pk)
        self.assertEqual(ReschedulingTrigger.objects.count(), 1)

    def test_trigger_prepares_replanning_scenario(self):
        trigger = create_rescheduling_trigger(
            plant=self.plant,
            trigger_type=ReschedulingTrigger.TriggerType.MATERIAL_SHORTAGE,
            source_type="Item",
            source_id="LED-001",
            idempotency_key="shortage-led-001",
        )
        scenario = prepare_rescheduling_scenario(trigger=trigger, horizon_days=7)
        trigger.refresh_from_db()
        self.assertEqual(trigger.status, ReschedulingTrigger.Status.RESCHEDULED)
        self.assertEqual(trigger.resulting_scenario_id, scenario.pk)
        self.assertEqual((scenario.horizon_end - scenario.horizon_start).days, 6)
        self.assertEqual(scenario.parameters["rescheduling_trigger_id"], trigger.pk)
