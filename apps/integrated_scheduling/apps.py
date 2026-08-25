from django.apps import AppConfig


class IntegratedSchedulingConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "apps.integrated_scheduling"
    verbose_name = "Programação integrada"

    def ready(self):
        from . import signals  # noqa: F401
