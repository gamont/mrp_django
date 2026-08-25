from datetime import date, datetime, timedelta
from decimal import Decimal
from django.test import TestCase
from django.utils import timezone
from apps.common.models import Plant
from apps.masterdata.models import Item, WorkCenter
from apps.production.models import WorkOrder, WorkOrderOperation
from apps.shopfloor.models import Machine
from apps.maintenance.models import MaintenanceAsset, MaintenanceWorkOrder
from apps.integrated_scheduling.models import IntegratedScheduleScenario, IntegratedScheduleConflict
from apps.integrated_scheduling.services import run_integrated_scenario

class IntegratedScheduleTest(TestCase):
    def test_maintenance_pushes_production_and_detects_conflict(self):
        plant = Plant.objects.create(code="SP01", name="SP")
        item = Item.objects.create(code="FG-1", description="Produto", item_type="FINISHED", uom="UN")
        wc = WorkCenter.objects.create(plant=plant, code="MONT", name="Montagem", capacity_hours_per_day=Decimal("8"), efficiency_percent=Decimal("100"))
        machine = Machine.objects.create(plant=plant, work_center=wc, code="M1", name="M1")
        asset = MaintenanceAsset.objects.create(plant=plant, machine=machine, code="A1", name="A1")
        wo = WorkOrder.objects.create(number="OP1", plant=plant, item=item, quantity=10, release_date=date.today(), due_date=date.today()+timedelta(days=2))
        start = timezone.make_aware(datetime.combine(date.today(), datetime.min.time())) + timedelta(hours=8)
        op = WorkOrderOperation.objects.create(work_order=wo, sequence=10, description="Montar", work_center=wc, planned_start=start, planned_end=start+timedelta(hours=4))
        MaintenanceWorkOrder.objects.create(plant=plant, number="OM1", asset=asset, title="Preventiva", scheduled_start=start+timedelta(hours=1), scheduled_end=start+timedelta(hours=3))
        scenario = IntegratedScheduleScenario.objects.create(name="Teste", plant=plant, horizon_start=date.today(), horizon_end=date.today()+timedelta(days=3))
        run_integrated_scenario(scenario=scenario)
        block = scenario.blocks.get(source_type="WORK_ORDER_OPERATION", source_id=str(op.pk))
        self.assertGreater(block.simulated_start, block.original_start)
        self.assertTrue(scenario.conflicts.filter(conflict_type=IntegratedScheduleConflict.ConflictType.MAINTENANCE_PRODUCTION).exists())
