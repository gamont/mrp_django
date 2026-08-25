from datetime import timedelta
from django.core.management.base import BaseCommand, CommandError
from django.utils import timezone

from apps.common.models import Plant
from apps.integrated_scheduling.models import IntegratedScheduleScenario
from apps.integrated_scheduling.advanced import run_finite_scenario


class Command(BaseCommand):
    help = "Simula programação finita 0.6.3 com regra de despacho e setup dependente da sequência."

    def add_arguments(self, parser):
        parser.add_argument("--plant", required=True)
        parser.add_argument("--days", type=int, default=14)
        parser.add_argument("--name", default="Sequenciamento 0.6.3")
        parser.add_argument("--rule", choices=["EDD", "SPT", "CR", "PRIORITY", "SETUP_MIN"], default="EDD")
        parser.add_argument("--direction", choices=["FORWARD", "BACKWARD"], default="FORWARD")
        parser.add_argument("--campaign", action="store_true")
        parser.add_argument("--ignore-setup", action="store_true")

    def handle(self, *args, **opts):
        plant = Plant.objects.filter(code=opts["plant"]).first()
        if not plant:
            raise CommandError("Planta não encontrada.")
        start = timezone.localdate()
        scenario = IntegratedScheduleScenario.objects.create(
            name=opts["name"], plant=plant, horizon_start=start,
            horizon_end=start + timedelta(days=max(1, opts["days"]) - 1),
            scheduling_direction=opts["direction"], dispatch_rule=opts["rule"],
            campaign_mode=opts["campaign"], minimize_setups=not opts["ignore_setup"],
            finite_by_machine=True, allow_alternate_resources=True, respect_industrial_calendar=True,
        )
        run_finite_scenario(scenario=scenario)
        scenario.refresh_from_db()
        m = scenario.simulated_summary or {}
        self.stdout.write(self.style.SUCCESS(
            f"Cenário {scenario.pk}: regra={scenario.dispatch_rule} "
            f"setup={m.get('sequence_setup_hours', '0')}h conflitos={m.get('conflicts', 0)} "
            f"atraso={m.get('late_hours', '0')}h"
        ))
