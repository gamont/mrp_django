import uuid

from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import models


class TimeStampedModel(models.Model):
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        abstract = True


class Plant(TimeStampedModel):
    code = models.CharField(max_length=20, unique=True)
    name = models.CharField(max_length=120)
    timezone = models.CharField(max_length=50, default="America/Sao_Paulo")
    is_active = models.BooleanField(default=True)

    class Meta:
        ordering = ["code"]

    def __str__(self) -> str:
        return f"{self.code} - {self.name}"


class ShopCalendarDay(TimeStampedModel):
    plant = models.ForeignKey(Plant, on_delete=models.CASCADE, related_name="calendar_days")
    date = models.DateField()
    is_working_day = models.BooleanField(default=True)
    capacity_factor = models.DecimalField(max_digits=6, decimal_places=3, default=1)
    note = models.CharField(max_length=200, blank=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=["plant", "date"], name="uq_calendar_plant_date"),
            models.CheckConstraint(
                condition=models.Q(capacity_factor__gt=0),
                name="ck_calendar_capacity_pos",
            ),
        ]
        ordering = ["date"]

    def __str__(self) -> str:
        return f"{self.plant.code} {self.date}"


class DomainEvent(models.Model):
    """Registro imutável de eventos relevantes do domínio.

    O idempotency_key protege integrações e comandos repetidos. Atualizações e
    exclusões são bloqueadas para manter uma trilha de auditoria append-only.
    """

    event_id = models.UUIDField(default=uuid.uuid4, unique=True, editable=False)
    idempotency_key = models.CharField(max_length=160, unique=True)
    event_type = models.CharField(max_length=80, db_index=True)
    aggregate_type = models.CharField(max_length=80, db_index=True)
    aggregate_id = models.CharField(max_length=80, db_index=True)
    payload = models.JSONField(default=dict, blank=True)
    actor = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="mrp_domain_events",
    )
    occurred_at = models.DateTimeField(auto_now_add=True, db_index=True)

    class Meta:
        ordering = ["-occurred_at", "-id"]
        indexes = [
            models.Index(
                fields=["aggregate_type", "aggregate_id", "occurred_at"],
                name="ix_event_aggregate_time",
            ),
            models.Index(fields=["event_type", "occurred_at"], name="ix_event_type_time"),
        ]

    def save(self, *args, **kwargs):
        if self.pk and type(self).objects.filter(pk=self.pk).exists():
            raise ValidationError("Eventos de domínio são imutáveis.")
        return super().save(*args, **kwargs)

    def delete(self, *args, **kwargs):
        raise ValidationError("Eventos de domínio não podem ser excluídos.")

    def __str__(self) -> str:
        return f"{self.event_type} {self.aggregate_type}/{self.aggregate_id}"
