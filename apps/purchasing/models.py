from django.db import models

from apps.common.models import Plant, TimeStampedModel
from apps.inventory.models import InventoryTransaction, Location
from apps.masterdata.models import Item, Supplier


class PurchaseOrder(TimeStampedModel):
    class Status(models.TextChoices):
        DRAFT = "DRAFT", "Rascunho"
        RELEASED = "RELEASED", "Liberada"
        PARTIAL = "PARTIAL", "Parcial"
        COMPLETED = "COMPLETED", "Concluída"
        CANCELLED = "CANCELLED", "Cancelada"

    number = models.CharField(max_length=40, unique=True)
    plant = models.ForeignKey(Plant, on_delete=models.PROTECT, related_name="purchase_orders")
    supplier = models.ForeignKey(Supplier, on_delete=models.PROTECT, related_name="purchase_orders")
    order_date = models.DateField()
    expected_date = models.DateField()
    status = models.CharField(max_length=15, choices=Status.choices, default=Status.DRAFT)
    planning_run_id = models.PositiveBigIntegerField(null=True, blank=True)
    planned_order_id = models.PositiveBigIntegerField(null=True, blank=True)

    class Meta:
        ordering = ["expected_date", "number"]
        indexes = [models.Index(fields=["plant", "status", "expected_date"], name="ix_po_plant_status_date")]
        constraints = [
            models.CheckConstraint(
                condition=models.Q(expected_date__gte=models.F("order_date")),
                name="ck_po_dates",
            ),
        ]

    def __str__(self) -> str:
        return self.number


class PurchaseOrderLine(TimeStampedModel):
    purchase_order = models.ForeignKey(PurchaseOrder, on_delete=models.CASCADE, related_name="lines")
    line_number = models.PositiveIntegerField()
    item = models.ForeignKey(Item, on_delete=models.PROTECT, related_name="purchase_order_lines")
    quantity = models.DecimalField(max_digits=18, decimal_places=4)
    received_quantity = models.DecimalField(max_digits=18, decimal_places=4, default=0)
    unit_price = models.DecimalField(max_digits=18, decimal_places=4, default=0)
    expected_date = models.DateField()

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=["purchase_order", "line_number"], name="uq_purchase_order_line"),
            models.CheckConstraint(condition=models.Q(quantity__gt=0), name="ck_pol_qty_pos"),
            models.CheckConstraint(condition=models.Q(received_quantity__gte=0), name="ck_pol_received_nonneg"),
            models.CheckConstraint(
                condition=models.Q(received_quantity__lte=models.F("quantity")),
                name="ck_pol_received_lte_qty",
            ),
            models.CheckConstraint(condition=models.Q(unit_price__gte=0), name="ck_pol_price_nonneg"),
        ]
        ordering = ["purchase_order", "line_number"]

    @property
    def open_quantity(self):
        return max(self.quantity - self.received_quantity, 0)


class GoodsReceipt(TimeStampedModel):
    purchase_order_line = models.ForeignKey(
        PurchaseOrderLine, on_delete=models.PROTECT, related_name="receipts"
    )
    receipt_number = models.CharField(max_length=40)
    idempotency_key = models.CharField(max_length=160, unique=True)
    received_at = models.DateTimeField()
    quantity = models.DecimalField(max_digits=18, decimal_places=4)
    destination_location = models.ForeignKey(
        Location, on_delete=models.PROTECT, related_name="purchase_receipts"
    )
    inventory_transaction = models.OneToOneField(
        InventoryTransaction,
        null=True,
        blank=True,
        on_delete=models.PROTECT,
        related_name="goods_receipt",
    )
    lot_number = models.CharField(max_length=60, blank=True)
    notes = models.TextField(blank=True)

    class Meta:
        ordering = ["-received_at"]
        constraints = [
            models.UniqueConstraint(
                fields=["purchase_order_line", "receipt_number"],
                name="uq_receipt_line_number",
            ),
            models.CheckConstraint(condition=models.Q(quantity__gt=0), name="ck_receipt_qty_pos"),
        ]
        indexes = [
            models.Index(fields=["purchase_order_line", "received_at"], name="ix_receipt_line_time"),
        ]

    def __str__(self) -> str:
        return f"{self.receipt_number} - {self.purchase_order_line}"
