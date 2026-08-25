from datetime import date, timedelta
from decimal import Decimal

from django.test import TestCase
from django.utils import timezone

from apps.common.models import Plant
from apps.masterdata.models import Item, WorkCenter
from apps.production.models import WorkOrder, WorkOrderOperation
from apps.shopfloor.models import Machine
from apps.integrated_scheduling.models import IntegratedScheduleBlock, IntegratedScheduleScenario
from apps.integrated_scheduling.advanced import compare_scenarios, move_schedule_block, run_finite_scenario


class FiniteSchedule061Tests(TestCase):
    def setUp(self):
        self.plant = Plant.objects.create(code="SP01", name="São Paulo")
        self.center = WorkCenter.objects.create(plant=self.plant, code="MONT", name="Montagem", capacity_hours_per_day=16)
        self.m1 = Machine.objects.create(plant=self.plant, work_center=self.center, code="M1", name="Máquina 1")
        self.m2 = Machine.objects.create(plant=self.plant, work_center=self.center, code="M2", name="Máquina 2")
        self.item = Item.objects.create(code="FG-1", description="Produto", item_type=Item.ItemType.FINISHED)
        today = timezone.localdate()
        start = timezone.now().replace(minute=0, second=0, microsecond=0)
        for idx in range(2):
            wo = WorkOrder.objects.create(
                number=f"OP-{idx+1}", plant=self.plant, item=self.item, quantity=10,
                release_date=today, due_date=today + timedelta(days=2), status=WorkOrder.Status.RELEASED,
            )
            WorkOrderOperation.objects.create(
                work_order=wo, sequence=10, description="Montar", work_center=self.center,
                planned_start=start, planned_end=start + timedelta(hours=4), run_hours=Decimal("4"),
            )
        self.scenario = IntegratedScheduleScenario.objects.create(
            name="Finite", plant=self.plant, horizon_start=today, horizon_end=today + timedelta(days=3),
            finite_by_machine=True, scheduling_direction="FORWARD",
        )

    def test_parallel_machines_receive_operations(self):
        run_finite_scenario(scenario=self.scenario)
        machines = set(self.scenario.blocks.filter(block_type="PRODUCTION").values_list("machine_id", flat=True))
        self.assertEqual(machines, {self.m1.id, self.m2.id})

    def test_manual_move_locks_block(self):
        run_finite_scenario(scenario=self.scenario)
        block = self.scenario.blocks.filter(block_type="PRODUCTION").first()
        new_start = block.simulated_start + timedelta(hours=2)
        move_schedule_block(block=block, start=new_start, end=new_start + timedelta(hours=4), machine=self.m2)
        block.refresh_from_db()
        self.assertTrue(block.manually_locked)
        self.assertEqual(block.machine, self.m2)

    def test_compare_prefers_lower_critical_and_late(self):
        self.scenario.simulated_summary = {"critical_conflicts": 1, "conflicts": 2, "late_hours": "3", "shifted_operations": 2}
        self.scenario.save()
        other = IntegratedScheduleScenario.objects.create(
            name="Better", plant=self.plant, horizon_start=self.scenario.horizon_start, horizon_end=self.scenario.horizon_end,
            simulated_summary={"critical_conflicts": 0, "conflicts": 1, "late_hours": "0", "shifted_operations": 1},
        )
        rows = compare_scenarios([self.scenario, other])
        self.assertEqual(rows[0]["name"], "Better")
