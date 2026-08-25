from django.db import models

from apps.common.models import Plant, TimeStampedModel
from apps.inventory.models import InventoryTransaction, Location
from apps.masterdata.models import BOMLine, Item, Routing, WorkCenter


class WorkOrder(TimeStampedModel):
    class Status(models.TextChoices):
        PLANNED = "PLANNED", "Planejada"
        RELEASED = "RELEASED", "Liberada"
        IN_PROGRESS = "IN_PROGRESS", "Em andamento"
        COMPLETED = "COMPLETED", "Concluída"
        CLOSED = "CLOSED", "Encerrada"
        CANCELLED = "CANCELLED", "Cancelada"

    number = models.CharField(max_length=40, unique=True)
    plant = models.ForeignKey(Plant, on_delete=models.PROTECT, related_name="work_orders")
    item = models.ForeignKey(Item, on_delete=models.PROTECT, related_name="work_orders")
    routing = models.ForeignKey(
        Routing, null=True, blank=True, on_delete=models.SET_NULL, related_name="work_orders"
    )
    quantity = models.DecimalField(max_digits=18, decimal_places=4)
    completed_quantity = models.DecimalField(max_digits=18, decimal_places=4, default=0)
    release_date = models.DateField()
    due_date = models.DateField()
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.PLANNED)
    planning_run_id = models.PositiveBigIntegerField(null=True, blank=True)
    planned_order_id = models.PositiveBigIntegerField(null=True, blank=True)

    class Meta:
        ordering = ["release_date", "number"]
        indexes = [models.Index(fields=["plant", "status", "due_date"], name="ix_wo_plant_status_due")]
        constraints = [
            models.CheckConstraint(condition=models.Q(quantity__gt=0), name="ck_wo_qty_pos"),
            models.CheckConstraint(condition=models.Q(completed_quantity__gte=0), name="ck_wo_completed_nonneg"),
            models.CheckConstraint(
                condition=models.Q(completed_quantity__lte=models.F("quantity")),
                name="ck_wo_completed_lte_qty",
            ),
            models.CheckConstraint(
                condition=models.Q(due_date__gte=models.F("release_date")),
                name="ck_wo_dates",
            ),
        ]

    def __str__(self) -> str:
        return self.number


class WorkOrderMaterial(TimeStampedModel):
    work_order = models.ForeignKey(WorkOrder, on_delete=models.CASCADE, related_name="materials")
    item = models.ForeignKey(Item, on_delete=models.PROTECT, related_name="work_order_materials")
    bom_line = models.ForeignKey(BOMLine, null=True, blank=True, on_delete=models.SET_NULL)
    required_quantity = models.DecimalField(max_digits=18, decimal_places=4)
    issued_quantity = models.DecimalField(max_digits=18, decimal_places=4, default=0)
    required_date = models.DateField()

    class Meta:
        ordering = ["work_order", "item__code"]
        indexes = [models.Index(fields=["work_order", "required_date"], name="ix_womaterial_order_date")]
        constraints = [
            models.CheckConstraint(condition=models.Q(required_quantity__gt=0), name="ck_womaterial_req_pos"),
            models.CheckConstraint(condition=models.Q(issued_quantity__gte=0), name="ck_womaterial_issue_nonneg"),
            models.CheckConstraint(
                condition=models.Q(issued_quantity__lte=models.F("required_quantity")),
                name="ck_womaterial_issue_lte",
            ),
        ]


