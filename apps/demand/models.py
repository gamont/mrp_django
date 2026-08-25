from django.db import models
from apps.common.models import Plant, TimeStampedModel
from apps.masterdata.models import Item


class Forecast(TimeStampedModel):
    class Status(models.TextChoices):
        DRAFT = "DRAFT", "Rascunho"
        APPROVED = "APPROVED", "Aprovada"
        CANCELLED = "CANCELLED", "Cancelada"

    plant = models.ForeignKey(Plant, on_delete=models.CASCADE, related_name="forecasts")
    item = models.ForeignKey(Item, on_delete=models.CASCADE, related_name="forecasts")
    period_start = models.DateField()
    period_end = models.DateField()
    quantity = models.DecimalField(max_digits=18, decimal_places=4)
    version = models.PositiveIntegerField(default=1)
    status = models.CharField(max_length=15, choices=Status.choices, default=Status.DRAFT)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["plant", "item", "period_start", "version"], name="uq_forecast_version"
            ),
            models.CheckConstraint(condition=models.Q(quantity__gt=0), name="ck_forecast_qty_pos"),
            models.CheckConstraint(
                condition=models.Q(period_end__gte=models.F("period_start")),
                name="ck_forecast_dates",
            ),
        ]
        ordering = ["period_start", "item__code"]


class SalesOrder(TimeStampedModel):
    class Status(models.TextChoices):
        DRAFT = "DRAFT", "Rascunho"
        CONFIRMED = "CONFIRMED", "Confirmado"
        PARTIAL = "PARTIAL", "Parcial"
        COMPLETED = "COMPLETED", "Concluído"
        CANCELLED = "CANCELLED", "Cancelado"

    number = models.CharField(max_length=40, unique=True)
    plant = models.ForeignKey(Plant, on_delete=models.PROTECT, related_name="sales_orders")
    customer_code = models.CharField(max_length=50)
    customer_name = models.CharField(max_length=160)
    order_date = models.DateField()
    requested_date = models.DateField()
    # 0.8.6 — condições comerciais para projeção de contas a receber.
    receivable_terms_days = models.PositiveIntegerField(default=30, help_text="Dias entre a data de compromisso/entrega planejada e o recebimento estimado.")
    receivable_terms_code = models.CharField(max_length=30, blank=True, default="NET30")
    receivable_installments = models.JSONField(default=list, blank=True, help_text='Opcional: [{"days":30,"percent":50},{"days":60,"percent":50}]')
    status = models.CharField(max_length=15, choices=Status.choices, default=Status.DRAFT)

    class Meta:
        ordering = ["-order_date", "number"]
        constraints = [
            models.CheckConstraint(
                condition=models.Q(requested_date__gte=models.F("order_date")),
                name="ck_salesorder_dates",
            ),
        ]

    def __str__(self) -> str:
        return self.number


class SalesOrderLine(TimeStampedModel):
    sales_order = models.ForeignKey(SalesOrder, on_delete=models.CASCADE, related_name="lines")
    line_number = models.PositiveIntegerField()
    item = models.ForeignKey(Item, on_delete=models.PROTECT, related_name="sales_order_lines")
    quantity = models.DecimalField(max_digits=18, decimal_places=4)
    delivered_quantity = models.DecimalField(max_digits=18, decimal_places=4, default=0)
    requested_date = models.DateField()
    # 0.7.8 — preço líquido opcional para análise executiva de receita em risco.
    unit_net_price = models.DecimalField(max_digits=18, decimal_places=4, null=True, blank=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=["sales_order", "line_number"], name="uq_sales_order_line"),
            models.CheckConstraint(condition=models.Q(quantity__gt=0), name="ck_sol_qty_pos"),
            models.CheckConstraint(condition=models.Q(delivered_quantity__gte=0), name="ck_sol_deliv_nonneg"),
            models.CheckConstraint(
                condition=models.Q(delivered_quantity__lte=models.F("quantity")),
                name="ck_sol_deliv_lte_qty",
            ),
            models.CheckConstraint(
                condition=models.Q(unit_net_price__isnull=True) | models.Q(unit_net_price__gte=0),
                name="ck_sol_net_price_nonneg",
            ),
        ]
        ordering = ["sales_order", "line_number"]

    @property
    def open_quantity(self):
        return max(self.quantity - self.delivered_quantity, 0)


class MasterProductionSchedule(TimeStampedModel):
    class Status(models.TextChoices):
        PLANNED = "PLANNED", "Planejado"
        FIRM = "FIRM", "Firme"
        FROZEN = "FROZEN", "Congelado"
        CANCELLED = "CANCELLED", "Cancelado"

    plant = models.ForeignKey(Plant, on_delete=models.CASCADE, related_name="mps_entries")
    item = models.ForeignKey(Item, on_delete=models.CASCADE, related_name="mps_entries")
    due_date = models.DateField()
    quantity = models.DecimalField(max_digits=18, decimal_places=4)
    status = models.CharField(max_length=15, choices=Status.choices, default=Status.PLANNED)
    source = models.CharField(max_length=60, blank=True)
    notes = models.TextField(blank=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=["plant", "item", "due_date", "source"], name="uq_mps_source"),
            models.CheckConstraint(condition=models.Q(quantity__gt=0), name="ck_mps_qty_pos"),
        ]
        ordering = ["due_date", "item__code"]
        indexes = [models.Index(fields=["plant", "due_date", "status"], name="ix_mps_plant_due_status")]

    def __str__(self) -> str:
        return f"{self.item.code} {self.due_date}: {self.quantity}"


# 0.7.6 — entregas comerciais para OTIF
class SalesDelivery(TimeStampedModel):
    number = models.CharField(max_length=50, unique=True)
    plant = models.ForeignKey(Plant, on_delete=models.PROTECT, related_name="sales_deliveries")
    delivery_date = models.DateField()
    shipped_at = models.DateTimeField(null=True, blank=True)
    carrier = models.CharField(max_length=120, blank=True)
    tracking_reference = models.CharField(max_length=120, blank=True)
    notes = models.TextField(blank=True)

    class Meta:
        ordering = ["-delivery_date", "number"]
        indexes = [models.Index(fields=["plant", "delivery_date"], name="ix_salesdel_plant_date")]

    def __str__(self):
        return self.number


class SalesDeliveryLine(TimeStampedModel):
    delivery = models.ForeignKey(SalesDelivery, on_delete=models.CASCADE, related_name="lines")
    sales_order_line = models.ForeignKey(SalesOrderLine, on_delete=models.PROTECT, related_name="delivery_lines")
    quantity = models.DecimalField(max_digits=18, decimal_places=4)

    class Meta:
        ordering = ["delivery", "sales_order_line__line_number"]
        constraints = [
            models.UniqueConstraint(fields=["delivery", "sales_order_line"], name="uq_delivery_sales_line"),
            models.CheckConstraint(condition=models.Q(quantity__gt=0), name="ck_deliveryline_qty_pos"),
        ]
        indexes = [models.Index(fields=["sales_order_line"], name="ix_deliveryline_sol")]
