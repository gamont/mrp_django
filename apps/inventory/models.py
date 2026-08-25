from decimal import Decimal
from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import models
from apps.common.models import Plant, TimeStampedModel
from apps.masterdata.models import Item


class Warehouse(TimeStampedModel):
    plant = models.ForeignKey(Plant, on_delete=models.CASCADE, related_name="warehouses")
    code = models.CharField(max_length=30)
    name = models.CharField(max_length=120)
    is_active = models.BooleanField(default=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=["plant", "code"], name="uq_warehouse_plant_code")
        ]
        ordering = ["plant__code", "code"]

    def __str__(self) -> str:
        return f"{self.plant.code}/{self.code}"


class Location(TimeStampedModel):
    warehouse = models.ForeignKey(Warehouse, on_delete=models.CASCADE, related_name="locations")
    code = models.CharField(max_length=40)
    description = models.CharField(max_length=120, blank=True)
    is_active = models.BooleanField(default=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=["warehouse", "code"], name="uq_location_warehouse_code")
        ]
        ordering = ["warehouse__code", "code"]

    def __str__(self) -> str:
        return f"{self.warehouse}/{self.code}"


class StockBalance(TimeStampedModel):
    item = models.ForeignKey(Item, on_delete=models.CASCADE, related_name="stock_balances")
    location = models.ForeignKey(Location, on_delete=models.CASCADE, related_name="stock_balances")
    on_hand = models.DecimalField(max_digits=18, decimal_places=4, default=0)
    allocated = models.DecimalField(max_digits=18, decimal_places=4, default=0)

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=["item", "location"], name="uq_stock_item_location"),
            models.CheckConstraint(condition=models.Q(on_hand__gte=0), name="ck_stock_onhand_nonneg"),
            models.CheckConstraint(condition=models.Q(allocated__gte=0), name="ck_stock_alloc_nonneg"),
        ]
        ordering = ["item__code", "location__code"]

    @property
    def available(self) -> Decimal:
        return self.on_hand - self.allocated

    def __str__(self) -> str:
        return f"{self.item.code} @ {self.location}: {self.on_hand}"


class InventoryTransaction(TimeStampedModel):
    class TransactionType(models.TextChoices):
        RECEIPT = "RECEIPT", "Recebimento"
        ISSUE = "ISSUE", "Baixa"
        TRANSFER = "TRANSFER", "Transferência"
        ADJUSTMENT = "ADJUSTMENT", "Ajuste"
        PURCHASE_RECEIPT = "PURCHASE_RECEIPT", "Recebimento de compra"
        PRODUCTION_RECEIPT = "PRODUCTION_RECEIPT", "Entrada de produção"
        PRODUCTION_ISSUE = "PRODUCTION_ISSUE", "Consumo de produção"
        RETURN = "RETURN", "Devolução"

    transaction_type = models.CharField(max_length=30, choices=TransactionType.choices)
    item = models.ForeignKey(Item, on_delete=models.PROTECT, related_name="inventory_transactions")
    from_location = models.ForeignKey(
        Location, null=True, blank=True, on_delete=models.PROTECT, related_name="outgoing_transactions"
    )
    to_location = models.ForeignKey(
        Location, null=True, blank=True, on_delete=models.PROTECT, related_name="incoming_transactions"
    )
    quantity = models.DecimalField(max_digits=18, decimal_places=4)
    reference_type = models.CharField(max_length=40, blank=True)
    reference_id = models.CharField(max_length=64, blank=True)
    posted_at = models.DateTimeField(auto_now_add=True)
    posted_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL
    )
    notes = models.TextField(blank=True)
    idempotency_key = models.CharField(max_length=160, null=True, blank=True, unique=True)

    class Meta:
        ordering = ["-posted_at", "-id"]
        indexes = [
            models.Index(fields=["item", "posted_at"], name="ix_invtx_item_posted"),
            models.Index(fields=["reference_type", "reference_id"], name="ix_invtx_reference"),
        ]
        constraints = [
            models.CheckConstraint(condition=~models.Q(quantity=0), name="ck_invtx_quantity_nonzero"),
            models.CheckConstraint(
                condition=(
                    models.Q(transaction_type="ADJUSTMENT")
                    | models.Q(quantity__gt=0)
                ),
                name="ck_invtx_positive_normal",
            ),
        ]

    def clean(self) -> None:
        if self.transaction_type != self.TransactionType.ADJUSTMENT and self.quantity <= 0:
            raise ValidationError({"quantity": "A quantidade deve ser positiva."})
        if self.transaction_type == self.TransactionType.TRANSFER:
            if not self.from_location_id or not self.to_location_id:
                raise ValidationError("Transferência exige origem e destino.")
            if self.from_location_id == self.to_location_id:
                raise ValidationError("Origem e destino devem ser diferentes.")

    def __str__(self) -> str:
        return f"{self.transaction_type} {self.item.code} {self.quantity}"


