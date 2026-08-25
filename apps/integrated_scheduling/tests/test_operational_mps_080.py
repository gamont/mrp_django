from datetime import date
from django.test import TestCase
from apps.common.models import Plant
from apps.masterdata.models import Item
from apps.integrated_scheduling.models import SAndOPCycle, SAndOPSupplyPlanLine, MPSOperationalPolicy
from apps.integrated_scheduling.sop_mps import build_operational_mps

class OperationalMPS080Tests(TestCase):
    def setUp(self):
        self.plant=Plant.objects.create(code='SP01',name='São Paulo')
        self.item=Item.objects.create(code='FG-A',description='Produto A',item_type='FINISHED')
        self.cycle=SAndOPCycle.objects.create(plant=self.plant,code='SOP-2026-08',version=1,cycle_month=date(2026,8,1),horizon_start=date(2026,8,1),horizon_end=date(2026,8,31),status=SAndOPCycle.Status.APPROVED)
        SAndOPSupplyPlanLine.objects.create(cycle=self.cycle,item=self.item,bucket_date=date(2026,8,1),demand_quantity=100,capacity_constrained_quantity=100)
        MPSOperationalPolicy.objects.create(plant=self.plant,demand_time_fence_days=7,planning_time_fence_days=21,require_rccp_clear=False)
    def test_month_is_split_into_weekly_buckets_and_preserves_total(self):
        pub=build_operational_mps(self.cycle,as_of_date=date(2026,8,1))
        self.assertGreater(pub.weekly_buckets.count(),1)
        total=sum(x.quantity for x in pub.weekly_buckets.all())
        self.assertEqual(total,100)
        self.assertIn('FROZEN',set(pub.weekly_buckets.values_list('mps_status',flat=True)))
