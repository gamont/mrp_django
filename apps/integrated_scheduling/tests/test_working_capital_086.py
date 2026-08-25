from decimal import Decimal
from django.test import SimpleTestCase
from apps.integrated_scheduling.working_capital_whatif import _schedule
class WorkingCapital086Tests(SimpleTestCase):
    def test_installment_schedule_normalizes(self):
        s=_schedule([{'days':30,'percent':25},{'days':60,'percent':75}],30)
        self.assertEqual(sum(p for _,p in s),Decimal('100'))
        self.assertEqual(s[1][0],60)
    def test_empty_schedule_uses_fallback(self):
        self.assertEqual(_schedule([],45),[(45,Decimal('100'))])
