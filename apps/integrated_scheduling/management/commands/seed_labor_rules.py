from datetime import date
from django.core.management.base import BaseCommand, CommandError
from apps.common.models import Plant
from apps.integrated_scheduling.models import LaborRuleSet

class Command(BaseCommand):
    help="Cria política-base parametrizável de jornada/custos para uma planta."
    def add_arguments(self, parser): parser.add_argument("--plant", required=True)
    def handle(self,*args,**opts):
        plant=Plant.objects.filter(code=opts["plant"]).first()
        if not plant: raise CommandError("Planta não encontrada.")
        obj,created=LaborRuleSet.objects.get_or_create(plant=plant,code="STD",effective_from=date(2026,1,1),defaults={"name":"Política padrão - revisar conforme legislação/convenção"})
        self.stdout.write(self.style.SUCCESS(f"{obj} {'criado' if created else 'já existe'}"))
