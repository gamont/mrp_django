from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import models

from apps.common.models import Plant, TimeStampedModel
from apps.masterdata.models import BOMLine, Item, Routing


class EngineeringChange(TimeStampedModel):
    class Status(models.TextChoices):
        DRAFT = "DRAFT", "Rascunho"
        ANALYSIS = "ANALYSIS", "Em análise"
        APPROVAL = "APPROVAL", "Em aprovação"
        APPROVED = "APPROVED", "Aprovada"
        SCHEDULED = "SCHEDULED", "Programada"
        EFFECTIVE = "EFFECTIVE", "Efetiva"
        CLOSED = "CLOSED", "Encerrada"
        REJECTED = "REJECTED", "Rejeitada"

    class EffectivityType(models.TextChoices):
        IMMEDIATE = "IMMEDIATE", "Imediata"
        DATE = "DATE", "Data"
        LOT = "LOT", "Lote"
        SERIAL = "SERIAL", "Número de série"
        QUANTITY = "QUANTITY", "Quantidade acumulada"
        STOCK_RUNOUT = "STOCK_RUNOUT", "Esgotamento do estoque"
        OTHER_ECO = "OTHER_ECO", "Outra ECO"

    number = models.CharField(max_length=40, unique=True)
    plant = models.ForeignKey(Plant, on_delete=models.PROTECT, related_name="engineering_changes")
    title = models.CharField(max_length=200)
    reason = models.TextField()
    description = models.TextField(blank=True)
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.DRAFT, db_index=True)
    priority = models.PositiveSmallIntegerField(default=3)
    effectivity_type = models.CharField(max_length=20, choices=EffectivityType.choices, default=EffectivityType.DATE)
    effective_date = models.DateField(null=True, blank=True)
    effective_lot = models.CharField(max_length=80, blank=True)
    effective_serial = models.CharField(max_length=80, blank=True)
    effective_quantity = models.DecimalField(max_digits=18, decimal_places=4, null=True, blank=True)
    controlling_change = models.ForeignKey("self", null=True, blank=True, on_delete=models.PROTECT, related_name="dependent_changes")
    requested_by = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL, related_name="requested_ecos")
    approved_by = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL, related_name="approved_ecos")
    submitted_at = models.DateTimeField(null=True, blank=True)
    approved_at = models.DateTimeField(null=True, blank=True)
    activated_at = models.DateTimeField(null=True, blank=True)
    impact_summary = models.JSONField(default=dict, blank=True)

    class Meta:
        ordering = ["-created_at"]
        indexes = [models.Index(fields=["plant", "status"], name="ix_eco_plant_status"), models.Index(fields=["effective_date"], name="ix_eco_effective_date")]
        constraints = [models.CheckConstraint(condition=models.Q(priority__gte=1, priority__lte=5), name="ck_eco_priority_range")]
        permissions = [("approve_engineeringchange", "Pode aprovar alteração de engenharia"), ("activate_engineeringchange", "Pode efetivar alteração de engenharia")]

    def clean(self):
        if self.effectivity_type == self.EffectivityType.DATE and not self.effective_date:
            raise ValidationError({"effective_date": "Informe a data de efetividade."})
        if self.effectivity_type == self.EffectivityType.LOT and not self.effective_lot:
            raise ValidationError({"effective_lot": "Informe o lote de efetividade."})
        if self.effectivity_type == self.EffectivityType.SERIAL and not self.effective_serial:
            raise ValidationError({"effective_serial": "Informe o número de série."})
        if self.effectivity_type == self.EffectivityType.QUANTITY and not self.effective_quantity:
            raise ValidationError({"effective_quantity": "Informe a quantidade de efetividade."})
        if self.controlling_change_id == self.id:
            raise ValidationError({"controlling_change": "Uma ECO não pode controlar a si mesma."})

    def __str__(self):
        return f"{self.number} - {self.title}"


class EngineeringChangeItem(TimeStampedModel):
    class Action(models.TextChoices):
        ADD = "ADD", "Adicionar"
        CHANGE = "CHANGE", "Alterar"
        DELETE = "DELETE", "Excluir"
        REPLACE = "REPLACE", "Substituir"

    change = models.ForeignKey(EngineeringChange, on_delete=models.CASCADE, related_name="items")
    affected_item = models.ForeignKey(Item, on_delete=models.PROTECT, related_name="engineering_change_items")
    action = models.CharField(max_length=12, choices=Action.choices)
    replacement_item = models.ForeignKey(Item, null=True, blank=True, on_delete=models.PROTECT, related_name="replacement_change_items")
    field_name = models.CharField(max_length=80, blank=True)
    old_value = models.JSONField(null=True, blank=True)
    new_value = models.JSONField(null=True, blank=True)
    notes = models.TextField(blank=True)

    class Meta:
        ordering = ["change__number", "affected_item__code", "id"]
        constraints = [models.UniqueConstraint(fields=["change", "affected_item", "field_name"], name="uq_eco_item_field")]


