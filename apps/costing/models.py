from django.conf import settings
from django.db import models
from django.utils import timezone
from apps.common.models import Plant, TimeStampedModel
from apps.masterdata.models import Item, WorkCenter
from apps.production.models import WorkOrder
from apps.purchasing.models import GoodsReceipt


class CostVersion(TimeStampedModel):
    class Status(models.TextChoices):
        DRAFT = "DRAFT", "Rascunho"
        CALCULATED = "CALCULATED", "Calculada"
        APPROVED = "APPROVED", "Aprovada"
        ACTIVE = "ACTIVE", "Ativa"
        CLOSED = "CLOSED", "Encerrada"

    plant = models.ForeignKey(Plant, on_delete=models.PROTECT, related_name="cost_versions")
    code = models.CharField(max_length=40)
    description = models.CharField(max_length=200, blank=True)
    effective_from = models.DateField()
    effective_to = models.DateField(null=True, blank=True)
    status = models.CharField(max_length=16, choices=Status.choices, default=Status.DRAFT, db_index=True)
    calculated_at = models.DateTimeField(null=True, blank=True)
    approved_at = models.DateTimeField(null=True, blank=True)
    approved_by = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL, related_name="approved_cost_versions")

    class Meta:
        constraints = [models.UniqueConstraint(fields=["plant", "code"], name="uq_cost_version_plant_code")]
        ordering = ["-effective_from", "code"]


class WorkCenterRate(TimeStampedModel):
    cost_version = models.ForeignKey(CostVersion, on_delete=models.CASCADE, related_name="work_center_rates")
    work_center = models.ForeignKey(WorkCenter, on_delete=models.PROTECT, related_name="cost_rates")
    setup_rate = models.DecimalField(max_digits=18, decimal_places=4, default=0)
    labor_rate = models.DecimalField(max_digits=18, decimal_places=4, default=0)
    machine_rate = models.DecimalField(max_digits=18, decimal_places=4, default=0)
    overhead_rate = models.DecimalField(max_digits=18, decimal_places=4, default=0)

    class Meta:
        constraints = [models.UniqueConstraint(fields=["cost_version", "work_center"], name="uq_cost_wc_rate")]


class ItemCost(TimeStampedModel):
    cost_version = models.ForeignKey(CostVersion, on_delete=models.CASCADE, related_name="item_costs")
    item = models.ForeignKey(Item, on_delete=models.PROTECT, related_name="cost_records")
    material_cost = models.DecimalField(max_digits=18, decimal_places=4, default=0)
    setup_cost = models.DecimalField(max_digits=18, decimal_places=4, default=0)
    labor_cost = models.DecimalField(max_digits=18, decimal_places=4, default=0)
    machine_cost = models.DecimalField(max_digits=18, decimal_places=4, default=0)
    overhead_cost = models.DecimalField(max_digits=18, decimal_places=4, default=0)
    subcontract_cost = models.DecimalField(max_digits=18, decimal_places=4, default=0)
    total_cost = models.DecimalField(max_digits=18, decimal_places=4, default=0, db_index=True)
    level = models.PositiveIntegerField(default=0)
    calculation_details = models.JSONField(default=dict, blank=True)

    class Meta:
        constraints = [models.UniqueConstraint(fields=["cost_version", "item"], name="uq_item_cost_version")]
        ordering = ["item__low_level_code", "item__code"]


class CostRollupRun(TimeStampedModel):
    class Status(models.TextChoices):
        PENDING = "PENDING", "Pendente"
        RUNNING = "RUNNING", "Executando"
        COMPLETED = "COMPLETED", "Concluída"
        FAILED = "FAILED", "Falhou"

    cost_version = models.ForeignKey(CostVersion, on_delete=models.CASCADE, related_name="rollup_runs")
    status = models.CharField(max_length=16, choices=Status.choices, default=Status.PENDING)
    started_at = models.DateTimeField(null=True, blank=True)
    finished_at = models.DateTimeField(null=True, blank=True)
    items_calculated = models.PositiveIntegerField(default=0)
    error_message = models.TextField(blank=True)


