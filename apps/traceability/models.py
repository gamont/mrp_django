from __future__ import annotations

from decimal import Decimal

from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import models

from apps.common.models import Plant, TimeStampedModel
from apps.inventory.models import Location
from apps.masterdata.models import Item, Supplier


class InventoryLot(TimeStampedModel):
    class Status(models.TextChoices):
        AVAILABLE = "AVAILABLE", "Disponível"
        QUARANTINE = "QUARANTINE", "Quarentena"
        INSPECTION = "INSPECTION", "Em inspeção"
        BLOCKED = "BLOCKED", "Bloqueado"
        REJECTED = "REJECTED", "Rejeitado"
        EXPIRED = "EXPIRED", "Vencido"
        CONSUMED = "CONSUMED", "Consumido"

    plant = models.ForeignKey(Plant, on_delete=models.PROTECT, related_name="inventory_lots")
    item = models.ForeignKey(Item, on_delete=models.PROTECT, related_name="inventory_lots")
    lot_number = models.CharField(max_length=80)
    supplier = models.ForeignKey(
        Supplier, null=True, blank=True, on_delete=models.PROTECT, related_name="supplied_lots"
    )
    manufacture_date = models.DateField(null=True, blank=True)
    expiration_date = models.DateField(null=True, blank=True)
    received_at = models.DateTimeField(null=True, blank=True)
    source_type = models.CharField(max_length=40, blank=True)
    source_id = models.CharField(max_length=64, blank=True)
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.AVAILABLE)
    notes = models.TextField(blank=True)

    class Meta:
        ordering = ["item__code", "lot_number"]
        constraints = [
            models.UniqueConstraint(fields=["plant", "item", "lot_number"], name="uq_lot_plant_item_number"),
            models.CheckConstraint(
                condition=models.Q(expiration_date__isnull=True)
                | models.Q(manufacture_date__isnull=True)
                | models.Q(expiration_date__gte=models.F("manufacture_date")),
                name="ck_lot_exp_after_mfg",
            ),
        ]
        indexes = [
            models.Index(fields=["plant", "item", "status"], name="ix_lot_plant_item_status"),
            models.Index(fields=["expiration_date", "status"], name="ix_lot_exp_status"),
            models.Index(fields=["source_type", "source_id"], name="ix_lot_source"),
        ]

    def clean(self):
        if self.expiration_date and self.manufacture_date and self.expiration_date < self.manufacture_date:
            raise ValidationError({"expiration_date": "Validade não pode preceder a fabricação."})

    def __str__(self):
        return f"{self.item.code}/{self.lot_number}"


class LotBalance(TimeStampedModel):
    lot = models.ForeignKey(InventoryLot, on_delete=models.CASCADE, related_name="balances")
    location = models.ForeignKey(Location, on_delete=models.PROTECT, related_name="lot_balances")
    on_hand = models.DecimalField(max_digits=18, decimal_places=4, default=0)
    allocated = models.DecimalField(max_digits=18, decimal_places=4, default=0)

    class Meta:
        ordering = ["lot__item__code", "lot__lot_number", "location__code"]
        constraints = [
            models.UniqueConstraint(fields=["lot", "location"], name="uq_lotbalance_lot_location"),
            models.CheckConstraint(condition=models.Q(on_hand__gte=0), name="ck_lotbal_onhand_nonneg"),
            models.CheckConstraint(condition=models.Q(allocated__gte=0), name="ck_lotbal_alloc_nonneg"),
            models.CheckConstraint(condition=models.Q(allocated__lte=models.F("on_hand")), name="ck_lotbal_alloc_lte_onhand"),
        ]
        indexes = [models.Index(fields=["location", "lot"], name="ix_lotbal_location_lot")]

    @property
    def available(self) -> Decimal:
        return self.on_hand - self.allocated

    def __str__(self):
        return f"{self.lot} @ {self.location}: {self.on_hand}"


