from django.apps import AppConfig


class PlanningConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "apps.planning"
    verbose_name = "Planejamento MRP"

    def ready(self):
        from . import signals  # noqa: F401
