from decimal import Decimal
from django.test import SimpleTestCase
from apps.integrated_scheduling.mps_optimizer import _score

class DummyPolicy:
    weight_shortage=Decimal('100'); weight_rccp_overload=Decimal('10'); weight_uncovered_financing=Decimal('1')
    weight_interest=Decimal('1'); weight_inventory=Decimal('0.1'); weight_purchase_spend=Decimal('0.1')

class MPSOptimizer088Tests(SimpleTestCase):
    def test_financially_infeasible_candidate_is_heavily_penalized(self):
        base={'shortage_delta_count':'0','rccp_overload_hours':'0','peak_uncovered_financing':'0','interest_cost':'0','inventory_exposure':'0','purchase_spend':'0','financially_feasible':True}
        bad=dict(base,financially_feasible=False)
        self.assertGreater(_score(bad,DummyPolicy()),_score(base,DummyPolicy()))