class LotTransaction(TimeStampedModel):
    class TransactionType(models.TextChoices):
        RECEIPT = "RECEIPT", "Recebimento"
        ISSUE = "ISSUE", "Baixa"
        TRANSFER = "TRANSFER", "Transferência"
        ADJUSTMENT = "ADJUSTMENT", "Ajuste"
        STATUS = "STATUS", "Mudança de status"
        SPLIT = "SPLIT", "Fracionamento"
        MERGE = "MERGE", "Consolidação"

    transaction_type = models.CharField(max_length=20, choices=TransactionType.choices)
    lot = models.ForeignKey(InventoryLot, on_delete=models.PROTECT, related_name="transactions")
    from_location = models.ForeignKey(
        Location, null=True, blank=True, on_delete=models.PROTECT, related_name="outgoing_lot_transactions"
    )
    to_location = models.ForeignKey(
        Location, null=True, blank=True, on_delete=models.PROTECT, related_name="incoming_lot_transactions"
    )
    quantity = models.DecimalField(max_digits=18, decimal_places=4)
    reference_type = models.CharField(max_length=40, blank=True)
    reference_id = models.CharField(max_length=64, blank=True)
    posted_at = models.DateTimeField(auto_now_add=True)
    posted_by = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL)
    idempotency_key = models.CharField(max_length=160, unique=True)
    notes = models.TextField(blank=True)

    class Meta:
        ordering = ["-posted_at", "-id"]
        constraints = [models.CheckConstraint(condition=models.Q(quantity__gt=0), name="ck_lottx_quantity_pos")]
        indexes = [
            models.Index(fields=["lot", "posted_at"], name="ix_lottx_lot_posted"),
            models.Index(fields=["reference_type", "reference_id"], name="ix_lottx_reference"),
        ]

    def clean(self):
        if self.transaction_type == self.TransactionType.TRANSFER:
            if not self.from_location_id or not self.to_location_id:
                raise ValidationError("Transferência de lote exige origem e destino.")
            if self.from_location_id == self.to_location_id:
                raise ValidationError("Origem e destino devem ser diferentes.")


class LotReservation(TimeStampedModel):
    class Status(models.TextChoices):
        OPEN = "OPEN", "Aberta"
        CONSUMED = "CONSUMED", "Consumida"
        CANCELLED = "CANCELLED", "Cancelada"

    lot = models.ForeignKey(InventoryLot, on_delete=models.PROTECT, related_name="reservations")
    location = models.ForeignKey(Location, on_delete=models.PROTECT, related_name="lot_reservations")
    quantity = models.DecimalField(max_digits=18, decimal_places=4)
    consumed_quantity = models.DecimalField(max_digits=18, decimal_places=4, default=0)
    demand_type = models.CharField(max_length=40)
    demand_id = models.CharField(max_length=64)
    required_date = models.DateField()
    status = models.CharField(max_length=15, choices=Status.choices, default=Status.OPEN)

    class Meta:
        ordering = ["required_date", "lot__item__code", "lot__lot_number"]
        constraints = [
            models.CheckConstraint(condition=models.Q(quantity__gt=0), name="ck_lotres_qty_pos"),
            models.CheckConstraint(condition=models.Q(consumed_quantity__gte=0), name="ck_lotres_cons_nonneg"),
            models.CheckConstraint(condition=models.Q(consumed_quantity__lte=models.F("quantity")), name="ck_lotres_cons_lte_qty"),
        ]
        indexes = [
            models.Index(fields=["demand_type", "demand_id", "status"], name="ix_lotres_demand"),
            models.Index(fields=["lot", "status", "required_date"], name="ix_lotres_lot_date"),
        ]

    @property
    def remaining_quantity(self) -> Decimal:
        return self.quantity - self.consumed_quantity


