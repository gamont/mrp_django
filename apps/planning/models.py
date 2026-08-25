from django.db import models
from apps.common.models import Plant, TimeStampedModel
from apps.masterdata.models import Item


class PlanningRun(TimeStampedModel):
    class Status(models.TextChoices):
        DRAFT = "DRAFT", "Rascunho"
        RUNNING = "RUNNING", "Executando"
        COMPLETED = "COMPLETED", "Concluída"
        FAILED = "FAILED", "Falhou"

    name = models.CharField(max_length=120)
    plant = models.ForeignKey(Plant, on_delete=models.PROTECT, related_name="planning_runs")
    horizon_start = models.DateField()
    horizon_end = models.DateField()
    status = models.CharField(max_length=15, choices=Status.choices, default=Status.DRAFT)
    started_at = models.DateTimeField(null=True, blank=True)
    completed_at = models.DateTimeField(null=True, blank=True)
    parameters = models.JSONField(default=dict, blank=True)
    error_message = models.TextField(blank=True)

    class Meta:
        ordering = ["-created_at"]
        constraints = [
            models.CheckConstraint(
                condition=models.Q(horizon_end__gte=models.F("horizon_start")),
                name="ck_planrun_horizon",
            ),
        ]

    def __str__(self) -> str:
        return self.name


class PlanningBucket(TimeStampedModel):
    planning_run = models.ForeignKey(PlanningRun, on_delete=models.CASCADE, related_name="buckets")
    item = models.ForeignKey(Item, on_delete=models.CASCADE, related_name="planning_buckets")
    bucket_date = models.DateField()
    gross_requirements = models.DecimalField(max_digits=18, decimal_places=4, default=0)
    scheduled_receipts = models.DecimalField(max_digits=18, decimal_places=4, default=0)
    projected_available = models.DecimalField(max_digits=18, decimal_places=4, default=0)
    net_requirements = models.DecimalField(max_digits=18, decimal_places=4, default=0)
    planned_order_receipts = models.DecimalField(max_digits=18, decimal_places=4, default=0)
    planned_order_releases = models.DecimalField(max_digits=18, decimal_places=4, default=0)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["planning_run", "item", "bucket_date"], name="uq_planning_bucket"
            )
        ]
        ordering = ["item__low_level_code", "item__code", "bucket_date"]


class PlannedOrder(TimeStampedModel):
    class OrderType(models.TextChoices):
        MAKE = "MAKE", "Ordem de produção"
        PURCHASE = "PURCHASE", "Ordem de compra"

    class Status(models.TextChoices):
        PLANNED = "PLANNED", "Planejada"
        FIRM = "FIRM", "Firme"
        CONVERTED = "CONVERTED", "Convertida"
        CANCELLED = "CANCELLED", "Cancelada"

    planning_run = models.ForeignKey(PlanningRun, on_delete=models.CASCADE, related_name="planned_orders")
    item = models.ForeignKey(Item, on_delete=models.PROTECT, related_name="planned_orders")
    order_type = models.CharField(max_length=12, choices=OrderType.choices)
    quantity = models.DecimalField(max_digits=18, decimal_places=4)
    release_date = models.DateField()
    due_date = models.DateField()
    status = models.CharField(max_length=15, choices=Status.choices, default=Status.PLANNED)
    source = models.CharField(max_length=80, default="MRP")
    converted_document_type = models.CharField(max_length=30, blank=True)
    converted_document_id = models.CharField(max_length=64, blank=True)

    class Meta:
        ordering = ["release_date", "item__code"]
        indexes = [models.Index(fields=["planning_run", "order_type", "release_date"], name="ix_plorder_run_type_date")]
        constraints = [
            models.CheckConstraint(condition=models.Q(quantity__gt=0), name="ck_plorder_qty_pos"),
            models.CheckConstraint(
                condition=models.Q(due_date__gte=models.F("release_date")),
                name="ck_plorder_dates",
            ),
        ]

    def __str__(self) -> str:
        return f"{self.item.code}: {self.quantity} em {self.due_date}"


class PeggingRecord(TimeStampedModel):
    planning_run = models.ForeignKey(PlanningRun, on_delete=models.CASCADE, related_name="pegging_records")
    component_item = models.ForeignKey(
        Item, on_delete=models.CASCADE, related_name="component_pegging_records"
    )
    parent_item = models.ForeignKey(Item, on_delete=models.CASCADE, related_name="parent_pegging_records")
    parent_planned_order = models.ForeignKey(
        PlannedOrder, on_delete=models.CASCADE, related_name="component_pegging"
    )
    top_level_item = models.ForeignKey(
        Item, null=True, blank=True, on_delete=models.SET_NULL, related_name="top_level_pegging"
    )
    requirement_date = models.DateField()
    quantity = models.DecimalField(max_digits=18, decimal_places=4)

    class Meta:
        ordering = ["component_item__code", "requirement_date"]
        indexes = [
            models.Index(fields=["planning_run", "component_item", "requirement_date"], name="ix_pegging_component_date"),
            models.Index(fields=["planning_run", "top_level_item"], name="ix_pegging_top_item"),
        ]
        constraints = [
            models.CheckConstraint(condition=models.Q(quantity__gt=0), name="ck_pegging_qty_pos"),
        ]


