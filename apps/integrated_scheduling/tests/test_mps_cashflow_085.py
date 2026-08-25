from datetime import date
from decimal import Decimal
from django.test import TestCase
from apps.integrated_scheduling.mps_cashflow_whatif import _bucket_date
from apps.integrated_scheduling.models import MPSFinancialBudget

class MPSCashFlow085Tests(TestCase):
    def test_month_bucket(self):
        self.assertEqual(_bucket_date(date(2026,8,19),MPSFinancialBudget.BucketType.MONTHLY),date(2026,8,1))
    def test_week_bucket_is_monday(self):
        self.assertEqual(_bucket_date(date(2026,8,19),MPSFinancialBudget.BucketType.WEEKLY),date(2026,8,17))
