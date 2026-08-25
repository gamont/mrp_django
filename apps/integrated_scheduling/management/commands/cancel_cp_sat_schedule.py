from django.core.management.base import BaseCommand, CommandError
from apps.integrated_scheduling.models import ScheduleSolverRun
from apps.integrated_scheduling.cp_sat_solver import request_solver_cancel


class Command(BaseCommand):
    help = "Solicita cancelamento cooperativo de uma execução CP-SAT em andamento."

    def add_arguments(self, parser):
        parser.add_argument("--run", type=int, required=True)
        parser.add_argument("--reason", default="Cancelado via CLI")

    def handle(self, *args, **opts):
        run = ScheduleSolverRun.objects.filter(pk=opts["run"]).first()
        if not run:
            raise CommandError("Execução não encontrada.")
        if run.status not in {ScheduleSolverRun.Status.DRAFT, ScheduleSolverRun.Status.RUNNING}:
            raise CommandError(f"Execução já terminou com status {run.status}.")
        request_solver_cancel(run, reason=opts["reason"])
        self.stdout.write(self.style.WARNING(f"Cancelamento solicitado para run {run.pk}."))