class WorkOrderCost(TimeStampedModel):
    class CostType(models.TextChoices):
        PLANNED = "PLANNED", "Planejado"
        ACTUAL = "ACTUAL", "Real"

    work_order = models.ForeignKey(WorkOrder, on_delete=models.CASCADE, related_name="cost_summaries")
    cost_version = models.ForeignKey(CostVersion, on_delete=models.PROTECT, related_name="work_order_costs")
    cost_type = models.CharField(max_length=12, choices=CostType.choices)
    quantity_basis = models.DecimalField(max_digits=18, decimal_places=4)
    material_cost = models.DecimalField(max_digits=18, decimal_places=4, default=0)
    setup_cost = models.DecimalField(max_digits=18, decimal_places=4, default=0)
    labor_cost = models.DecimalField(max_digits=18, decimal_places=4, default=0)
    machine_cost = models.DecimalField(max_digits=18, decimal_places=4, default=0)
    overhead_cost = models.DecimalField(max_digits=18, decimal_places=4, default=0)
    subcontract_cost = models.DecimalField(max_digits=18, decimal_places=4, default=0)
    scrap_cost = models.DecimalField(max_digits=18, decimal_places=4, default=0)
    rework_cost = models.DecimalField(max_digits=18, decimal_places=4, default=0)
    total_cost = models.DecimalField(max_digits=18, decimal_places=4, default=0)
    unit_cost = models.DecimalField(max_digits=18, decimal_places=6, default=0)
    calculated_at = models.DateTimeField()
    calculation_details = models.JSONField(default=dict, blank=True)

    class Meta:
        constraints = [models.UniqueConstraint(fields=["work_order", "cost_type"], name="uq_wo_cost_type")]
        indexes = [models.Index(fields=["cost_version", "cost_type"], name="ix_wocost_version_type")]


class WorkOrderCostLine(TimeStampedModel):
    class Category(models.TextChoices):
        MATERIAL = "MATERIAL", "Material"
        SETUP = "SETUP", "Setup"
        LABOR = "LABOR", "Mão de obra"
        MACHINE = "MACHINE", "Máquina"
        OVERHEAD = "OVERHEAD", "Indireto"
        SUBCONTRACT = "SUBCONTRACT", "Subcontratação"
        SCRAP = "SCRAP", "Refugo"
        REWORK = "REWORK", "Retrabalho"

    work_order_cost = models.ForeignKey(WorkOrderCost, on_delete=models.CASCADE, related_name="lines")
    category = models.CharField(max_length=20, choices=Category.choices)
    item = models.ForeignKey(Item, null=True, blank=True, on_delete=models.PROTECT, related_name="work_order_cost_lines")
    work_center = models.ForeignKey(WorkCenter, null=True, blank=True, on_delete=models.PROTECT, related_name="work_order_cost_lines")
    reference = models.CharField(max_length=80, blank=True)
    quantity = models.DecimalField(max_digits=18, decimal_places=4, default=0)
    hours = models.DecimalField(max_digits=18, decimal_places=4, default=0)
    rate = models.DecimalField(max_digits=18, decimal_places=4, default=0)
    amount = models.DecimalField(max_digits=18, decimal_places=4, default=0)
    details = models.JSONField(default=dict, blank=True)

    class Meta:
        ordering = ["category", "id"]


class CostVariance(TimeStampedModel):
    class VarianceType(models.TextChoices):
        MATERIAL_PRICE = "MATERIAL_PRICE", "Preço de material"
        MATERIAL_USAGE = "MATERIAL_USAGE", "Consumo de material"
        LABOR_RATE = "LABOR_RATE", "Taxa de mão de obra"
        LABOR_EFFICIENCY = "LABOR_EFFICIENCY", "Eficiência de mão de obra"
        MACHINE_EFFICIENCY = "MACHINE_EFFICIENCY", "Eficiência de máquina"
        SETUP = "SETUP", "Setup"
        OVERHEAD = "OVERHEAD", "Custos indiretos"
        SCRAP = "SCRAP", "Refugo"
        TOTAL = "TOTAL", "Total"

    work_order = models.ForeignKey(WorkOrder, on_delete=models.CASCADE, related_name="cost_variances")
    variance_type = models.CharField(max_length=30, choices=VarianceType.choices)
    planned_amount = models.DecimalField(max_digits=18, decimal_places=4, default=0)
    actual_amount = models.DecimalField(max_digits=18, decimal_places=4, default=0)
    variance_amount = models.DecimalField(max_digits=18, decimal_places=4, default=0)
    favorable = models.BooleanField(default=False)
    details = models.JSONField(default=dict, blank=True)

    class Meta:
        constraints = [models.UniqueConstraint(fields=["work_order", "variance_type"], name="uq_wo_variance_type")]


