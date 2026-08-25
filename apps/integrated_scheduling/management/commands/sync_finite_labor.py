from django.core.management.base import BaseCommand, CommandError

from apps.common.models import Plant
from apps.maintenance.models import TechnicianProfile
from apps.shopfloor.models import OperatorProfile
from apps.integrated_scheduling.models import LaborResource


class Command(BaseCommand):
    help = "Sincroniza operadores e técnicos existentes com os recursos de mão de obra finita. Turnos e skills são cadastrados separadamente."

    def add_arguments(self, parser):
        parser.add_argument("--plant", required=True)

    def handle(self, *args, **opts):
        plant = Plant.objects.filter(code=opts["plant"]).first()
        if not plant:
            raise CommandError("Planta não encontrada.")
        created = updated = 0
        for profile in OperatorProfile.objects.filter(is_active=True).select_related("user"):
            code = f"OP-{profile.badge_code}"
            obj, was_created = LaborResource.objects.update_or_create(
                plant=plant,
                employee_code=code,
                defaults={
                    "name": profile.user.get_full_name() or profile.user.get_username(),
                    "resource_type": LaborResource.ResourceType.OPERATOR,
                    "operator_profile": profile,
                    "user": profile.user,
                    "is_active": True,
                },
            )
            created += int(was_created); updated += int(not was_created)
        for profile in TechnicianProfile.objects.filter(plant=plant, is_active=True).select_related("user"):
            obj, was_created = LaborResource.objects.update_or_create(
                plant=plant,
                employee_code=profile.employee_code,
                defaults={
                    "name": profile.user.get_full_name() or profile.user.get_username(),
                    "resource_type": LaborResource.ResourceType.TECHNICIAN,
                    "technician_profile": profile,
                    "user": profile.user,
                    "is_active": True,
                },
            )
            created += int(was_created); updated += int(not was_created)
        self.stdout.write(self.style.SUCCESS(f"Recursos sincronizados: criados={created}, atualizados={updated}. Cadastre skills e turnos antes de ativar o solver de mão de obra."))