class EngineeringChangeApproval(TimeStampedModel):
    class Decision(models.TextChoices):
        PENDING = "PENDING", "Pendente"
        APPROVED = "APPROVED", "Aprovada"
        REJECTED = "REJECTED", "Rejeitada"

    change = models.ForeignKey(EngineeringChange, on_delete=models.CASCADE, related_name="approvals")
    sequence = models.PositiveSmallIntegerField(default=1)
    role = models.CharField(max_length=80)
    approver = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL, related_name="engineering_approvals")
    decision = models.CharField(max_length=12, choices=Decision.choices, default=Decision.PENDING)
    decided_at = models.DateTimeField(null=True, blank=True)
    comment = models.TextField(blank=True)

    class Meta:
        ordering = ["change", "sequence"]
        constraints = [models.UniqueConstraint(fields=["change", "sequence"], name="uq_eco_approval_sequence")]


class BOMRevision(TimeStampedModel):
    class Status(models.TextChoices):
        DRAFT = "DRAFT", "Rascunho"
        RELEASED = "RELEASED", "Liberada"
        OBSOLETE = "OBSOLETE", "Obsoleta"

    plant = models.ForeignKey(Plant, on_delete=models.PROTECT, related_name="bom_revisions")
    parent = models.ForeignKey(Item, on_delete=models.PROTECT, related_name="bom_revisions")
    revision = models.CharField(max_length=20)
    status = models.CharField(max_length=12, choices=Status.choices, default=Status.DRAFT)
    effective_from = models.DateField(null=True, blank=True)
    effective_to = models.DateField(null=True, blank=True)
    change = models.ForeignKey(EngineeringChange, null=True, blank=True, on_delete=models.PROTECT, related_name="bom_revisions")
    notes = models.TextField(blank=True)

    class Meta:
        ordering = ["parent__code", "-revision"]
        constraints = [models.UniqueConstraint(fields=["plant", "parent", "revision"], name="uq_bom_revision"), models.CheckConstraint(condition=models.Q(effective_to__isnull=True) | models.Q(effective_from__isnull=True) | models.Q(effective_to__gte=models.F("effective_from")), name="ck_bomrev_dates")]


class BOMRevisionLine(TimeStampedModel):
    revision = models.ForeignKey(BOMRevision, on_delete=models.CASCADE, related_name="lines")
    sequence = models.PositiveIntegerField(default=10)
    component = models.ForeignKey(Item, on_delete=models.PROTECT, related_name="bom_revision_usages")
    quantity_per = models.DecimalField(max_digits=18, decimal_places=6)
    scrap_percent = models.DecimalField(max_digits=7, decimal_places=3, default=0)
    source_line = models.ForeignKey(BOMLine, null=True, blank=True, on_delete=models.SET_NULL, related_name="revision_lines")

    class Meta:
        ordering = ["revision", "sequence"]
        constraints = [models.UniqueConstraint(fields=["revision", "sequence"], name="uq_bomrev_line_sequence"), models.CheckConstraint(condition=models.Q(quantity_per__gt=0), name="ck_bomrev_qty_pos"), models.CheckConstraint(condition=models.Q(scrap_percent__gte=0), name="ck_bomrev_scrap_nonneg")]


class RoutingRevision(TimeStampedModel):
    plant = models.ForeignKey(Plant, on_delete=models.PROTECT, related_name="routing_revisions")
    item = models.ForeignKey(Item, on_delete=models.PROTECT, related_name="routing_revisions")
    routing = models.ForeignKey(Routing, null=True, blank=True, on_delete=models.SET_NULL, related_name="revision_snapshots")
    revision = models.CharField(max_length=20)
    status = models.CharField(max_length=12, choices=BOMRevision.Status.choices, default=BOMRevision.Status.DRAFT)
    effective_from = models.DateField(null=True, blank=True)
    effective_to = models.DateField(null=True, blank=True)
    change = models.ForeignKey(EngineeringChange, null=True, blank=True, on_delete=models.PROTECT, related_name="routing_revisions")
    operations_snapshot = models.JSONField(default=list, blank=True)

    class Meta:
        constraints = [models.UniqueConstraint(fields=["plant", "item", "revision"], name="uq_routing_revision")]


class EngineeringImpact(TimeStampedModel):
    change = models.ForeignKey(EngineeringChange, on_delete=models.CASCADE, related_name="impacts")
    impact_type = models.CharField(max_length=40)
    object_type = models.CharField(max_length=80)
    object_id = models.CharField(max_length=80)
    severity = models.CharField(max_length=12, default="INFO")
    description = models.TextField()
    details = models.JSONField(default=dict, blank=True)

    class Meta:
        ordering = ["-severity", "object_type", "object_id"]
        constraints = [models.UniqueConstraint(fields=["change", "impact_type", "object_type", "object_id"], name="uq_eco_impact_object")]