class PurchasePriceVariance(TimeStampedModel):
    goods_receipt = models.OneToOneField(GoodsReceipt, on_delete=models.CASCADE, related_name="price_variance")
    cost_version = models.ForeignKey(CostVersion, on_delete=models.PROTECT, related_name="purchase_price_variances")
    standard_unit_cost = models.DecimalField(max_digits=18, decimal_places=4)
    actual_unit_price = models.DecimalField(max_digits=18, decimal_places=4)
    quantity = models.DecimalField(max_digits=18, decimal_places=4)
    variance_amount = models.DecimalField(max_digits=18, decimal_places=4)
    favorable = models.BooleanField(default=False)

    class Meta:
        ordering = ["-created_at"]

class AccountingPeriod(TimeStampedModel):
    class Status(models.TextChoices):
        OPEN = "OPEN", "Aberto"
        CLOSING = "CLOSING", "Em fechamento"
        CLOSED = "CLOSED", "Fechado"

    plant = models.ForeignKey(Plant, on_delete=models.PROTECT, related_name="accounting_periods")
    code = models.CharField(max_length=20)
    start_date = models.DateField()
    end_date = models.DateField()
    status = models.CharField(max_length=12, choices=Status.choices, default=Status.OPEN, db_index=True)
    cost_version = models.ForeignKey(CostVersion, null=True, blank=True, on_delete=models.PROTECT, related_name="accounting_periods")
    closed_at = models.DateTimeField(null=True, blank=True)
    closed_by = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL, related_name="closed_accounting_periods")

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=["plant", "code"], name="uq_cost_period_plant_code"),
            models.CheckConstraint(condition=models.Q(end_date__gte=models.F("start_date")), name="ck_cost_period_dates"),
        ]
        ordering = ["-start_date", "plant__code"]


class InventoryValuationSnapshot(TimeStampedModel):
    class ValuationMethod(models.TextChoices):
        STANDARD = "STANDARD", "Custo padrão"
        MOVING_AVERAGE = "MOVING_AVERAGE", "Custo médio móvel"
        ACTUAL = "ACTUAL", "Custo real"

    period = models.ForeignKey(AccountingPeriod, on_delete=models.CASCADE, related_name="inventory_snapshots")
    cost_version = models.ForeignKey(CostVersion, on_delete=models.PROTECT, related_name="inventory_snapshots")
    valuation_method = models.CharField(max_length=20, choices=ValuationMethod.choices, default=ValuationMethod.STANDARD)
    as_of = models.DateTimeField()
    total_quantity = models.DecimalField(max_digits=22, decimal_places=4, default=0)
    total_value = models.DecimalField(max_digits=22, decimal_places=4, default=0)

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=["period", "valuation_method"], name="uq_invvaluation_period_method")
        ]
        ordering = ["-as_of"]


class InventoryValuationLine(TimeStampedModel):
    snapshot = models.ForeignKey(InventoryValuationSnapshot, on_delete=models.CASCADE, related_name="lines")
    item = models.ForeignKey(Item, on_delete=models.PROTECT, related_name="inventory_valuation_lines")
    location = models.ForeignKey("inventory.Location", on_delete=models.PROTECT, related_name="valuation_lines")
    quantity = models.DecimalField(max_digits=18, decimal_places=4)
    unit_cost = models.DecimalField(max_digits=18, decimal_places=6, default=0)
    total_value = models.DecimalField(max_digits=22, decimal_places=4, default=0)

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=["snapshot", "item", "location"], name="uq_invvaluation_line")
        ]
        ordering = ["item__code", "location__code"]


class WIPSnapshot(TimeStampedModel):
    period = models.ForeignKey(AccountingPeriod, on_delete=models.CASCADE, related_name="wip_snapshots")
    cost_version = models.ForeignKey(CostVersion, on_delete=models.PROTECT, related_name="wip_snapshots")
    as_of = models.DateTimeField()
    total_value = models.DecimalField(max_digits=22, decimal_places=4, default=0)

    class Meta:
        constraints = [models.UniqueConstraint(fields=["period"], name="uq_wip_period")]
        ordering = ["-as_of"]


