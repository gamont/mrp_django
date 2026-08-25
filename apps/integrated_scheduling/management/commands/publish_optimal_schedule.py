from django.core.management.base import BaseCommand, CommandError
from apps.integrated_scheduling.models import ScheduleSolverRun
from apps.integrated_scheduling.execution import publish_solver_run
class Command(BaseCommand):
    help = "Publica uma execução CP-SAT como cronograma oficial versionado."
    def add_arguments(self, p):
        p.add_argument("--run", type=int, required=True); p.add_argument("--frozen-hours", type=int, default=24); p.add_argument("--notes", default="")
    def handle(self, *args, **o):
        run=ScheduleSolverRun.objects.filter(pk=o["run"]).first()
        if not run: raise CommandError("Solver run não encontrado.")
        pub=publish_solver_run(run=run, frozen_hours=o["frozen_hours"], notes=o["notes"])
        self.stdout.write(self.style.SUCCESS(f"Publicado {pub.plant.code} v{pub.version}: {pub.slots.count()} slots."))
