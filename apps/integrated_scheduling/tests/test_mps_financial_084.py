from datetime import date
from decimal import Decimal
from django.test import TestCase

from apps.common.models import Plant
from apps.costing.models import CostVersion, ItemCost
from apps.masterdata.models import Item
from apps.integrated_scheduling.mps_financial_whatif import resolve_cost_version, money

class MPSFinancialWhatIf084Tests(TestCase):
    def setUp(self):
        self.plant=Plant.objects.create(code='P084',name='Plant 084')
        self.item=Item.objects.create(code='I084',description='Item 084',item_type=Item.ItemType.MANUFACTURED,standard_cost=Decimal('10'))

    def test_active_cost_version_is_preferred(self):
        CostVersion.objects.create(plant=self.plant,code='OLD',effective_from=date(2026,1,1),status=CostVersion.Status.CALCULATED)
        active=CostVersion.objects.create(plant=self.plant,code='ACTIVE084',effective_from=date(2026,7,1),status=CostVersion.Status.ACTIVE)
        ItemCost.objects.create(cost_version=active,item=self.item,material_cost=4,labor_cost=2,machine_cost=1,overhead_cost=1,total_cost=8)
        got,source=resolve_cost_version(self.plant,date(2026,8,10))
        self.assertEqual(got.pk,active.pk)
        self.assertEqual(source,'ACTIVE')

    def test_money_rounding(self):
        self.assertEqual(money(Decimal('12.345')),Decimal('12.35'))
