from decimal import Decimal
from django.test import SimpleTestCase
from apps.integrated_scheduling.financing_whatif import _period_days

class Financing087Tests(SimpleTestCase):
    def test_period_days_defaults_to_30(self):
        from datetime import date
        self.assertEqual(_period_days(date(2026,8,1),None),30)
    def test_period_days_uses_bucket_gap(self):
        from datetime import date
        self.assertEqual(_period_days(date(2026,8,1),date(2026,8,8)),7)
