from decimal import Decimal
from django.test import SimpleTestCase
from apps.integrated_scheduling.optimizer import _weights

class OptimizerWeightsTests(SimpleTestCase):
    def test_weights_are_normalized(self):
        w = _weights({"lateness": 3, "setup": 2, "overtime": 1, "priority_tardiness": 1, "utilization_imbalance": 1, "conflicts": 2})
        self.assertEqual(sum(w.values()), Decimal("1"))
        self.assertEqual(w["lateness"], Decimal("0.3"))

    def test_default_weights_sum_to_one(self):
        self.assertEqual(sum(_weights({}).values()), Decimal("1"))
