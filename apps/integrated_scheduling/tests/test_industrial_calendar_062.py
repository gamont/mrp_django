from datetime import datetime, time, timedelta
from decimal import Decimal

from django.test import TestCase
from django.utils import timezone

from apps.common.models import Plant, ShopCalendarDay
from apps.masterdata.models import Item, WorkCenter, WorkCenterShift
from apps.production.models import WorkOrder, WorkOrderOperation
from apps.shopfloor.models import Machine
from apps.integrated_scheduling.models import (
    IndustrialCalendarWindow, IndustrialShiftBreak, IntegratedScheduleScenario,
)
from apps.integrated_scheduling.advanced import run_finite_scenario


class IndustrialCalendar062Tests(TestCase):
    def setUp(self):
        self.plant = Plant.objects.create(code="SP01", name="São Paulo")
        self.center = WorkCenter.objects.create(plant=self.plant, code="MONT", name="Montagem", capacity_hours_per_day=8)
        self.machine = Machine.objects.create(plant=self.plant, work_center=self.center, code="M1", name="Máquina 1")
        self.item = Item.objects.create(code="FG-062", description="Produto", item_type=Item.ItemType.FINISHED)
        self.today = timezone.localdate()
        # garantir turno para o weekday do teste
        self.shift = WorkCenterShift.objects.create(
            work_center=self.center, name="A", weekday=self.today.weekday(), start_time=time(8), end_time=time(17),
            capacity_hours=Decimal("8"), efficiency_percent=Decimal("100"),
        )
        IndustrialShiftBreak.objects.create(shift=self.shift, name="Almoço", start_time=time(12), end_time=time(13))

    def _scenario_with_operation(self, hours=Decimal("8")):
        start = timezone.make_aware(datetime.combine(self.today, time(8)))
        wo = WorkOrder.objects.create(
            number="OP-062", plant=self.plant, item=self.item, quantity=10, release_date=self.today,
            due_date=self.today + timedelta(days=3), status=WorkOrder.Status.RELEASED,
        )
        WorkOrderOperation.objects.create(
            work_order=wo, sequence=10, description="Montar", work_center=self.center,
            planned_start=start, planned_end=start + timedelta(hours=float(hours)), run_hours=hours,
        )
        return IntegratedScheduleScenario.objects.create(
            name="Calendar", plant=self.plant, horizon_start=self.today, horizon_end=self.today + timedelta(days=3),
            finite_by_machine=True, scheduling_direction="FORWARD", respect_industrial_calendar=True,
        )

    def test_break_splits_operation(self):
        scenario = self._scenario_with_operation(Decimal("8"))
        run_finite_scenario(scenario=scenario)
        block = scenario.blocks.get(block_type="PRODUCTION")
        self.assertGreaterEqual(block.segments.count(), 2)
        self.assertFalse(block.segments.filter(start__time__lt=time(13), end__time__gt=time(12)).exists())

    def test_holiday_blocks_regular_capacity_but_overtime_can_restore(self):
        ShopCalendarDay.objects.create(plant=self.plant, date=self.today, is_working_day=False, capacity_factor=1, note="Feriado")
        IndustrialCalendarWindow.objects.create(
            plant=self.plant, work_center=self.center, machine=self.machine, date=self.today,
            start_time=time(18), end_time=time(22), window_type="OVERTIME", capacity_factor=1,
        )
        scenario = self._scenario_with_operation(Decimal("4"))
        run_finite_scenario(scenario=scenario)
        block = scenario.blocks.get(block_type="PRODUCTION")
        seg = block.segments.get()
        self.assertEqual(seg.segment_type, "OVERTIME")
        self.assertEqual(timezone.localtime(seg.start).time().hour, 18)

    def test_capacity_factor_extends_elapsed_time(self):
        ShopCalendarDay.objects.create(plant=self.plant, date=self.today, is_working_day=True, capacity_factor=Decimal("0.5"))
        scenario = self._scenario_with_operation(Decimal("4"))
        run_finite_scenario(scenario=scenario)
        block = scenario.blocks.get(block_type="PRODUCTION")
        elapsed = sum((s.end - s.start for s in block.segments.all()), timedelta())
        self.assertGreaterEqual(elapsed.total_seconds() / 3600, 8)
