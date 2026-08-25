from datetime import datetime, time, timedelta

from django.test import TestCase
from django.utils import timezone

from apps.common.models import Plant
from apps.masterdata.models import WorkCenter, WorkCenterShift
from apps.integrated_scheduling.models import (
    IndustrialShiftBreak,
    LaborResource,
    LaborShiftAssignment,
    LaborUnavailability,
)
from apps.integrated_scheduling.labor import labor_windows


class FiniteLaborCalendarTests(TestCase):
    def test_labor_windows_respect_break_and_unavailability(self):
        plant = Plant.objects.create(code="SP01", name="São Paulo")
        center = WorkCenter.objects.create(plant=plant, code="MONT", name="Montagem")
        shift = WorkCenterShift.objects.create(
            work_center=center,
            name="Turno A",
            weekday=0,
            start_time=time(8, 0),
            end_time=time(17, 0),
            capacity_hours=8,
        )
        IndustrialShiftBreak.objects.create(shift=shift, name="Almoço", start_time=time(12, 0), end_time=time(13, 0))
        worker = LaborResource.objects.create(plant=plant, employee_code="OP001", name="Operador 1")
        LaborShiftAssignment.objects.create(labor_resource=worker, shift=shift)

        monday = timezone.localdate()
        while monday.weekday() != 0:
            monday += timedelta(days=1)
        absence_start = timezone.make_aware(datetime.combine(monday, time(15, 0)))
        absence_end = timezone.make_aware(datetime.combine(monday, time(16, 0)))
        LaborUnavailability.objects.create(labor_resource=worker, start=absence_start, end=absence_end, reason="Treinamento")

        windows = labor_windows(resource=worker, center=center, start_date=monday, end_date=monday)
        pairs = [(timezone.localtime(s).time(), timezone.localtime(e).time()) for s, e, _ in windows]
        self.assertEqual(pairs, [(time(8, 0), time(12, 0)), (time(13, 0), time(15, 0)), (time(16, 0), time(17, 0))])
