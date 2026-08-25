from datetime import date
from decimal import Decimal
from django.test import TestCase
from apps.common.models import Plant
from apps.masterdata.models import Item
from apps.integrated_scheduling.models import OperationalMPSPublication, MPSOperationalPolicy, MPSRevision, MPSRevisionLine, SAndOPCycle
from apps.integrated_scheduling.mps_whatif import create_simulation

class MPSWhatIf083Tests(TestCase):
    def test_create_simulation_uses_baseline(self):
        plant=Plant.objects.create(code='SP01',name='SP')
        policy=MPSOperationalPolicy.objects.create(plant=plant)
        cycle=SAndOPCycle.objects.create(plant=plant,code='SOP-2026-08',version=1,cycle_month=date(2026,8,1),horizon_start=date(2026,8,1),horizon_end=date(2026,8,31))
        pub=OperationalMPSPublication.objects.create(cycle=cycle,policy=policy,as_of_date=date(2026,8,1),horizon_start=date(2026,8,1),horizon_end=date(2026,8,31),source='TEST')
        base=MPSRevision.objects.create(publication=pub,number=1,kind='BASELINE',status='APPROVED')
        target=MPSRevision.objects.create(publication=pub,number=2,parent=base,kind='WORKING',status='DRAFT')
        sim=create_simulation(target)
        self.assertEqual(sim.compare_revision_id,base.id)
        self.assertEqual(sim.revision_id,target.id)