class Reservation(TimeStampedModel):
    class Status(models.TextChoices):
        OPEN = "OPEN", "Aberta"
        CONSUMED = "CONSUMED", "Consumida"
        CANCELLED = "CANCELLED", "Cancelada"

    item = models.ForeignKey(Item, on_delete=models.CASCADE, related_name="reservations")
    location = models.ForeignKey(Location, on_delete=models.PROTECT, related_name="reservations")
    quantity = models.DecimalField(max_digits=18, decimal_places=4)
    requested_item = models.ForeignKey(
        Item,
        null=True,
        blank=True,
        on_delete=models.PROTECT,
        related_name="substitution_reservations",
        help_text="Item originalmente solicitado quando a reserva usa substituto.",
    )
    requested_quantity = models.DecimalField(max_digits=18, decimal_places=4, default=0)
    consumed_quantity = models.DecimalField(max_digits=18, decimal_places=4, default=0)
    consumed_requested_quantity = models.DecimalField(max_digits=18, decimal_places=4, default=0)
    demand_type = models.CharField(max_length=40)
    demand_id = models.CharField(max_length=64)
    required_date = models.DateField()
    status = models.CharField(max_length=15, choices=Status.choices, default=Status.OPEN)

    class Meta:
        ordering = ["required_date", "item__code"]
        indexes = [
            models.Index(fields=["demand_type", "demand_id", "status"], name="ix_reservation_demand"),
            models.Index(fields=["item", "status", "required_date"], name="ix_reservation_item_date"),
        ]
        constraints = [
            models.CheckConstraint(condition=models.Q(quantity__gt=0), name="ck_reservation_qty_pos"),
            models.CheckConstraint(condition=models.Q(requested_quantity__gt=0), name="ck_reservation_req_pos"),
            models.CheckConstraint(condition=models.Q(consumed_quantity__gte=0), name="ck_reservation_cons_nonneg"),
            models.CheckConstraint(
                condition=models.Q(consumed_quantity__lte=models.F("quantity")),
                name="ck_reservation_cons_lte_qty",
            ),
            models.CheckConstraint(condition=models.Q(consumed_requested_quantity__gte=0), name="ck_reservation_reqcons_nonneg"),
            models.CheckConstraint(
                condition=models.Q(consumed_requested_quantity__lte=models.F("requested_quantity")),
                name="ck_reservation_reqcons_lte",
            ),
        ]

    @property
    def remaining_quantity(self) -> Decimal:
        return self.quantity - self.consumed_quantity

    @property
    def remaining_requested_quantity(self) -> Decimal:
        basis = self.requested_quantity or self.quantity
        return basis - self.consumed_requested_quantity

    def save(self, *args, **kwargs):
        if not self.requested_item_id:
            self.requested_item = self.item
        if not self.requested_quantity:
            self.requested_quantity = self.quantity
        return super().save(*args, **kwargs)

    def __str__(self) -> str:
        requested = self.requested_item.code if self.requested_item_id else self.item.code
        return f"{requested} via {self.item.code}: {self.quantity} para {self.demand_type}/{self.demand_id}"
