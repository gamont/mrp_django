from decimal import Decimal
from django.test import TestCase

from apps.common.models import Plant
from apps.masterdata.models import Item, WorkCenter
from apps.shopfloor.models import Machine
from apps.integrated_scheduling.models import ProductFamily, ItemSchedulingProfile, SequenceSetupRule, IntegratedScheduleScenario
from apps.integrated_scheduling.sequencing import setup_hours


class SequenceSetup063Tests(TestCase):
    def setUp(self):
        self.plant = Plant.objects.create(code="P1", name="Plant 1")
        self.center = WorkCenter.objects.create(plant=self.plant, code="WC1", name="WC1", capacity_hours_per_day=8)
        self.machine = Machine.objects.create(plant=self.plant, work_center=self.center, code="M1", name="Machine 1")
        self.a = ProductFamily.objects.create(plant=self.plant, code="A", name="Family A")
        self.b = ProductFamily.objects.create(plant=self.plant, code="B", name="Family B")
        self.scenario = IntegratedScheduleScenario.objects.create(name="S", plant=self.plant, horizon_start="2026-08-08", horizon_end="2026-08-09")

    def test_machine_rule_precedes_center_rule(self):
        SequenceSetupRule.objects.create(plant=self.plant, work_center=self.center, from_family=self.a, to_family=self.b, setup_hours=Decimal("2"))
        SequenceSetupRule.objects.create(plant=self.plant, work_center=self.center, machine=self.machine, from_family=self.a, to_family=self.b, setup_hours=Decimal("1.25"))
        value = setup_hours(scenario=self.scenario, center=self.center, machine=self.machine, from_family=self.a, to_family=self.b)
        self.assertEqual(value, Decimal("1.25"))

    def test_item_profile_priority_and_family(self):
        item = Item.objects.create(code="FG1", description="Finished", item_type=Item.ItemType.FINISHED)
        profile = ItemSchedulingProfile.objects.create(plant=self.plant, item=item, family=self.a, commercial_priority=90, campaign_code="CAMP-A")
        self.assertEqual(profile.family, self.a)
        self.assertEqual(profile.commercial_priority, 90)
