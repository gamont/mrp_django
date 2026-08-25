from datetime import date
from decimal import Decimal
from django.test import TestCase
from apps.common.models import Plant
from apps.masterdata.models import Item
from apps.integrated_scheduling.models import SAndOPCycle, SAndOPSupplyPlanLine, MPSOperationalPolicy, MPSRevision
from apps.integrated_scheduling.sop_mps import build_operational_mps, run_rccp
from apps.integrated_scheduling.mps_revision import capture_revision, compare_revisions, rollback_to_revision

class MPSRevision082Tests(TestCase):
    def setUp(self):
        self.plant=Plant.objects.create(code='SP82',name='Planta 082')
        self.item=Item.objects.create(code='FG-082',description='Produto 082',item_type='FINISHED')
        self.cycle=SAndOPCycle.objects.create(plant=self.plant,code='SOP-2026-08-082',version=1,cycle_month=date(2026,8,1),horizon_start=date(2026,8,1),horizon_end=date(2026,8,31),status=SAndOPCycle.Status.APPROVED)
        SAndOPSupplyPlanLine.objects.create(cycle=self.cycle,item=self.item,bucket_date=date(2026,8,1),demand_quantity=100,capacity_constrained_quantity=100)
        MPSOperationalPolicy.objects.create(plant=self.plant,demand_time_fence_days=7,planning_time_fence_days=21,require_rccp_clear=False)
        self.pub=build_operational_mps(self.cycle,as_of_date=date(2026,8,1))

    def test_build_creates_approved_baseline_revision(self):
        rev=self.pub.revisions.get(number=1)
        self.assertEqual(rev.kind,MPSRevision.Kind.BASELINE)
        self.assertEqual(rev.status,MPSRevision.Status.APPROVED)
        self.assertEqual(rev.lines.count(),self.pub.weekly_buckets.count())

    def test_diff_and_rollback_restore_quantities(self):
        baseline=self.pub.revisions.get(number=1)
        bucket=self.pub.weekly_buckets.order_by('bucket_start').first()
        original=bucket.quantity
        bucket.quantity=original+Decimal('10'); bucket.save(update_fields=['quantity','updated_at'])
        run_rccp(self.pub)
        changed=capture_revision(self.pub,label='Teste mudança')
        diff=compare_revisions(baseline,changed)
        self.assertEqual(diff['estimated_mrp_impact']['changed_buckets'],1)
        self.assertEqual(diff['estimated_mrp_impact']['net_quantity_delta'],'10.0000')
        rollback_to_revision(self.pub,baseline,reason='teste')
        bucket.refresh_from_db()
        self.assertEqual(bucket.quantity,original)