class WIPLine(TimeStampedModel):
    snapshot = models.ForeignKey(WIPSnapshot, on_delete=models.CASCADE, related_name="lines")
    work_order = models.ForeignKey(WorkOrder, on_delete=models.PROTECT, related_name="wip_lines")
    material_cost = models.DecimalField(max_digits=18, decimal_places=4, default=0)
    setup_cost = models.DecimalField(max_digits=18, decimal_places=4, default=0)
    labor_cost = models.DecimalField(max_digits=18, decimal_places=4, default=0)
    machine_cost = models.DecimalField(max_digits=18, decimal_places=4, default=0)
    overhead_cost = models.DecimalField(max_digits=18, decimal_places=4, default=0)
    subcontract_cost = models.DecimalField(max_digits=18, decimal_places=4, default=0)
    scrap_cost = models.DecimalField(max_digits=18, decimal_places=4, default=0)
    completed_value = models.DecimalField(max_digits=18, decimal_places=4, default=0)
    wip_value = models.DecimalField(max_digits=18, decimal_places=4, default=0)

    class Meta:
        constraints = [models.UniqueConstraint(fields=["snapshot", "work_order"], name="uq_wip_line")]
        ordering = ["work_order__number"]


class MovingAverageCostBalance(TimeStampedModel):
    """Saldo financeiro do item por planta para custo médio móvel."""
    plant = models.ForeignKey(Plant, on_delete=models.PROTECT, related_name="moving_average_costs")
    item = models.ForeignKey(Item, on_delete=models.PROTECT, related_name="moving_average_costs")
    quantity = models.DecimalField(max_digits=22, decimal_places=4, default=0)
    inventory_value = models.DecimalField(max_digits=22, decimal_places=4, default=0)
    average_unit_cost = models.DecimalField(max_digits=22, decimal_places=6, default=0)
    last_transaction = models.ForeignKey("inventory.InventoryTransaction", null=True, blank=True, on_delete=models.SET_NULL, related_name="moving_average_balances")

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=["plant", "item"], name="uq_mavg_plant_item"),
            models.CheckConstraint(condition=models.Q(quantity__gte=0), name="ck_mavg_qty_nonneg"),
            models.CheckConstraint(condition=models.Q(inventory_value__gte=0), name="ck_mavg_value_nonneg"),
        ]
        indexes = [models.Index(fields=["plant", "item"], name="ix_mavg_plant_item")]


class InventoryCostMovement(TimeStampedModel):
    class MovementType(models.TextChoices):
        RECEIPT = "RECEIPT", "Entrada"
        ISSUE = "ISSUE", "Saída"
        ADJUSTMENT = "ADJUSTMENT", "Ajuste"
        REVALUATION = "REVALUATION", "Reavaliação"
        TRANSFER = "TRANSFER", "Transferência"

    transaction = models.OneToOneField("inventory.InventoryTransaction", null=True, blank=True, on_delete=models.PROTECT, related_name="cost_movement")
    plant = models.ForeignKey(Plant, on_delete=models.PROTECT, related_name="inventory_cost_movements")
    item = models.ForeignKey(Item, on_delete=models.PROTECT, related_name="inventory_cost_movements")
    movement_type = models.CharField(max_length=20, choices=MovementType.choices)
    quantity = models.DecimalField(max_digits=22, decimal_places=4)
    unit_cost = models.DecimalField(max_digits=22, decimal_places=6, default=0)
    value = models.DecimalField(max_digits=22, decimal_places=4, default=0)
    quantity_after = models.DecimalField(max_digits=22, decimal_places=4, default=0)
    value_after = models.DecimalField(max_digits=22, decimal_places=4, default=0)
    average_cost_after = models.DecimalField(max_digits=22, decimal_places=6, default=0)
    reference_type = models.CharField(max_length=40, blank=True)
    reference_id = models.CharField(max_length=64, blank=True)
    posted_at = models.DateTimeField(default=timezone.now, db_index=True)
    details = models.JSONField(default=dict, blank=True)

    class Meta:
        ordering = ["posted_at", "id"]
        indexes = [models.Index(fields=["plant", "item", "posted_at"], name="ix_costmov_item_time")]


