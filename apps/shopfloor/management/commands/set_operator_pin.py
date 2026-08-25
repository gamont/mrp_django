from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand, CommandError

from apps.shopfloor.models import OperatorProfile


class Command(BaseCommand):
    help = "Cria/atualiza crachá e PIN de um operador do terminal."

    def add_arguments(self, parser):
        parser.add_argument("--username", required=True)
        parser.add_argument("--badge", required=True)
        parser.add_argument("--pin", required=True)

    def handle(self, *args, **options):
        if len(options["pin"]) < 4:
            raise CommandError("O PIN deve possuir pelo menos 4 caracteres.")
        User = get_user_model()
        try:
            user = User.objects.get(username=options["username"])
        except User.DoesNotExist as exc:
            raise CommandError("Usuário não encontrado.") from exc
        profile, _ = OperatorProfile.objects.get_or_create(user=user, defaults={"badge_code": options["badge"], "pin_hash": ""})
        profile.badge_code = options["badge"]
        profile.set_pin(options["pin"])
        profile.is_active = True
        profile.failed_attempts = 0
        profile.locked_until = None
        profile.save()
        self.stdout.write(self.style.SUCCESS(f"Operador {user.username} configurado com crachá {profile.badge_code}."))
