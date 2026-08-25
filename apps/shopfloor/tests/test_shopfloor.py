from decimal import Decimal
from django.contrib.auth.models import Group, User
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from apps.common.models import Plant
from apps.masterdata.models import Item, WorkCenter
from apps.production.models import WorkOrder, WorkOrderOperation
from apps.shopfloor.models import DowntimeReason, Machine, OperatorProfile, TerminalStation
from apps.shopfloor.services import authenticate_operator, dispatch_next, end_downtime, start_downtime


class ShopfloorFlowTests(TestCase):
    def setUp(self):
        self.plant = Plant.objects.create(code="SP01", name="São Paulo")
        self.item = Item.objects.create(code="PA-1", description="Produto acabado", item_type="MANUFACTURED")
        self.wc = WorkCenter.objects.create(plant=self.plant, code="MONT", name="Montagem")
        self.wo = WorkOrder.objects.create(number="OP-001", plant=self.plant, item=self.item, quantity=10, release_date=timezone.localdate(), due_date=timezone.localdate(), status=WorkOrder.Status.RELEASED)
        self.op = WorkOrderOperation.objects.create(work_order=self.wo, sequence=10, description="Montar", work_center=self.wc, status=WorkOrderOperation.Status.READY)
        self.machine = Machine.objects.create(plant=self.plant, work_center=self.wc, code="MONT-01", name="Montadora")
        self.station = TerminalStation.objects.create(plant=self.plant, code="T-MONT", name="Terminal Montagem", work_center=self.wc, machine=self.machine)
        self.reason = DowntimeReason.objects.create(plant=self.plant, code="FALHA", description="Falha")
        self.user = User.objects.create_user(username="operador", password="unused")
        profile = OperatorProfile(user=self.user, badge_code="1001", pin_hash="")
        profile.set_pin("1234")
        profile.save()
        self.profile = profile

    def test_badge_pin_authentication(self):
        self.assertEqual(authenticate_operator(badge_code="1001", pin="1234").pk, self.profile.pk)

    def test_dispatch_and_downtime(self):
        op = dispatch_next(station=self.station, actor=self.user)
        self.machine.refresh_from_db()
        self.assertEqual(op.pk, self.op.pk)
        self.assertEqual(self.machine.current_operation_id, self.op.pk)
        event = start_downtime(machine=self.machine, reason=self.reason, actor=self.user)
        self.machine.refresh_from_db()
        self.assertEqual(self.machine.status, Machine.Status.DOWN)
        self.assertIsNone(event.ended_at)
        end_downtime(machine=self.machine, actor=self.user)
        event.refresh_from_db()
        self.assertIsNotNone(event.ended_at)

    def test_login_screen(self):
        response = self.client.post(reverse("shopfloor:login"), {"badge_code": "1001", "pin": "1234"})
        self.assertEqual(response.status_code, 302)


class OEEMonitoringTests(TestCase):
    def setUp(self):
        from apps.production.models import ProductionReport
        from apps.shopfloor.models import MachineProductionRecord

        self.plant = Plant.objects.create(code="RJ01", name="Rio")
        self.item = Item.objects.create(code="PA-OEE", description="Produto OEE", item_type="MANUFACTURED")
        self.wc = WorkCenter.objects.create(plant=self.plant, code="LINHA", name="Linha")
        self.machine = Machine.objects.create(
            plant=self.plant,
            work_center=self.wc,
            code="LINHA-01",
            name="Linha 1",
            planned_minutes_per_day=Decimal("480"),
            ideal_cycle_seconds=Decimal("60"),
        )
        self.wo = WorkOrder.objects.create(
            number="OP-OEE-1",
            plant=self.plant,
            item=self.item,
            quantity=100,
            release_date=timezone.localdate(),
            due_date=timezone.localdate(),
            status=WorkOrder.Status.IN_PROGRESS,
        )
        self.op = WorkOrderOperation.objects.create(
            work_order=self.wo,
            sequence=10,
            description="Produzir",
            work_center=self.wc,
            status=WorkOrderOperation.Status.COMPLETED,
        )
        now = timezone.now()
        self.report = ProductionReport.objects.create(
            work_order=self.wo,
            operation=self.op,
            reported_at=now,
            good_quantity=Decimal("90"),
            scrap_quantity=Decimal("10"),
            labor_hours=Decimal("1"),
            machine_hours=Decimal("1"),
        )
        MachineProductionRecord.objects.create(machine=self.machine, report=self.report, operation=self.op, reported_at=now)

    def test_oee_snapshot(self):
        from apps.shopfloor.oee import calculate_machine_oee

        snapshot = calculate_machine_oee(machine=self.machine, metric_date=timezone.localdate())
        self.assertEqual(snapshot.good_quantity, 90)
        self.assertEqual(snapshot.scrap_quantity, 10)
        self.assertEqual(snapshot.quality, Decimal("0.9000"))
        self.assertGreater(snapshot.oee, 0)

    def test_unplanned_downtime_updates_mttr(self):
        from datetime import timedelta
        from apps.shopfloor.oee import calculate_machine_oee

        reason = DowntimeReason.objects.create(
            plant=self.plant,
            code="BREAK",
            description="Quebra",
            category=DowntimeReason.Category.UNPLANNED,
        )
        now = timezone.now()
        self.machine.downtime_events.create(
            reason=reason,
            started_at=now - timedelta(minutes=30),
            ended_at=now,
        )
        snapshot = calculate_machine_oee(machine=self.machine, metric_date=timezone.localdate())
        self.assertEqual(snapshot.failures, 1)
        self.assertGreaterEqual(snapshot.mttr_minutes, Decimal("29.00"))