class CostLedgerEntry(TimeStampedModel):
    class EntryType(models.TextChoices):
        INVENTORY = "INVENTORY", "Estoque"
        WIP = "WIP", "Produção em processo"
        VARIANCE = "VARIANCE", "Variação"
        ADJUSTMENT = "ADJUSTMENT", "Ajuste"
        PERIOD_CLOSE = "PERIOD_CLOSE", "Fechamento"

    period = models.ForeignKey(AccountingPeriod, null=True, blank=True, on_delete=models.PROTECT, related_name="ledger_entries")
    plant = models.ForeignKey(Plant, on_delete=models.PROTECT, related_name="cost_ledger_entries")
    entry_type = models.CharField(max_length=20, choices=EntryType.choices, db_index=True)
    posting_date = models.DateField(db_index=True)
    account_code = models.CharField(max_length=40)
    debit = models.DecimalField(max_digits=22, decimal_places=4, default=0)
    credit = models.DecimalField(max_digits=22, decimal_places=4, default=0)
    reference_type = models.CharField(max_length=40, blank=True)
    reference_id = models.CharField(max_length=64, blank=True)
    description = models.CharField(max_length=240, blank=True)
    idempotency_key = models.CharField(max_length=180, unique=True)
    details = models.JSONField(default=dict, blank=True)

    class Meta:
        ordering = ["posting_date", "id"]
        constraints = [
            models.CheckConstraint(condition=models.Q(debit__gte=0), name="ck_costledger_debit_nonneg"),
            models.CheckConstraint(condition=models.Q(credit__gte=0), name="ck_costledger_credit_nonneg"),
            models.CheckConstraint(condition=(models.Q(debit__gt=0, credit=0) | models.Q(credit__gt=0, debit=0)), name="ck_costledger_one_side"),
        ]
        indexes = [models.Index(fields=["plant", "posting_date", "entry_type"], name="ix_costledger_plant_date")]


class PeriodVariancePosting(TimeStampedModel):
    period = models.ForeignKey(AccountingPeriod, on_delete=models.CASCADE, related_name="variance_postings")
    variance_type = models.CharField(max_length=30, choices=CostVariance.VarianceType.choices)
    amount = models.DecimalField(max_digits=22, decimal_places=4, default=0)
    favorable = models.BooleanField(default=False)
    posted_at = models.DateTimeField(null=True, blank=True)
    ledger_debit = models.ForeignKey(CostLedgerEntry, null=True, blank=True, on_delete=models.PROTECT, related_name="variance_debits")
    ledger_credit = models.ForeignKey(CostLedgerEntry, null=True, blank=True, on_delete=models.PROTECT, related_name="variance_credits")

    class Meta:
        constraints = [models.UniqueConstraint(fields=["period", "variance_type"], name="uq_period_variance_type")]
        ordering = ["variance_type"]


class InventoryRevaluation(TimeStampedModel):
    """Reavaliação financeira de um item sem alterar a quantidade física."""
    class Method(models.TextChoices):
        STANDARD = "STANDARD", "Custo padrão"
        MOVING_AVERAGE = "MOVING_AVERAGE", "Custo médio móvel"
        MANUAL = "MANUAL", "Manual"

    plant = models.ForeignKey(Plant, on_delete=models.PROTECT, related_name="inventory_revaluations")
    item = models.ForeignKey(Item, on_delete=models.PROTECT, related_name="inventory_revaluations")
    period = models.ForeignKey(AccountingPeriod, null=True, blank=True, on_delete=models.PROTECT, related_name="inventory_revaluations")
    method = models.CharField(max_length=20, choices=Method.choices, default=Method.MANUAL)
    quantity = models.DecimalField(max_digits=22, decimal_places=4, default=0)
    old_unit_cost = models.DecimalField(max_digits=22, decimal_places=6, default=0)
    new_unit_cost = models.DecimalField(max_digits=22, decimal_places=6, default=0)
    old_value = models.DecimalField(max_digits=22, decimal_places=4, default=0)
    new_value = models.DecimalField(max_digits=22, decimal_places=4, default=0)
    variance_value = models.DecimalField(max_digits=22, decimal_places=4, default=0)
    reason = models.CharField(max_length=240)
    posted_at = models.DateTimeField(default=timezone.now, db_index=True)
    posted_by = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL, related_name="posted_inventory_revaluations")
    ledger_debit = models.ForeignKey(CostLedgerEntry, null=True, blank=True, on_delete=models.PROTECT, related_name="revaluation_debits")
    ledger_credit = models.ForeignKey(CostLedgerEntry, null=True, blank=True, on_delete=models.PROTECT, related_name="revaluation_credits")
    idempotency_key = models.CharField(max_length=180, unique=True)

    class Meta:
        ordering = ["-posted_at", "item__code"]
        indexes = [models.Index(fields=["plant", "item", "posted_at"], name="ix_reval_plant_item_time")]


