from django.core.management.base import BaseCommand

from apps.common.roles import sync_default_roles


class Command(BaseCommand):
    help = "Cria ou sincroniza os grupos e permissões padrão do sistema MRP."

    def handle(self, *args, **options):
        result = sync_default_roles()
        for role, count in result.items():
            self.stdout.write(self.style.SUCCESS(f"{role}: {count} permissões"))
