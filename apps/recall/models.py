from __future__ import annotations

from django.conf import settings
from django.db import models

from apps.common.models import Plant, TimeStampedModel
from apps.masterdata.models import Item, Supplier
from apps.quality.models import NonConformance
from apps.traceability.models import InventoryLot, SerialNumber


class RecallCase(TimeStampedModel):
    class Status(models.TextChoices):
        DRAFT = "DRAFT", "Rascunho"
        INVESTIGATING = "INVESTIGATING", "Em investigação"
        APPROVED = "APPROVED", "Aprovado"
        EXECUTING = "EXECUTING", "Em execução"
        COMPLETED = "COMPLETED", "Concluído"
        CANCELLED = "CANCELLED", "Cancelado"

    class Classification(models.TextChoices):
        INTERNAL = "INTERNAL", "Contenção interna"
        SUPPLIER = "SUPPLIER", "Problema de fornecedor"
        MARKET = "MARKET", "Recall de mercado"
        REGULATORY = "REGULATORY", "Recall regulatório"

    number = models.CharField(max_length=30, unique=True)
    plant = models.ForeignKey(Plant, on_delete=models.PROTECT, related_name="recall_cases")
    classification = models.CharField(max_length=20, choices=Classification.choices)
    title = models.CharField(max_length=200)
    description = models.TextField()
    reason = models.TextField()
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.DRAFT)
    nonconformance = models.ForeignKey(
        NonConformance, null=True, blank=True, on_delete=models.PROTECT, related_name="recall_cases"
    )
    supplier = models.ForeignKey(
        Supplier, null=True, blank=True, on_delete=models.PROTECT, related_name="recall_cases"
    )
    opened_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL,
        related_name="opened_recall_cases",
    )
    approved_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL,
        related_name="approved_recall_cases",
    )
    approved_at = models.DateTimeField(null=True, blank=True)
    completed_at = models.DateTimeField(null=True, blank=True)
    notes = models.TextField(blank=True)

    class Meta:
        ordering = ["-created_at", "-id"]
        indexes = [
            models.Index(fields=["plant", "status", "classification"], name="ix_recall_status_class"),
            models.Index(fields=["supplier", "status"], name="ix_recall_supplier_status"),
        ]
        permissions = [
            ("approve_recallcase", "Pode aprovar recall"),
            ("execute_recallcase", "Pode executar recall"),
        ]

    def __str__(self):
        return f"{self.number} - {self.title}"


class RecallCriterion(TimeStampedModel):
    class CriterionType(models.TextChoices):
        LOT = "LOT", "Lote"
        SERIAL = "SERIAL", "Número de série"
        ITEM = "ITEM", "Item"
        SUPPLIER = "SUPPLIER", "Fornecedor"
        PRODUCTION_PERIOD = "PRODUCTION_PERIOD", "Período de produção"
        SOURCE_REFERENCE = "SOURCE_REFERENCE", "Referência de origem"

    recall_case = models.ForeignKey(RecallCase, on_delete=models.CASCADE, related_name="criteria")
    criterion_type = models.CharField(max_length=25, choices=CriterionType.choices)
    item = models.ForeignKey(Item, null=True, blank=True, on_delete=models.PROTECT, related_name="recall_criteria")
    lot = models.ForeignKey(InventoryLot, null=True, blank=True, on_delete=models.PROTECT, related_name="recall_criteria")
    serial = models.ForeignKey(SerialNumber, null=True, blank=True, on_delete=models.PROTECT, related_name="recall_criteria")
    supplier = models.ForeignKey(Supplier, null=True, blank=True, on_delete=models.PROTECT, related_name="recall_criteria")
    date_from = models.DateTimeField(null=True, blank=True)
    date_to = models.DateTimeField(null=True, blank=True)
    reference_type = models.CharField(max_length=40, blank=True)
    reference_id = models.CharField(max_length=64, blank=True)
    notes = models.TextField(blank=True)

    class Meta:
        ordering = ["recall_case", "id"]
        indexes = [
            models.Index(fields=["recall_case", "criterion_type"], name="ix_recallcriterion_case_type"),
            models.Index(fields=["reference_type", "reference_id"], name="ix_recallcriterion_ref"),
        ]