class FinancialInventoryAdjustment(TimeStampedModel):
    """Ajuste financeiro controlado; pode ou não acompanhar ajuste físico já lançado."""
    class Status(models.TextChoices):
        DRAFT = "DRAFT", "Rascunho"
        POSTED = "POSTED", "Contabilizado"
        REVERSED = "REVERSED", "Estornado"

    plant = models.ForeignKey(Plant, on_delete=models.PROTECT, related_name="financial_inventory_adjustments")
    item = models.ForeignKey(Item, on_delete=models.PROTECT, related_name="financial_inventory_adjustments")
    location = models.ForeignKey("inventory.Location", null=True, blank=True, on_delete=models.PROTECT, related_name="financial_adjustments")
    inventory_transaction = models.ForeignKey("inventory.InventoryTransaction", null=True, blank=True, on_delete=models.PROTECT, related_name="financial_adjustments")
    period = models.ForeignKey(AccountingPeriod, null=True, blank=True, on_delete=models.PROTECT, related_name="financial_inventory_adjustments")
    quantity_delta = models.DecimalField(max_digits=22, decimal_places=4, default=0)
    value_delta = models.DecimalField(max_digits=22, decimal_places=4)
    reason_code = models.CharField(max_length=40, default="OTHER")
    reason = models.CharField(max_length=240)
    status = models.CharField(max_length=12, choices=Status.choices, default=Status.DRAFT, db_index=True)
    posted_at = models.DateTimeField(null=True, blank=True)
    posted_by = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL, related_name="posted_financial_inventory_adjustments")
    ledger_debit = models.ForeignKey(CostLedgerEntry, null=True, blank=True, on_delete=models.PROTECT, related_name="adjustment_debits")
    ledger_credit = models.ForeignKey(CostLedgerEntry, null=True, blank=True, on_delete=models.PROTECT, related_name="adjustment_credits")
    idempotency_key = models.CharField(max_length=180, unique=True)

    class Meta:
        ordering = ["-created_at"]
        indexes = [models.Index(fields=["plant", "status", "created_at"], name="ix_finadj_plant_status")]
        constraints = [models.CheckConstraint(condition=~models.Q(value_delta=0), name="ck_finadj_value_nonzero")]


class LotActualCost(TimeStampedModel):
    lot = models.OneToOneField("traceability.InventoryLot", on_delete=models.CASCADE, related_name="actual_cost")
    cost_version = models.ForeignKey(CostVersion, null=True, blank=True, on_delete=models.PROTECT, related_name="lot_actual_costs")
    quantity_basis = models.DecimalField(max_digits=22, decimal_places=4, default=0)
    purchase_cost = models.DecimalField(max_digits=22, decimal_places=4, default=0)
    material_cost = models.DecimalField(max_digits=22, decimal_places=4, default=0)
    conversion_cost = models.DecimalField(max_digits=22, decimal_places=4, default=0)
    quality_cost = models.DecimalField(max_digits=22, decimal_places=4, default=0)
    scrap_cost = models.DecimalField(max_digits=22, decimal_places=4, default=0)
    total_cost = models.DecimalField(max_digits=22, decimal_places=4, default=0)
    unit_cost = models.DecimalField(max_digits=22, decimal_places=6, default=0)
    calculated_at = models.DateTimeField(default=timezone.now)
    details = models.JSONField(default=dict, blank=True)

    class Meta:
        ordering = ["lot__item__code", "lot__lot_number"]


