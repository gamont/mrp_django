from decimal import Decimal
from django.test import TestCase
from apps.common.models import Plant
from apps.integrated_scheduling.models import LaborResource, LaborRuleSet

class LaborCost069Tests(TestCase):
    def test_resource_cost_and_preference(self):
        plant=Plant.objects.create(code="P069", name="Plant 069")
        worker=LaborResource.objects.create(plant=plant, employee_code="E069", name="Worker", hourly_cost=Decimal("50.00"), preference_score=90)
        self.assertEqual(worker.hourly_cost, Decimal("50.00"))
        self.assertEqual(worker.preference_score, 90)

    def test_rule_set_limits(self):
        plant=Plant.objects.create(code="P069B", name="Plant 069B")
        rule=LaborRuleSet.objects.create(plant=plant, code="STD", name="Standard", effective_from="2026-01-01", normal_daily_hours=8, max_daily_hours=10, max_weekly_hours=44, overtime_multiplier=Decimal("1.5"), night_premium_percent=Decimal("20"))
        self.assertEqual(rule.max_weekly_hours, Decimal("44"))
