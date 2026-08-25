from decimal import Decimal
from django.test import TestCase

from apps.common.models import Plant
from apps.integrated_scheduling.models import IntegratedScheduleScenario, ScheduleSolverRun, ScheduleSolverIncumbent
from apps.integrated_scheduling.cp_sat_solver import request_solver_cancel


class Solver066ModelTests(TestCase):
    def setUp(self):
        self.plant = Plant.objects.create(code="T01", name="Teste")
        self.scenario = IntegratedScheduleScenario.objects.create(
            name="Cenário 066", plant=self.plant,
            horizon_start="2026-08-10", horizon_end="2026-08-12",
        )

    def test_solver_run_supports_gap_warm_start_and_async(self):
        run = ScheduleSolverRun.objects.create(
            scenario=self.scenario, execution_mode="ASYNC", relative_gap_limit=Decimal("0.020000"),
            warm_start_enabled=True,
        )
        self.assertEqual(run.execution_mode, "ASYNC")
        self.assertEqual(run.relative_gap_limit, Decimal("0.020000"))
        self.assertTrue(run.warm_start_enabled)

    def test_cancel_request_is_persisted(self):
        run = ScheduleSolverRun.objects.create(scenario=self.scenario, status=ScheduleSolverRun.Status.RUNNING)
        request_solver_cancel(run, reason="teste")
        self.assertIsNotNone(run.cancel_requested_at)
        self.assertEqual(run.cancellation_reason, "teste")

    def test_incumbents_are_ordered(self):
        run = ScheduleSolverRun.objects.create(scenario=self.scenario)
        ScheduleSolverIncumbent.objects.create(run=run, sequence=2, objective_value=90)
        ScheduleSolverIncumbent.objects.create(run=run, sequence=1, objective_value=100)
        self.assertEqual(list(run.incumbents.values_list("sequence", flat=True)), [1, 2])