class SerialActualCost(TimeStampedModel):
    serial = models.OneToOneField("traceability.SerialNumber", on_delete=models.CASCADE, related_name="actual_cost")
    lot_cost = models.DecimalField(max_digits=22, decimal_places=4, default=0)
    component_cost = models.DecimalField(max_digits=22, decimal_places=4, default=0)
    conversion_cost = models.DecimalField(max_digits=22, decimal_places=4, default=0)
    total_cost = models.DecimalField(max_digits=22, decimal_places=4, default=0)
    calculated_at = models.DateTimeField(default=timezone.now)
    details = models.JSONField(default=dict, blank=True)

    class Meta:
        ordering = ["serial__item__code", "serial__serial_number"]


class InventoryReconciliationRun(TimeStampedModel):
    class Status(models.TextChoices):
        RUNNING = "RUNNING", "Executando"
        COMPLETED = "COMPLETED", "Concluída"
        RECONCILED = "RECONCILED", "Conciliada"

    plant = models.ForeignKey(Plant, on_delete=models.PROTECT, related_name="inventory_reconciliation_runs")
    period = models.ForeignKey(AccountingPeriod, null=True, blank=True, on_delete=models.PROTECT, related_name="reconciliation_runs")
    as_of = models.DateTimeField(default=timezone.now)
    status = models.CharField(max_length=16, choices=Status.choices, default=Status.RUNNING)
    physical_quantity = models.DecimalField(max_digits=22, decimal_places=4, default=0)
    financial_quantity = models.DecimalField(max_digits=22, decimal_places=4, default=0)
    physical_value = models.DecimalField(max_digits=22, decimal_places=4, default=0)
    financial_value = models.DecimalField(max_digits=22, decimal_places=4, default=0)
    quantity_variance = models.DecimalField(max_digits=22, decimal_places=4, default=0)
    value_variance = models.DecimalField(max_digits=22, decimal_places=4, default=0)
    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL, related_name="inventory_reconciliation_runs")

    class Meta:
        ordering = ["-as_of"]


class InventoryReconciliationLine(TimeStampedModel):
    run = models.ForeignKey(InventoryReconciliationRun, on_delete=models.CASCADE, related_name="lines")
    item = models.ForeignKey(Item, on_delete=models.PROTECT, related_name="inventory_reconciliation_lines")
    physical_quantity = models.DecimalField(max_digits=22, decimal_places=4, default=0)
    financial_quantity = models.DecimalField(max_digits=22, decimal_places=4, default=0)
    unit_cost = models.DecimalField(max_digits=22, decimal_places=6, default=0)
    physical_value = models.DecimalField(max_digits=22, decimal_places=4, default=0)
    financial_value = models.DecimalField(max_digits=22, decimal_places=4, default=0)
    quantity_variance = models.DecimalField(max_digits=22, decimal_places=4, default=0)
    value_variance = models.DecimalField(max_digits=22, decimal_places=4, default=0)
    reconciled = models.BooleanField(default=False)
    notes = models.CharField(max_length=240, blank=True)

    class Meta:
        constraints = [models.UniqueConstraint(fields=["run", "item"], name="uq_reconciliation_run_item")]
        ordering = ["item__code"]

class PeriodCloseRun(TimeStampedModel):
    class Status(models.TextChoices):
        RUNNING = "RUNNING", "Executando"
        COMPLETED = "COMPLETED", "Concluído"
        FAILED = "FAILED", "Falhou"
        REVERSED = "REVERSED", "Estornado"

    period = models.ForeignKey(AccountingPeriod, on_delete=models.PROTECT, related_name="close_runs")
    status = models.CharField(max_length=16, choices=Status.choices, default=Status.RUNNING, db_index=True)
    started_at = models.DateTimeField(default=timezone.now)
    finished_at = models.DateTimeField(null=True, blank=True)
    inventory_value = models.DecimalField(max_digits=22, decimal_places=4, default=0)
    wip_value = models.DecimalField(max_digits=22, decimal_places=4, default=0)
    variance_value = models.DecimalField(max_digits=22, decimal_places=4, default=0)
    ledger_debits = models.DecimalField(max_digits=22, decimal_places=4, default=0)
    ledger_credits = models.DecimalField(max_digits=22, decimal_places=4, default=0)
    reconciliation_quantity_variance = models.DecimalField(max_digits=22, decimal_places=4, default=0)
    reconciliation_value_variance = models.DecimalField(max_digits=22, decimal_places=4, default=0)
    strict_reconciliation = models.BooleanField(default=False)
    error_message = models.TextField(blank=True)
    executed_by = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL, related_name="cost_period_close_runs")

    class Meta:
        ordering = ["-started_at"]
        indexes = [models.Index(fields=["period", "status", "started_at"], name="ix_close_run_period_status")]


