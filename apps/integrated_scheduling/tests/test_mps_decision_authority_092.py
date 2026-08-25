from decimal import Decimal
from django.test import SimpleTestCase
from apps.integrated_scheduling.mps_decision_authority import LEVEL_RANK,_d
class Authority092Tests(SimpleTestCase):
    def test_level_order(self): self.assertGreater(LEVEL_RANK['EXECUTIVE_COMMITTEE'],LEVEL_RANK['DIRECTOR']); self.assertGreater(LEVEL_RANK['DIRECTOR'],LEVEL_RANK['MANAGER'])
    def test_decimal_normalization(self): self.assertEqual(_d('1250.50'),Decimal('1250.50')); self.assertEqual(_d(None),Decimal('0'))