class PlanningMessage(TimeStampedModel):
    class MessageType(models.TextChoices):
        RELEASE = "RELEASE", "Liberar ordem"
        PAST_DUE = "PAST_DUE", "Data vencida"
        SHORTAGE = "SHORTAGE", "Falta"
        RESCHEDULE_IN = "RESCHEDULE_IN", "Antecipar"
        RESCHEDULE_OUT = "RESCHEDULE_OUT", "Postergar"
        DATA_ERROR = "DATA_ERROR", "Erro de cadastro"

    class Severity(models.TextChoices):
        INFO = "INFO", "Informação"
        WARNING = "WARNING", "Atenção"
        ERROR = "ERROR", "Erro"

    planning_run = models.ForeignKey(PlanningRun, on_delete=models.CASCADE, related_name="messages")
    item = models.ForeignKey(Item, null=True, blank=True, on_delete=models.SET_NULL)
    planned_order = models.ForeignKey(
        PlannedOrder, null=True, blank=True, on_delete=models.CASCADE, related_name="messages"
    )
    message_type = models.CharField(max_length=20, choices=MessageType.choices)
    severity = models.CharField(max_length=10, choices=Severity.choices, default=Severity.INFO)
    action_date = models.DateField(null=True, blank=True)
    suggested_date = models.DateField(null=True, blank=True)
    reference_type = models.CharField(max_length=40, blank=True)
    reference_id = models.CharField(max_length=64, blank=True)
    message = models.TextField()

    class Meta:
        ordering = ["severity", "action_date", "item__code"]
        indexes = [
            models.Index(fields=["planning_run", "severity", "action_date"], name="ix_planmsg_run_sev_date"),
        ]


class CapacityScenario(TimeStampedModel):
    class ScenarioType(models.TextChoices):
        CRP = "CRP", "Planejamento de capacidade"
        CTP = "CTP", "Capable to Promise"
        WHAT_IF = "WHAT_IF", "Simulação what-if"

    class Status(models.TextChoices):
        DRAFT = "DRAFT", "Rascunho"
        RUNNING = "RUNNING", "Executando"
        COMPLETED = "COMPLETED", "Concluído"
        FAILED = "FAILED", "Falhou"

    name = models.CharField(max_length=160)
    scenario_type = models.CharField(max_length=16, choices=ScenarioType.choices)
    plant = models.ForeignKey(Plant, on_delete=models.PROTECT, related_name="capacity_scenarios")
    planning_run = models.ForeignKey(
        PlanningRun,
        null=True,
        blank=True,
        on_delete=models.CASCADE,
        related_name="capacity_scenarios",
    )
    item = models.ForeignKey(
        Item,
        null=True,
        blank=True,
        on_delete=models.PROTECT,
        related_name="capacity_scenarios",
    )
    quantity = models.DecimalField(max_digits=18, decimal_places=4, default=0)
    requested_release_date = models.DateField(null=True, blank=True)
    requested_due_date = models.DateField(null=True, blank=True)
    promised_date = models.DateField(null=True, blank=True)
    feasible = models.BooleanField(null=True, blank=True)
    parameters = models.JSONField(default=dict, blank=True)
    summary = models.JSONField(default=dict, blank=True)
    status = models.CharField(max_length=16, choices=Status.choices, default=Status.DRAFT)
    started_at = models.DateTimeField(null=True, blank=True)
    completed_at = models.DateTimeField(null=True, blank=True)
    error_message = models.TextField(blank=True)

    class Meta:
        ordering = ["-created_at"]
        indexes = [models.Index(fields=["plant", "scenario_type", "status"], name="ix_capscenario_plant_type")]
        constraints = [
            models.CheckConstraint(condition=models.Q(quantity__gte=0), name="ck_capscenario_qty_nonneg"),
        ]

    def __str__(self) -> str:
        return self.name


