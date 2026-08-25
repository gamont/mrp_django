from django.test import TestCase
from apps.planning.models import DemandPeggingAllocation

class DemandPeggingModelTest(TestCase):
    def test_source_type_exists(self):
        self.assertEqual(DemandPeggingAllocation.SourceType.SALES_ORDER_LINE, "SALES_ORDER_LINE")
