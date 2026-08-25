from datetime import date
from decimal import Decimal
from django.test import TestCase
from apps.common.models import Plant
from apps.masterdata.models import Item
from apps.demand.models import Forecast, SalesOrder, SalesOrderLine, MasterProductionSchedule
from apps.integrated_scheduling.models import SAndOPCycle, SAndOPConstraint
from apps.integrated_scheduling.sop_cycle import create_sop_cycle, build_supply_review, advance_cycle, approve_cycle, publish_cycle_to_mps

class SAndOPCycle079Tests(TestCase):
    def setUp(self):
        self.plant=Plant.objects.create(code='SP01',name='SP')
        self.item=Item.objects.create(code='FG-1',description='Produto',item_type='FINISHED',uom='EA')
        Forecast.objects.create(plant=self.plant,item=self.item,period_start=date(2026,8,1),period_end=date(2026,8,31),quantity=Decimal('100'),status='APPROVED')
        so=SalesOrder.objects.create(number='SO-1',plant=self.plant,customer_code='C1',customer_name='Cliente',order_date=date(2026,7,1),requested_date=date(2026,8,15),status='CONFIRMED')
        SalesOrderLine.objects.create(sales_order=so,line_number=10,item=self.item,quantity=Decimal('120'),requested_date=date(2026,8,15))
    def test_cycle_versions_and_consensus(self):
        c1=create_sop_cycle(self.plant,date(2026,8,1),date(2026,10,31))
        c2=create_sop_cycle(self.plant,date(2026,8,1),date(2026,10,31))
        self.assertEqual(c1.version,1); self.assertEqual(c2.version,2)
        line=c1.demand_lines.get(item=self.item)
        self.assertEqual(line.consensus_quantity,Decimal('120.0000'))
    def test_critical_constraint_blocks_approval(self):
        c=create_sop_cycle(self.plant,date(2026,8,1),date(2026,10,31)); build_supply_review(c); advance_cycle(c); advance_cycle(c)
        SAndOPConstraint.objects.create(cycle=c,category='CAPACITY',severity='CRITICAL',title='Gargalo')
        with self.assertRaises(ValueError): approve_cycle(c)
    def test_publish_creates_mps_and_planning_run(self):
        c=create_sop_cycle(self.plant,date(2026,8,1),date(2026,10,31)); build_supply_review(c); advance_cycle(c); advance_cycle(c); approve_cycle(c)
        pub=publish_cycle_to_mps(c)
        self.assertGreater(pub.mps_lines,0)
        self.assertIsNotNone(pub.planning_run_id)
        self.assertTrue(MasterProductionSchedule.objects.filter(source=f'SOP:{c.code}:v{c.version}').exists())
