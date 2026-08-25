from django.test import SimpleTestCase

from apps.integrated_scheduling.cp_sat_preemptive import _split_minutes


class PreemptiveChunkingTests(SimpleTestCase):
    def test_operation_is_split_by_max_consecutive_limit(self):
        self.assertEqual(_split_minutes(600, 240, 5), [240, 240, 120])

    def test_chunking_rounds_to_solver_granularity(self):
        self.assertEqual(_split_minutes(121, 60, 15), [60, 60, 15])

    def test_short_operation_stays_single_segment(self):
        self.assertEqual(_split_minutes(45, 240, 5), [45])
