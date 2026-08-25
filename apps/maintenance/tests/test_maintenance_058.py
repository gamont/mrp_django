from decimal import Decimal
from django.contrib.auth import get_user_model
from django.test import TestCase
from django.utils import timezone
from datetime import timedelta
from apps.common.models import Plant
from apps.maintenance.models import MaintenanceAsset, MaintenanceWorkOrder, ConditionReading, ConditionRule, TechnicianProfile
from apps.maintenance.services import evaluate_condition_reading, weekly_maintenance_plan

class Maintenance058Tests(TestCase):
    def setUp(self):
        self.plant = Plant.objects.create(code="SP01", name="São Paulo")
        self.asset = MaintenanceAsset.objects.create(plant=self.plant, code="M01", name="Montadora")
        self.user = get_user_model().objects.create_user(username="tec", password="x")

    def test_condition_rule_generates_predictive_order(self):
        ConditionRule.objects.create(asset=self.asset, code="VIB-HI", metric="VIBRATION", comparator="GTE", threshold=Decimal("8.0"), title="Inspecionar vibração")
        reading = ConditionReading.objects.create(asset=self.asset, metric="VIBRATION", value=Decimal("8.5"), unit="mm/s")
        orders = evaluate_condition_reading(reading=reading, actor=self.user)
        self.assertEqual(len(orders), 1)
        self.assertEqual(orders[0].order_type, MaintenanceWorkOrder.OrderType.PREDICTIVE)

    def test_weekly_capacity(self):
        TechnicianProfile.objects.create(user=self.user, plant=self.plant, employee_code="T001", daily_capacity_hours=Decimal("8"))
        monday = timezone.localdate() - timedelta(days=timezone.localdate().weekday())
        result = weekly_maintenance_plan(plant=self.plant, week_start=monday)
        self.assertEqual(result["technicians"][0]["capacity_hours"], Decimal("40"))