class WorkOrderOperation(TimeStampedModel):
    class Status(models.TextChoices):
        PENDING = "PENDING", "Pendente"
        READY = "READY", "Pronta"
        SETUP = "SETUP", "Setup"
        RUNNING = "RUNNING", "Executando"
        INTERRUPTED = "INTERRUPTED", "Interrompida"
        COMPLETED = "COMPLETED", "Concluída"

    work_order = models.ForeignKey(WorkOrder, on_delete=models.CASCADE, related_name="operations")
    sequence = models.PositiveIntegerField()
    description = models.CharField(max_length=200)
    work_center = models.ForeignKey(WorkCenter, on_delete=models.PROTECT, related_name="work_order_operations")
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.PENDING)
    planned_start = models.DateTimeField(null=True, blank=True)
    planned_end = models.DateTimeField(null=True, blank=True)
    actual_start = models.DateTimeField(null=True, blank=True)
    actual_end = models.DateTimeField(null=True, blank=True)
    setup_hours = models.DecimalField(max_digits=12, decimal_places=4, default=0)
    run_hours = models.DecimalField(max_digits=12, decimal_places=4, default=0)

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=["work_order", "sequence"], name="uq_work_order_operation"),
            models.CheckConstraint(condition=models.Q(setup_hours__gte=0), name="ck_woop_setup_nonneg"),
            models.CheckConstraint(condition=models.Q(run_hours__gte=0), name="ck_woop_run_nonneg"),
        ]
        ordering = ["work_order", "sequence"]


class ProductionReport(TimeStampedModel):
    work_order = models.ForeignKey(WorkOrder, on_delete=models.PROTECT, related_name="reports")
    operation = models.ForeignKey(
        WorkOrderOperation, null=True, blank=True, on_delete=models.PROTECT, related_name="reports"
    )
    reported_at = models.DateTimeField()
    good_quantity = models.DecimalField(max_digits=18, decimal_places=4, default=0)
    scrap_quantity = models.DecimalField(max_digits=18, decimal_places=4, default=0)
    labor_hours = models.DecimalField(max_digits=12, decimal_places=4, default=0)
    machine_hours = models.DecimalField(max_digits=12, decimal_places=4, default=0)
    notes = models.TextField(blank=True)

    class Meta:
        ordering = ["-reported_at"]
        indexes = [models.Index(fields=["work_order", "reported_at"], name="ix_prodreport_order_time")]
        constraints = [
            models.CheckConstraint(condition=models.Q(good_quantity__gte=0), name="ck_prodreport_good_nonneg"),
            models.CheckConstraint(condition=models.Q(scrap_quantity__gte=0), name="ck_prodreport_scrap_nonneg"),
            models.CheckConstraint(condition=models.Q(labor_hours__gte=0), name="ck_prodreport_labor_nonneg"),
            models.CheckConstraint(condition=models.Q(machine_hours__gte=0), name="ck_prodreport_machine_nonneg"),
        ]


class WorkOrderCompletion(TimeStampedModel):
    """Comando idempotente de apontamento/encerramento com integração ao estoque."""

    work_order = models.ForeignKey(WorkOrder, on_delete=models.PROTECT, related_name="completions")
    idempotency_key = models.CharField(max_length=160, unique=True)
    good_quantity = models.DecimalField(max_digits=18, decimal_places=4)
    scrap_quantity = models.DecimalField(max_digits=18, decimal_places=4, default=0)
    destination_location = models.ForeignKey(
        Location, on_delete=models.PROTECT, related_name="production_completions"
    )
    receipt_transaction = models.OneToOneField(
        InventoryTransaction,
        on_delete=models.PROTECT,
        related_name="work_order_completion",
    )
    reported_at = models.DateTimeField()
    backflush = models.BooleanField(default=True)
    closed_order = models.BooleanField(default=False)
    notes = models.TextField(blank=True)

    class Meta:
        ordering = ["-reported_at", "-id"]
        indexes = [models.Index(fields=["work_order", "reported_at"], name="ix_wocompletion_order_time")]
        constraints = [
            models.CheckConstraint(condition=models.Q(good_quantity__gt=0), name="ck_wocompletion_good_pos"),
            models.CheckConstraint(condition=models.Q(scrap_quantity__gte=0), name="ck_wocompletion_scrap_nonneg"),
        ]

    def __str__(self) -> str:
        return f"{self.work_order.number}: {self.good_quantity}"
