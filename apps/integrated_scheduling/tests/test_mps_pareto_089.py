from django.test import SimpleTestCase
from apps.integrated_scheduling.mps_pareto_optimizer import dominates, PARETO_KEYS, ortools_pareto_available
class Pareto089Tests(SimpleTestCase):
    def test_dominance(self):
        a={k:'1' for k in PARETO_KEYS}; b={k:'2' for k in PARETO_KEYS}
        self.assertTrue(dominates(a,b)); self.assertFalse(dominates(b,a))
    def test_equal_vectors_do_not_dominate(self):
        a={k:'1' for k in PARETO_KEYS}; self.assertFalse(dominates(a,a))
    def test_ortools_probe_is_boolean(self):
        self.assertIsInstance(ortools_pareto_available(),bool)