class PeriodReopenRequest(TimeStampedModel):
    class Status(models.TextChoices):
        REQUESTED = "REQUESTED", "Solicitada"
        APPROVED = "APPROVED", "Aprovada"
        REJECTED = "REJECTED", "Rejeitada"
        APPLIED = "APPLIED", "Aplicada"
        CANCELLED = "CANCELLED", "Cancelada"

    period = models.ForeignKey(AccountingPeriod, on_delete=models.PROTECT, related_name="reopen_requests")
    status = models.CharField(max_length=16, choices=Status.choices, default=Status.REQUESTED, db_index=True)
    reason = models.TextField()
    requested_by = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL, related_name="requested_cost_period_reopens")
    requested_at = models.DateTimeField(default=timezone.now)
    decided_by = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL, related_name="decided_cost_period_reopens")
    decided_at = models.DateTimeField(null=True, blank=True)
    decision_notes = models.TextField(blank=True)
    applied_by = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL, related_name="applied_cost_period_reopens")
    applied_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ["-requested_at"]
        indexes = [models.Index(fields=["period", "status"], name="ix_reopen_period_status")]


class CostLedgerReversal(TimeStampedModel):
    original_entry = models.OneToOneField(CostLedgerEntry, on_delete=models.PROTECT, related_name="reversal_record")
    reversal_entry = models.OneToOneField(CostLedgerEntry, on_delete=models.PROTECT, related_name="reverses_record")
    reason = models.CharField(max_length=240)
    reversed_by = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL, related_name="cost_ledger_reversals")
    reversed_at = models.DateTimeField(default=timezone.now)

    class Meta:
        ordering = ["-reversed_at"]


class CostPeriodAudit(TimeStampedModel):
    class Action(models.TextChoices):
        CLOSE_STARTED = "CLOSE_STARTED", "Fechamento iniciado"
        CLOSE_COMPLETED = "CLOSE_COMPLETED", "Fechamento concluído"
        CLOSE_FAILED = "CLOSE_FAILED", "Falha no fechamento"
        REOPEN_REQUESTED = "REOPEN_REQUESTED", "Reabertura solicitada"
        REOPEN_APPROVED = "REOPEN_APPROVED", "Reabertura aprovada"
        REOPEN_REJECTED = "REOPEN_REJECTED", "Reabertura rejeitada"
        REOPEN_APPLIED = "REOPEN_APPLIED", "Reabertura aplicada"
        LEDGER_REVERSED = "LEDGER_REVERSED", "Lançamento estornado"

    period = models.ForeignKey(AccountingPeriod, on_delete=models.PROTECT, related_name="cost_audit_entries")
    action = models.CharField(max_length=32, choices=Action.choices, db_index=True)
    actor = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL, related_name="cost_period_audit_entries")
    occurred_at = models.DateTimeField(default=timezone.now, db_index=True)
    reference_type = models.CharField(max_length=40, blank=True)
    reference_id = models.CharField(max_length=64, blank=True)
    payload = models.JSONField(default=dict, blank=True)

    class Meta:
        ordering = ["-occurred_at", "-id"]
        indexes = [models.Index(fields=["period", "action", "occurred_at"], name="ix_costaudit_period_action")]

    def save(self, *args, **kwargs):
        if self.pk and type(self).objects.filter(pk=self.pk).exists():
            from django.core.exceptions import ValidationError
            raise ValidationError("A trilha de auditoria de custos é imutável.")
        return super().save(*args, **kwargs)

    def delete(self, *args, **kwargs):
        from django.core.exceptions import ValidationError
        raise ValidationError("A trilha de auditoria de custos não pode ser excluída.")