class RecallAffectedUnit(TimeStampedModel):
    class Source(models.TextChoices):
        DIRECT = "DIRECT", "Critério direto"
        LOT_SERIAL = "LOT_SERIAL", "Série vinculada ao lote"
        GENEALOGY_UP = "GENEALOGY_UP", "Where-used"
        GENEALOGY_DOWN = "GENEALOGY_DOWN", "Componente"
        REFERENCE = "REFERENCE", "Referência transacional"

    class Disposition(models.TextChoices):
        PENDING = "PENDING", "Pendente"
        BLOCKED = "BLOCKED", "Bloqueado"
        RETURNED = "RETURNED", "Retornado"
        REWORKED = "REWORKED", "Retrabalhado"
        SCRAPPED = "SCRAPPED", "Refugado"
        CLEARED = "CLEARED", "Liberado"

    recall_case = models.ForeignKey(RecallCase, on_delete=models.CASCADE, related_name="affected_units")
    item = models.ForeignKey(Item, on_delete=models.PROTECT, related_name="recall_affected_units")
    lot = models.ForeignKey(InventoryLot, null=True, blank=True, on_delete=models.PROTECT, related_name="recall_affected_units")
    serial = models.ForeignKey(SerialNumber, null=True, blank=True, on_delete=models.PROTECT, related_name="recall_affected_units")
    source = models.CharField(max_length=20, choices=Source.choices)
    depth = models.PositiveIntegerField(default=0)
    disposition = models.CharField(max_length=20, choices=Disposition.choices, default=Disposition.PENDING)
    blocked_at = models.DateTimeField(null=True, blank=True)
    disposition_at = models.DateTimeField(null=True, blank=True)
    notes = models.TextField(blank=True)

    class Meta:
        ordering = ["recall_case", "depth", "item__code", "id"]
        constraints = [
            models.UniqueConstraint(
                fields=["recall_case", "serial"], condition=models.Q(serial__isnull=False),
                name="uq_recall_affected_serial",
            ),
            models.UniqueConstraint(
                fields=["recall_case", "lot"], condition=models.Q(serial__isnull=True, lot__isnull=False),
                name="uq_recall_affected_lot",
            ),
            models.CheckConstraint(
                condition=models.Q(serial__isnull=False) | models.Q(lot__isnull=False),
                name="ck_recall_affected_target",
            ),
        ]
        indexes = [
            models.Index(fields=["recall_case", "disposition"], name="ix_recallaffected_disposition"),
            models.Index(fields=["item", "lot", "serial"], name="ix_recallaffected_target"),
        ]


class RecallAction(TimeStampedModel):
    class ActionType(models.TextChoices):
        BLOCK = "BLOCK", "Bloquear"
        NOTIFY = "NOTIFY", "Notificar"
        RETURN = "RETURN", "Retornar"
        REWORK = "REWORK", "Retrabalhar"
        SCRAP = "SCRAP", "Refugar"
        RELEASE = "RELEASE", "Liberar"
        VERIFY = "VERIFY", "Verificar"

    class Status(models.TextChoices):
        OPEN = "OPEN", "Aberta"
        IN_PROGRESS = "IN_PROGRESS", "Em andamento"
        DONE = "DONE", "Concluída"
        CANCELLED = "CANCELLED", "Cancelada"

    recall_case = models.ForeignKey(RecallCase, on_delete=models.CASCADE, related_name="actions")
    affected_unit = models.ForeignKey(
        RecallAffectedUnit, null=True, blank=True, on_delete=models.CASCADE, related_name="actions"
    )
    action_type = models.CharField(max_length=15, choices=ActionType.choices)
    status = models.CharField(max_length=15, choices=Status.choices, default=Status.OPEN)
    owner = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL,
        related_name="recall_actions",
    )
    due_date = models.DateField(null=True, blank=True)
    completed_at = models.DateTimeField(null=True, blank=True)
    result = models.TextField(blank=True)

    class Meta:
        ordering = ["status", "due_date", "id"]
        indexes = [
            models.Index(fields=["recall_case", "status", "action_type"], name="ix_recallaction_case_status"),
            models.Index(fields=["owner", "status", "due_date"], name="ix_recallaction_owner_due"),
        ]
