from __future__ import annotations

from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import models

from apps.common.models import Plant, TimeStampedModel
from apps.masterdata.models import Item, Supplier
from apps.traceability.models import InventoryLot, SerialNumber


class InspectionPlan(TimeStampedModel):
    class SourceType(models.TextChoices):
        RECEIPT = "RECEIPT", "Recebimento"
        PRODUCTION = "PRODUCTION", "Produção"
        STOCK = "STOCK", "Estoque"

    code = models.CharField(max_length=40, unique=True)
    description = models.CharField(max_length=200)
    item = models.ForeignKey(Item, on_delete=models.PROTECT, related_name="inspection_plans")
    source_type = models.CharField(max_length=20, choices=SourceType.choices)
    revision = models.CharField(max_length=20, default="A")
    effective_from = models.DateField()
    effective_to = models.DateField(null=True, blank=True)
    sample_size = models.PositiveIntegerField(default=1)
    is_active = models.BooleanField(default=True)

    class Meta:
        ordering = ["item__code", "code", "revision"]
        constraints = [
            models.CheckConstraint(condition=models.Q(sample_size__gt=0), name="ck_qplan_sample_pos"),
            models.CheckConstraint(condition=models.Q(effective_to__isnull=True) | models.Q(effective_to__gte=models.F("effective_from")), name="ck_qplan_dates"),
        ]
        indexes = [models.Index(fields=["item", "source_type", "is_active"], name="ix_qplan_item_source")]

    def __str__(self):
        return f"{self.code} rev. {self.revision}"


class InspectionCharacteristic(TimeStampedModel):
    class DataType(models.TextChoices):
        NUMERIC = "NUMERIC", "Numérico"
        BOOLEAN = "BOOLEAN", "Conforme/não conforme"
        TEXT = "TEXT", "Texto"

    plan = models.ForeignKey(InspectionPlan, on_delete=models.CASCADE, related_name="characteristics")
    sequence = models.PositiveIntegerField()
    name = models.CharField(max_length=120)
    data_type = models.CharField(max_length=15, choices=DataType.choices)
    unit = models.CharField(max_length=20, blank=True)
    lower_limit = models.DecimalField(max_digits=18, decimal_places=6, null=True, blank=True)
    target_value = models.DecimalField(max_digits=18, decimal_places=6, null=True, blank=True)
    upper_limit = models.DecimalField(max_digits=18, decimal_places=6, null=True, blank=True)
    is_mandatory = models.BooleanField(default=True)

    class Meta:
        ordering = ["plan", "sequence"]
        constraints = [
            models.UniqueConstraint(fields=["plan", "sequence"], name="uq_qchar_plan_seq"),
            models.CheckConstraint(condition=models.Q(lower_limit__isnull=True) | models.Q(upper_limit__isnull=True) | models.Q(lower_limit__lte=models.F("upper_limit")), name="ck_qchar_limits"),
        ]


class InspectionOrder(TimeStampedModel):
    class Status(models.TextChoices):
        OPEN = "OPEN", "Aberta"
        IN_PROGRESS = "IN_PROGRESS", "Em inspeção"
        APPROVED = "APPROVED", "Aprovada"
        PARTIAL = "PARTIAL", "Aprovada parcialmente"
        REJECTED = "REJECTED", "Rejeitada"
        CANCELLED = "CANCELLED", "Cancelada"

    plant = models.ForeignKey(Plant, on_delete=models.PROTECT, related_name="inspection_orders")
    plan = models.ForeignKey(InspectionPlan, on_delete=models.PROTECT, related_name="orders")
    item = models.ForeignKey(Item, on_delete=models.PROTECT, related_name="inspection_orders")
    lot = models.ForeignKey(InventoryLot, null=True, blank=True, on_delete=models.PROTECT, related_name="inspection_orders")
    serial = models.ForeignKey(SerialNumber, null=True, blank=True, on_delete=models.PROTECT, related_name="inspection_orders")
    supplier = models.ForeignKey(Supplier, null=True, blank=True, on_delete=models.PROTECT, related_name="inspection_orders")
    source_type = models.CharField(max_length=40)
    source_id = models.CharField(max_length=64)
    quantity_received = models.DecimalField(max_digits=18, decimal_places=4)
    quantity_inspected = models.DecimalField(max_digits=18, decimal_places=4, default=0)
    quantity_approved = models.DecimalField(max_digits=18, decimal_places=4, default=0)
    quantity_rejected = models.DecimalField(max_digits=18, decimal_places=4, default=0)
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.OPEN)
    opened_at = models.DateTimeField(auto_now_add=True)
    completed_at = models.DateTimeField(null=True, blank=True)
    inspector = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL, related_name="quality_inspections")
    notes = models.TextField(blank=True)

    class Meta:
        ordering = ["-opened_at", "-id"]
        constraints = [
            models.CheckConstraint(condition=models.Q(quantity_received__gt=0), name="ck_qorder_received_pos"),
            models.CheckConstraint(condition=models.Q(quantity_inspected__gte=0), name="ck_qorder_inspected_nonneg"),
            models.CheckConstraint(condition=models.Q(quantity_approved__gte=0), name="ck_qorder_approved_nonneg"),
            models.CheckConstraint(condition=models.Q(quantity_rejected__gte=0), name="ck_qorder_rejected_nonneg"),
            models.UniqueConstraint(fields=["source_type", "source_id", "plan"], name="uq_qorder_source_plan"),
        ]
        indexes = [
            models.Index(fields=["plant", "status", "opened_at"], name="ix_qorder_plant_status"),
            models.Index(fields=["item", "status"], name="ix_qorder_item_status"),
        ]

    def clean(self):
        if self.lot_id and self.lot.item_id != self.item_id:
            raise ValidationError({"lot": "O lote deve pertencer ao item da inspeção."})
        if self.serial_id and self.serial.item_id != self.item_id:
            raise ValidationError({"serial": "A série deve pertencer ao item da inspeção."})


