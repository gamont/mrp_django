from decimal import Decimal
from datetime import timedelta
from django.contrib.auth import get_user_model
from django.test import TestCase
from django.utils import timezone
from apps.common.models import Plant
from apps.maintenance.models import (
    MaintenanceAsset, MaintenanceWorkOrder, TechnicianProfile, TechnicianSkill,
    TechnicianSkillAssignment, MaintenanceRequiredSkill,
)
from apps.maintenance.services import maintenance_priority_score, auto_assign_technicians


class Maintenance059Tests(TestCase):
    def setUp(self):
        self.plant = Plant.objects.create(code="SP01", name="São Paulo")
        self.asset = MaintenanceAsset.objects.create(
            plant=self.plant, code="M01", name="Montadora",
            criticality=MaintenanceAsset.Criticality.CRITICAL,
        )
        self.wo = MaintenanceWorkOrder.objects.create(
            plant=self.plant, number="OM-2026-00001", asset=self.asset,
            order_type=MaintenanceWorkOrder.OrderType.CORRECTIVE,
            priority=MaintenanceWorkOrder.Priority.HIGH,
            title="Falha",
            scheduled_start=timezone.now() + timedelta(days=1),
            scheduled_end=timezone.now() + timedelta(days=1, hours=2),
        )

    def test_priority_score_reflects_criticality_and_priority(self):
        score, reason = maintenance_priority_score(self.wo)
        self.assertGreaterEqual(score, Decimal("50"))
        self.assertEqual(reason["priority"], "30")
        self.assertEqual(reason["criticality"], "30")

    def test_auto_assign_matches_required_skill(self):
        user = get_user_model().objects.create_user(username="tech", password="x")
        tech = TechnicianProfile.objects.create(user=user, plant=self.plant, employee_code="T001", daily_capacity_hours=8)
        skill = TechnicianSkill.objects.create(code="ELEC", name="Elétrica")
        TechnicianSkillAssignment.objects.create(technician=tech, skill=skill, proficiency=4)
        MaintenanceRequiredSkill.objects.create(work_order=self.wo, skill=skill, min_proficiency=3)
        assignments = auto_assign_technicians(work_order=self.wo)
        self.assertEqual(len(assignments), 1)
        self.assertEqual(assignments[0].technician, tech)