class CapacityAllocation(TimeStampedModel):
    scenario = models.ForeignKey(
        CapacityScenario, on_delete=models.CASCADE, related_name="allocations"
    )
    work_center = models.ForeignKey(
        "masterdata.WorkCenter", on_delete=models.PROTECT, related_name="capacity_allocations"
    )
    item = models.ForeignKey(Item, on_delete=models.PROTECT, related_name="capacity_allocations")
    source_type = models.CharField(max_length=30)
    source_id = models.CharField(max_length=64)
    operation_sequence = models.PositiveIntegerField(default=0)
    load_date = models.DateField()
    week_start = models.DateField(db_index=True)
    required_hours = models.DecimalField(max_digits=18, decimal_places=4)
    available_hours = models.DecimalField(max_digits=18, decimal_places=4)
    allocated_hours = models.DecimalField(max_digits=18, decimal_places=4)
    overload_hours = models.DecimalField(max_digits=18, decimal_places=4, default=0)
    is_existing_load = models.BooleanField(default=False)

    class Meta:
        ordering = ["load_date", "work_center__code", "source_type", "source_id", "operation_sequence"]
        indexes = [
            models.Index(fields=["scenario", "work_center", "load_date"], name="ix_capalloc_center_date"),
            models.Index(fields=["scenario", "week_start"], name="ix_capalloc_week"),
        ]
        constraints = [
            models.CheckConstraint(condition=models.Q(required_hours__gte=0), name="ck_capalloc_req_nonneg"),
            models.CheckConstraint(condition=models.Q(available_hours__gte=0), name="ck_capalloc_avail_nonneg"),
            models.CheckConstraint(condition=models.Q(allocated_hours__gte=0), name="ck_capalloc_alloc_nonneg"),
            models.CheckConstraint(condition=models.Q(overload_hours__gte=0), name="ck_capalloc_over_nonneg"),
        ]

    @property
    def utilization_percent(self):
        if self.available_hours <= 0:
            return None
        return (self.allocated_hours / self.available_hours) * 100

    def __str__(self) -> str:
        return f"{self.scenario_id}/{self.work_center_id}/{self.load_date}"


class PlanningChange(TimeStampedModel):
    class ChangeType(models.TextChoices):
        DEMAND = "DEMAND", "Demanda"
        STOCK = "STOCK", "Estoque"
        BOM = "BOM", "Estrutura"
        POLICY = "POLICY", "Política"
        SUPPLY = "SUPPLY", "Suprimento"
        ROUTING = "ROUTING", "Roteiro/capacidade"

    class Status(models.TextChoices):
        PENDING = "PENDING", "Pendente"
        PROCESSED = "PROCESSED", "Processada"
        CANCELLED = "CANCELLED", "Cancelada"

    plant = models.ForeignKey(Plant, on_delete=models.CASCADE, related_name="planning_changes")
    item = models.ForeignKey(
        Item, null=True, blank=True, on_delete=models.CASCADE, related_name="planning_changes"
    )
    change_type = models.CharField(max_length=16, choices=ChangeType.choices)
    source_type = models.CharField(max_length=50)
    source_id = models.CharField(max_length=80)
    idempotency_key = models.CharField(max_length=180, unique=True)
    payload = models.JSONField(default=dict, blank=True)
    status = models.CharField(max_length=16, choices=Status.choices, default=Status.PENDING)
    processed_at = models.DateTimeField(null=True, blank=True)
    planning_run = models.ForeignKey(
        PlanningRun,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="processed_changes",
    )

    class Meta:
        ordering = ["created_at", "id"]
        indexes = [models.Index(fields=["plant", "status", "created_at"], name="ix_plchange_status_time")]

    def __str__(self) -> str:
        return f"{self.plant.code}/{self.change_type}/{self.source_type}/{self.source_id}"

class DemandPeggingAllocation(TimeStampedModel):
    """Source-aware pegging persisted by MRP for exact commercial traceability."""
    class SourceType(models.TextChoices):
        SALES_ORDER_LINE = "SALES_ORDER_LINE", "Linha de pedido"
        MPS = "MPS", "MPS"
        FORECAST = "FORECAST", "Previsão"
        SAFETY_STOCK = "SAFETY_STOCK", "Estoque de segurança"

    planned_order = models.ForeignKey(PlannedOrder, on_delete=models.CASCADE, related_name="demand_allocations")
    source_type = models.CharField(max_length=24, choices=SourceType.choices)
    sales_order_line = models.ForeignKey("demand.SalesOrderLine", null=True, blank=True, on_delete=models.CASCADE, related_name="mrp_allocations")
    source_id = models.PositiveIntegerField(null=True, blank=True)
    required_date = models.DateField()
    quantity = models.DecimalField(max_digits=18, decimal_places=4)
    top_level_item = models.ForeignKey(Item, null=True, blank=True, on_delete=models.SET_NULL, related_name="demand_pegging_allocations")
    details = models.JSONField(default=dict, blank=True)

    class Meta:
        ordering = ["planned_order", "required_date", "source_type", "source_id"]
        indexes = [models.Index(fields=["source_type", "source_id"], name="ix_dempeg_source"), models.Index(fields=["planned_order", "source_type"], name="ix_dempeg_order_source")]
        constraints = [models.CheckConstraint(condition=models.Q(quantity__gt=0), name="ck_dempeg_qty_pos")]