class InspectionResult(TimeStampedModel):
    order = models.ForeignKey(InspectionOrder, on_delete=models.CASCADE, related_name="results")
    characteristic = models.ForeignKey(InspectionCharacteristic, on_delete=models.PROTECT, related_name="results")
    sample_number = models.PositiveIntegerField(default=1)
    numeric_value = models.DecimalField(max_digits=18, decimal_places=6, null=True, blank=True)
    boolean_value = models.BooleanField(null=True, blank=True)
    text_value = models.TextField(blank=True)
    is_conforming = models.BooleanField()
    measured_at = models.DateTimeField(auto_now_add=True)
    measured_by = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL)
    notes = models.TextField(blank=True)

    class Meta:
        ordering = ["order", "characteristic__sequence", "sample_number"]
        constraints = [models.UniqueConstraint(fields=["order", "characteristic", "sample_number"], name="uq_qresult_order_char_sample")]


class NonConformance(TimeStampedModel):
    class Status(models.TextChoices):
        OPEN = "OPEN", "Aberta"
        UNDER_REVIEW = "UNDER_REVIEW", "Em análise"
        DISPOSITIONED = "DISPOSITIONED", "Com disposição"
        CLOSED = "CLOSED", "Encerrada"

    class Severity(models.TextChoices):
        MINOR = "MINOR", "Menor"
        MAJOR = "MAJOR", "Maior"
        CRITICAL = "CRITICAL", "Crítica"

    number = models.CharField(max_length=30, unique=True)
    inspection_order = models.ForeignKey(InspectionOrder, null=True, blank=True, on_delete=models.PROTECT, related_name="nonconformances")
    plant = models.ForeignKey(Plant, on_delete=models.PROTECT, related_name="nonconformances")
    item = models.ForeignKey(Item, on_delete=models.PROTECT, related_name="nonconformances")
    lot = models.ForeignKey(InventoryLot, null=True, blank=True, on_delete=models.PROTECT, related_name="nonconformances")
    serial = models.ForeignKey(SerialNumber, null=True, blank=True, on_delete=models.PROTECT, related_name="nonconformances")
    supplier = models.ForeignKey(Supplier, null=True, blank=True, on_delete=models.PROTECT, related_name="nonconformances")
    severity = models.CharField(max_length=10, choices=Severity.choices, default=Severity.MAJOR)
    description = models.TextField()
    quantity_affected = models.DecimalField(max_digits=18, decimal_places=4)
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.OPEN)
    opened_by = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL, related_name="opened_nonconformances")
    closed_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ["-created_at"]
        constraints = [models.CheckConstraint(condition=models.Q(quantity_affected__gt=0), name="ck_ncr_qty_pos")]
        indexes = [models.Index(fields=["plant", "status", "severity"], name="ix_ncr_status_severity")]


class Disposition(TimeStampedModel):
    class Decision(models.TextChoices):
        USE_AS_IS = "USE_AS_IS", "Usar como está"
        REWORK = "REWORK", "Retrabalho"
        RETURN = "RETURN", "Devolver ao fornecedor"
        SCRAP = "SCRAP", "Refugar"
        SORT = "SORT", "Selecionar"

    nonconformance = models.ForeignKey(NonConformance, on_delete=models.CASCADE, related_name="dispositions")
    decision = models.CharField(max_length=20, choices=Decision.choices)
    quantity = models.DecimalField(max_digits=18, decimal_places=4)
    instructions = models.TextField(blank=True)
    approved_by = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL)
    decided_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["nonconformance", "decided_at"]
        constraints = [models.CheckConstraint(condition=models.Q(quantity__gt=0), name="ck_disposition_qty_pos")]
