from django.core.management.base import BaseCommand, CommandError
from apps.costing.models import CostVersion
from apps.costing.services.rollup import run_rollup
class Command(BaseCommand):
    help="Executa o roll-up de custos de uma versão."
    def add_arguments(self,p): p.add_argument("--version",required=True); p.add_argument("--plant",required=True)
    def handle(self,*args,**o):
        try: v=CostVersion.objects.get(code=o["version"],plant__code=o["plant"])
        except CostVersion.DoesNotExist: raise CommandError("Versão de custo não encontrada.")
        r=run_rollup(v); self.stdout.write(self.style.SUCCESS(f"{r.items_calculated} itens calculados"))