class SerialNumber(TimeStampedModel):
    class Status(models.TextChoices):
        CREATED = "CREATED", "Criado"
        AVAILABLE = "AVAILABLE", "Disponível"
        RESERVED = "RESERVED", "Reservado"
        IN_PRODUCTION = "IN_PRODUCTION", "Em produção"
        INSTALLED = "INSTALLED", "Instalado"
        SHIPPED = "SHIPPED", "Expedido"
        BLOCKED = "BLOCKED", "Bloqueado"
        SCRAPPED = "SCRAPPED", "Refugado"

    plant = models.ForeignKey(Plant, on_delete=models.PROTECT, related_name="serial_numbers")
    item = models.ForeignKey(Item, on_delete=models.PROTECT, related_name="serial_numbers")
    serial_number = models.CharField(max_length=100)
    lot = models.ForeignKey(InventoryLot, null=True, blank=True, on_delete=models.PROTECT, related_name="serial_numbers")
    current_location = models.ForeignKey(
        Location, null=True, blank=True, on_delete=models.PROTECT, related_name="serial_numbers"
    )
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.CREATED)
    source_type = models.CharField(max_length=40, blank=True)
    source_id = models.CharField(max_length=64, blank=True)
    manufactured_at = models.DateTimeField(null=True, blank=True)
    notes = models.TextField(blank=True)

    class Meta:
        ordering = ["item__code", "serial_number"]
        constraints = [
            models.UniqueConstraint(fields=["plant", "item", "serial_number"], name="uq_serial_plant_item_number")
        ]
        indexes = [
            models.Index(fields=["plant", "item", "status"], name="ix_serial_plant_item_status"),
            models.Index(fields=["source_type", "source_id"], name="ix_serial_source"),
        ]

    def clean(self):
        if self.lot_id and self.lot.item_id != self.item_id:
            raise ValidationError({"lot": "O lote deve pertencer ao mesmo item da série."})

    def __str__(self):
        return f"{self.item.code}/{self.serial_number}"


class SerialTransaction(TimeStampedModel):
    class TransactionType(models.TextChoices):
        CREATE = "CREATE", "Criação"
        MOVE = "MOVE", "Movimentação"
        RESERVE = "RESERVE", "Reserva"
        ISSUE = "ISSUE", "Baixa"
        INSTALL = "INSTALL", "Instalação"
        REMOVE = "REMOVE", "Remoção"
        SHIP = "SHIP", "Expedição"
        BLOCK = "BLOCK", "Bloqueio"
        SCRAP = "SCRAP", "Refugo"

    serial = models.ForeignKey(SerialNumber, on_delete=models.PROTECT, related_name="transactions")
    transaction_type = models.CharField(max_length=20, choices=TransactionType.choices)
    from_location = models.ForeignKey(
        Location, null=True, blank=True, on_delete=models.PROTECT, related_name="outgoing_serial_transactions"
    )
    to_location = models.ForeignKey(
        Location, null=True, blank=True, on_delete=models.PROTECT, related_name="incoming_serial_transactions"
    )
    reference_type = models.CharField(max_length=40, blank=True)
    reference_id = models.CharField(max_length=64, blank=True)
    posted_at = models.DateTimeField(auto_now_add=True)
    posted_by = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL)
    idempotency_key = models.CharField(max_length=160, unique=True)
    notes = models.TextField(blank=True)

    class Meta:
        ordering = ["-posted_at", "-id"]
        indexes = [
            models.Index(fields=["serial", "posted_at"], name="ix_serialtx_serial_posted"),
            models.Index(fields=["reference_type", "reference_id"], name="ix_serialtx_reference"),
        ]


class SerialComponent(TimeStampedModel):
    parent_serial = models.ForeignKey(SerialNumber, on_delete=models.PROTECT, related_name="installed_components")
    component_serial = models.ForeignKey(SerialNumber, on_delete=models.PROTECT, related_name="where_installed")
    quantity = models.DecimalField(max_digits=18, decimal_places=4, default=1)
    installed_at = models.DateTimeField()
    removed_at = models.DateTimeField(null=True, blank=True)
    work_order_id = models.CharField(max_length=64, blank=True)
    operation_sequence = models.PositiveIntegerField(null=True, blank=True)
    notes = models.TextField(blank=True)

    class Meta:
        ordering = ["parent_serial__serial_number", "installed_at"]
        constraints = [
            models.CheckConstraint(condition=models.Q(quantity__gt=0), name="ck_serialcomp_qty_pos"),
            models.CheckConstraint(condition=~models.Q(parent_serial=models.F("component_serial")), name="ck_serialcomp_not_self"),
            models.UniqueConstraint(
                fields=["parent_serial", "component_serial"],
                condition=models.Q(removed_at__isnull=True),
                name="uq_serialcomp_active_pair",
            ),
        ]
        indexes = [
            models.Index(fields=["parent_serial", "removed_at"], name="ix_serialcomp_parent_active"),
            models.Index(fields=["component_serial", "removed_at"], name="ix_serialcomp_component_active"),
        ]

    def clean(self):
        if self.parent_serial_id == self.component_serial_id:
            raise ValidationError("Uma série não pode conter a si própria.")