class OEEShiftAndTargetsTests(TestCase):
    def setUp(self):
        from datetime import time
        from apps.masterdata.models import WorkCenterShift
        from apps.production.models import ProductionReport
        from apps.shopfloor.models import MachineProductionRecord, OEETarget

        self.plant = Plant.objects.create(code="MG01", name="Minas")
        self.item = Item.objects.create(code="PA-SHIFT", description="Produto turno", item_type="MANUFACTURED")
        self.wc = WorkCenter.objects.create(plant=self.plant, code="LIN2", name="Linha 2")
        self.machine = Machine.objects.create(
            plant=self.plant,
            work_center=self.wc,
            code="LIN2-01",
            name="Linha 2 / 01",
            planned_minutes_per_day=Decimal("480"),
            ideal_cycle_seconds=Decimal("60"),
        )
        self.shift = WorkCenterShift.objects.create(
            work_center=self.wc,
            name="Integral",
            weekday=timezone.localdate().weekday(),
            start_time=time(0, 0),
            end_time=time(23, 59),
            capacity_hours=Decimal("8"),
            efficiency_percent=Decimal("100"),
        )
        self.wo = WorkOrder.objects.create(
            number="OP-SHIFT",
            plant=self.plant,
            item=self.item,
            quantity=100,
            release_date=timezone.localdate(),
            due_date=timezone.localdate(),
            status=WorkOrder.Status.IN_PROGRESS,
        )
        self.op = WorkOrderOperation.objects.create(
            work_order=self.wo,
            sequence=10,
            description="Produzir",
            work_center=self.wc,
            status=WorkOrderOperation.Status.COMPLETED,
        )
        report = ProductionReport.objects.create(
            work_order=self.wo,
            operation=self.op,
            reported_at=timezone.now(),
            good_quantity=Decimal("80"),
            scrap_quantity=Decimal("20"),
            labor_hours=Decimal("1"),
            machine_hours=Decimal("1"),
        )
        MachineProductionRecord.objects.create(machine=self.machine, report=report, operation=self.op, reported_at=report.reported_at)
        self.plant_target = OEETarget.objects.create(
            plant=self.plant,
            effective_from=timezone.localdate(),
            oee_target=Decimal("0.8000"),
        )

    def test_shift_snapshot_and_losses(self):
        from apps.shopfloor.oee import calculate_machine_shift_oee

        snapshot = calculate_machine_shift_oee(machine=self.machine, shift=self.shift, metric_date=timezone.localdate())
        self.assertEqual(snapshot.good_quantity, Decimal("80"))
        self.assertEqual(snapshot.scrap_quantity, Decimal("20"))
        self.assertEqual(snapshot.quality, Decimal("0.8000"))
        self.assertGreaterEqual(snapshot.quality_loss_minutes, Decimal("20.00"))

    def test_machine_target_overrides_plant(self):
        from apps.shopfloor.models import OEETarget
        from apps.shopfloor.oee import resolve_oee_target

        target = OEETarget.objects.create(
            plant=self.plant,
            machine=self.machine,
            effective_from=timezone.localdate(),
            oee_target=Decimal("0.9000"),
        )
        resolved = resolve_oee_target(machine=self.machine, metric_date=timezone.localdate())
        self.assertEqual(resolved.pk, target.pk)

    def test_history_screen(self):
        from apps.shopfloor.oee import calculate_machine_oee, calculate_machine_shift_oee

        calculate_machine_oee(machine=self.machine, metric_date=timezone.localdate())
        calculate_machine_shift_oee(machine=self.machine, shift=self.shift, metric_date=timezone.localdate())
        user = User.objects.create_superuser(username="oee-admin", password="x", email="a@example.com")
        self.client.force_login(user)
        response = self.client.get(reverse("shopfloor:oee-history"), {"plant": self.plant.pk})
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Histórico OEE")
        self.assertContains(response, "Integral")
