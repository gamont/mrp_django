from django.test import SimpleTestCase
from apps.integrated_scheduling.cp_sat_solver import _weight_map, ortools_available


class CpSatSolverUnitTests(SimpleTestCase):
    def test_weight_map_accepts_override(self):
        weights = _weight_map({"tardiness": 250, "setup": 0})
        self.assertEqual(weights["tardiness"], 250)
        self.assertEqual(weights["setup"], 0)

    def test_ortools_availability_is_boolean(self):
        self.assertIsInstance(ortools_available(), bool)
