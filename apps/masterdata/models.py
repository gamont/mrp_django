from decimal import Decimal
from django.core.exceptions import ValidationError
from django.db import models
from apps.common.models import Plant, TimeStampedModel


class Item(TimeStampedModel):
    class ItemType(models.TextChoices):
        FINISHED = "FINISHED", "Produto acabado"
        ASSEMBLY = "ASSEMBLY", "Conjunto"
        MANUFACTURED = "MANUFACTURED", "Fabricado"
        PURCHASED = "PURCHASED", "Comprado"
        RAW = "RAW", "Matéria-prima"
        SUBCONTRACTED = "SUBCONTRACTED", "Subcontratado"

    class Status(models.TextChoices):
        NEW = "NEW", "Novo"
        ACTIVE = "ACTIVE", "Em produção"
        SUPERSEDED = "SUPERSEDED", "Substituído"
        OBSOLETE = "OBSOLETE", "Obsoleto"

    code = models.CharField(max_length=50, unique=True)
    description = models.CharField(max_length=240)
    item_type = models.CharField(max_length=20, choices=ItemType.choices)
    uom = models.CharField(max_length=10, default="UN")
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.ACTIVE)
    low_level_code = models.PositiveIntegerField(default=0, db_index=True)
    standard_cost = models.DecimalField(max_digits=18, decimal_places=4, default=0)
    superseded_by = models.ForeignKey(
        "self", null=True, blank=True, on_delete=models.SET_NULL, related_name="supersedes"
    )
    is_active = models.BooleanField(default=True)

    class Meta:
        ordering = ["code"]
        indexes = [models.Index(fields=["item_type", "is_active"], name="ix_item_type_active")]
        constraints = [
            models.CheckConstraint(condition=models.Q(standard_cost__gte=0), name="ck_item_cost_nonneg"),
        ]

    def __str__(self) -> str:
        return f"{self.code} - {self.description}"


class ItemPlantPolicy(TimeStampedModel):
    class SourceType(models.TextChoices):
        MAKE = "MAKE", "Fabricar"
        BUY = "BUY", "Comprar"

    class LotSizingRule(models.TextChoices):
        LOT_FOR_LOT = "L4L", "Lote por lote"
        FIXED = "FIXED", "Quantidade fixa"
        MULTIPLE = "MULTIPLE", "Múltiplo"
        MINIMUM = "MINIMUM", "Quantidade mínima"

    plant = models.ForeignKey(Plant, on_delete=models.CASCADE, related_name="item_policies")
    item = models.ForeignKey(Item, on_delete=models.CASCADE, related_name="plant_policies")
    source_type = models.CharField(max_length=10, choices=SourceType.choices)
    lead_time_days = models.PositiveIntegerField(default=0)
    safety_stock = models.DecimalField(max_digits=18, decimal_places=4, default=0)
    lot_sizing_rule = models.CharField(
        max_length=12, choices=LotSizingRule.choices, default=LotSizingRule.LOT_FOR_LOT
    )
    fixed_order_quantity = models.DecimalField(max_digits=18, decimal_places=4, default=0)
    minimum_order_quantity = models.DecimalField(max_digits=18, decimal_places=4, default=0)
    order_multiple = models.DecimalField(max_digits=18, decimal_places=4, default=1)
    yield_percent = models.DecimalField(max_digits=7, decimal_places=3, default=100)
    planning_time_fence_days = models.PositiveIntegerField(default=0)

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=["plant", "item"], name="uq_item_policy_plant_item"),
            models.CheckConstraint(condition=models.Q(safety_stock__gte=0), name="ck_policy_safety_nonneg"),
            models.CheckConstraint(condition=models.Q(fixed_order_quantity__gte=0), name="ck_policy_fixed_nonneg"),
            models.CheckConstraint(condition=models.Q(minimum_order_quantity__gte=0), name="ck_policy_min_nonneg"),
            models.CheckConstraint(condition=models.Q(order_multiple__gt=0), name="ck_policy_multiple_pos"),
            models.CheckConstraint(condition=models.Q(yield_percent__gt=0), name="ck_policy_yield_pos"),
        ]
        ordering = ["plant__code", "item__code"]

    def clean(self) -> None:
        if self.yield_percent <= 0:
            raise ValidationError({"yield_percent": "O rendimento deve ser maior que zero."})
        if self.lot_sizing_rule == self.LotSizingRule.FIXED and self.fixed_order_quantity <= 0:
            raise ValidationError({"fixed_order_quantity": "Informe a quantidade fixa."})
        if self.lot_sizing_rule == self.LotSizingRule.MULTIPLE and self.order_multiple <= 0:
            raise ValidationError({"order_multiple": "O múltiplo deve ser maior que zero."})

    def __str__(self) -> str:
        return f"{self.plant.code}/{self.item.code}"


class BOMLine(TimeStampedModel):
    class BOMType(models.TextChoices):
        ALL = "ALL", "Todos"
        ENGINEERING = "ENGINEERING", "Engenharia"
        MANUFACTURING = "MANUFACTURING", "Produção"
        SPARES = "SPARES", "Reposição"

    parent = models.ForeignKey(Item, on_delete=models.CASCADE, related_name="bom_components")
    component = models.ForeignKey(Item, on_delete=models.PROTECT, related_name="where_used")
    sequence = models.PositiveIntegerField(default=10)
    quantity_per = models.DecimalField(max_digits=18, decimal_places=6)
    scrap_percent = models.DecimalField(max_digits=7, decimal_places=3, default=0)
    bom_type = models.CharField(max_length=20, choices=BOMType.choices, default=BOMType.MANUFACTURING)
    effective_from = models.DateField(null=True, blank=True)
    effective_to = models.DateField(null=True, blank=True)
    engineering_change = models.CharField(max_length=50, blank=True)
    is_active = models.BooleanField(default=True)

    class Meta:
        ordering = ["parent__code", "sequence", "component__code"]
        constraints = [
            models.UniqueConstraint(
                fields=["parent", "component", "sequence"], name="uq_bom_parent_component_sequence"
            ),
            models.CheckConstraint(condition=models.Q(quantity_per__gt=0), name="ck_bom_quantity_pos"),
            models.CheckConstraint(condition=models.Q(scrap_percent__gte=0), name="ck_bom_scrap_nonneg"),
            models.CheckConstraint(
                condition=~models.Q(parent=models.F("component")),
                name="ck_bom_parent_diff_comp",
            ),
            models.CheckConstraint(
                condition=(
                    models.Q(effective_from__isnull=True)
                    | models.Q(effective_to__isnull=True)
                    | models.Q(effective_to__gte=models.F("effective_from"))
                ),
                name="ck_bom_effectivity_dates",
            ),
        ]
        indexes = [models.Index(fields=["parent", "is_active"], name="ix_bom_parent_active")]

    def clean(self) -> None:
        if self.parent_id == self.component_id:
            raise ValidationError("Um item não pode ser componente de si mesmo.")
        if self.quantity_per <= 0:
            raise ValidationError({"quantity_per": "A quantidade deve ser maior que zero."})
        if self.effective_from and self.effective_to and self.effective_to < self.effective_from:
            raise ValidationError({"effective_to": "A data final deve ser posterior à inicial."})

    def quantity_with_scrap(self) -> Decimal:
        return self.quantity_per * (Decimal("1") + self.scrap_percent / Decimal("100"))

    def __str__(self) -> str:
        return f"{self.parent.code} -> {self.component.code}"


class WorkCenter(TimeStampedModel):
    plant = models.ForeignKey(Plant, on_delete=models.CASCADE, related_name="work_centers")
    code = models.CharField(max_length=30)
    name = models.CharField(max_length=120)
    capacity_hours_per_day = models.DecimalField(max_digits=10, decimal_places=3, default=8)
    efficiency_percent = models.DecimalField(max_digits=7, decimal_places=3, default=100)
    queue_days = models.DecimalField(max_digits=8, decimal_places=3, default=0)
    preparation_days = models.DecimalField(max_digits=8, decimal_places=3, default=0)
    postoperation_days = models.DecimalField(max_digits=8, decimal_places=3, default=0)
    wait_days = models.DecimalField(max_digits=8, decimal_places=3, default=0)
    is_critical = models.BooleanField(default=False)
    is_active = models.BooleanField(default=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=["plant", "code"], name="uq_work_center_plant_code"),
            models.CheckConstraint(condition=models.Q(capacity_hours_per_day__gt=0), name="ck_wc_capacity_pos"),
            models.CheckConstraint(condition=models.Q(efficiency_percent__gt=0), name="ck_wc_efficiency_pos"),
            models.CheckConstraint(condition=models.Q(queue_days__gte=0), name="ck_wc_queue_nonneg"),
            models.CheckConstraint(condition=models.Q(preparation_days__gte=0), name="ck_wc_prep_nonneg"),
            models.CheckConstraint(condition=models.Q(postoperation_days__gte=0), name="ck_wc_post_nonneg"),
            models.CheckConstraint(condition=models.Q(wait_days__gte=0), name="ck_wc_wait_nonneg"),
        ]
        ordering = ["plant__code", "code"]

    def __str__(self) -> str:
        return f"{self.plant.code}/{self.code}"


class Routing(TimeStampedModel):
    plant = models.ForeignKey(Plant, on_delete=models.CASCADE, related_name="routings")
    item = models.ForeignKey(Item, on_delete=models.CASCADE, related_name="routings")
    code = models.CharField(max_length=30, default="STD")
    version = models.PositiveIntegerField(default=1)
    is_primary = models.BooleanField(default=True)
    effective_from = models.DateField(null=True, blank=True)
    effective_to = models.DateField(null=True, blank=True)
    is_active = models.BooleanField(default=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["plant", "item", "code", "version"], name="uq_routing_version"
            ),
            models.CheckConstraint(
                condition=(
                    models.Q(effective_from__isnull=True)
                    | models.Q(effective_to__isnull=True)
                    | models.Q(effective_to__gte=models.F("effective_from"))
                ),
                name="ck_routing_effect_dates",
            ),
        ]
        ordering = ["plant__code", "item__code", "code", "version"]

    def __str__(self) -> str:
        return f"{self.plant.code}/{self.item.code}/{self.code} v{self.version}"


class RoutingOperation(TimeStampedModel):
    routing = models.ForeignKey(Routing, on_delete=models.CASCADE, related_name="operations")
    sequence = models.PositiveIntegerField()
    description = models.CharField(max_length=200)
    work_center = models.ForeignKey(WorkCenter, on_delete=models.PROTECT, related_name="operations")
    alternate_work_center = models.ForeignKey(
        WorkCenter, null=True, blank=True, on_delete=models.SET_NULL, related_name="alternate_operations"
    )
    setup_hours = models.DecimalField(max_digits=12, decimal_places=4, default=0)
    run_hours_per_unit = models.DecimalField(max_digits=12, decimal_places=6, default=0)
    teardown_hours = models.DecimalField(max_digits=12, decimal_places=4, default=0)
    move_days = models.DecimalField(max_digits=8, decimal_places=3, default=0)
    yield_percent = models.DecimalField(max_digits=7, decimal_places=3, default=100)

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=["routing", "sequence"], name="uq_routing_operation_sequence"),
            models.CheckConstraint(condition=models.Q(setup_hours__gte=0), name="ck_routeop_setup_nonneg"),
            models.CheckConstraint(condition=models.Q(run_hours_per_unit__gte=0), name="ck_routeop_run_nonneg"),
            models.CheckConstraint(condition=models.Q(teardown_hours__gte=0), name="ck_routeop_teardown_nonneg"),
            models.CheckConstraint(condition=models.Q(move_days__gte=0), name="ck_routeop_move_nonneg"),
            models.CheckConstraint(condition=models.Q(yield_percent__gt=0), name="ck_routeop_yield_pos"),
        ]
        ordering = ["routing", "sequence"]

    def __str__(self) -> str:
        return f"{self.routing} op {self.sequence}"


class Supplier(TimeStampedModel):
    code = models.CharField(max_length=30, unique=True)
    name = models.CharField(max_length=160)
    email = models.EmailField(blank=True)
    phone = models.CharField(max_length=40, blank=True)
    payment_terms_days = models.PositiveIntegerField(default=30, help_text="Dias entre a data planejada da compra e o desembolso estimado.")
    payment_terms_code = models.CharField(max_length=30, blank=True, default="NET30")
    # 0.8.6 — parcelamento opcional; se vazio, usa payment_terms_days em parcela única.
    payment_installments = models.JSONField(default=list, blank=True, help_text='Opcional: [{"days":30,"percent":50},{"days":60,"percent":50}]')
    is_active = models.BooleanField(default=True)

    class Meta:
        ordering = ["code"]

    def __str__(self) -> str:
        return f"{self.code} - {self.name}"


class ItemSupplier(TimeStampedModel):
    plant = models.ForeignKey(Plant, on_delete=models.CASCADE, related_name="item_suppliers")
    item = models.ForeignKey(Item, on_delete=models.CASCADE, related_name="suppliers")
    supplier = models.ForeignKey(Supplier, on_delete=models.CASCADE, related_name="items")
    lead_time_days = models.PositiveIntegerField(default=0)
    minimum_order_quantity = models.DecimalField(max_digits=18, decimal_places=4, default=0)
    order_multiple = models.DecimalField(max_digits=18, decimal_places=4, default=1)
    unit_price = models.DecimalField(max_digits=18, decimal_places=4, default=0)
    is_primary = models.BooleanField(default=False)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["plant", "item", "supplier"], name="uq_item_supplier"
            ),
            models.CheckConstraint(condition=models.Q(minimum_order_quantity__gte=0), name="ck_itemsupp_min_nonneg"),
            models.CheckConstraint(condition=models.Q(order_multiple__gt=0), name="ck_itemsupp_multiple_pos"),
            models.CheckConstraint(condition=models.Q(unit_price__gte=0), name="ck_itemsupp_price_nonneg"),
        ]
        ordering = ["plant__code", "item__code", "supplier__code"]

    def __str__(self) -> str:
        return f"{self.item.code} / {self.supplier.code}"


class WorkCenterShift(TimeStampedModel):
    """Capacidade regular por turno e dia da semana.

    ``weekday`` segue a convenção do Python: 0=segunda ... 6=domingo.
    Quando não há turnos ativos para um dia, o CRP usa
    ``WorkCenter.capacity_hours_per_day`` como fallback.
    """

    work_center = models.ForeignKey(WorkCenter, on_delete=models.CASCADE, related_name="shifts")
    name = models.CharField(max_length=60)
    weekday = models.PositiveSmallIntegerField()
    start_time = models.TimeField()
    end_time = models.TimeField()
    capacity_hours = models.DecimalField(max_digits=10, decimal_places=3)
    efficiency_percent = models.DecimalField(max_digits=7, decimal_places=3, default=100)
    is_active = models.BooleanField(default=True)

    class Meta:
        constraints = [
            models.CheckConstraint(
                condition=models.Q(weekday__gte=0, weekday__lte=6),
                name="ck_shift_weekday_0_6",
            ),
            models.CheckConstraint(condition=models.Q(capacity_hours__gt=0), name="ck_shift_capacity_pos"),
            models.CheckConstraint(condition=models.Q(efficiency_percent__gt=0), name="ck_shift_efficiency_pos"),
            models.UniqueConstraint(
                fields=["work_center", "weekday", "name"],
                name="uq_work_center_shift_day_name",
            ),
        ]
        ordering = ["work_center", "weekday", "start_time"]

    def clean(self) -> None:
        if self.capacity_hours <= 0:
            raise ValidationError({"capacity_hours": "A capacidade do turno deve ser positiva."})
        if self.efficiency_percent <= 0:
            raise ValidationError({"efficiency_percent": "A eficiência deve ser positiva."})

    def __str__(self) -> str:
        return f"{self.work_center} {self.name} d{self.weekday}"


class ItemSubstitute(TimeStampedModel):
    """Alternativa aprovada para atender falta de um item principal."""

    plant = models.ForeignKey(Plant, on_delete=models.CASCADE, related_name="item_substitutes")
    item = models.ForeignKey(Item, on_delete=models.CASCADE, related_name="substitute_options")
    substitute_item = models.ForeignKey(
        Item, on_delete=models.PROTECT, related_name="substitutes_for"
    )
    priority = models.PositiveIntegerField(default=10)
    substitute_quantity_per_primary = models.DecimalField(
        max_digits=18,
        decimal_places=6,
        default=1,
        help_text="Quantidade do substituto equivalente a uma unidade do item principal.",
    )
    effective_from = models.DateField(null=True, blank=True)
    effective_to = models.DateField(null=True, blank=True)
    notes = models.CharField(max_length=240, blank=True)
    is_active = models.BooleanField(default=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["plant", "item", "substitute_item"],
                name="uq_item_substitute_plant_pair",
            ),
            models.CheckConstraint(
                condition=~models.Q(item=models.F("substitute_item")),
                name="ck_substitute_items_diff",
            ),
            models.CheckConstraint(
                condition=models.Q(substitute_quantity_per_primary__gt=0),
                name="ck_substitute_ratio_pos",
            ),
            models.CheckConstraint(
                condition=(
                    models.Q(effective_from__isnull=True)
                    | models.Q(effective_to__isnull=True)
                    | models.Q(effective_to__gte=models.F("effective_from"))
                ),
                name="ck_substitute_effect_dates",
            ),
        ]
        ordering = ["plant__code", "item__code", "priority", "substitute_item__code"]

    def clean(self) -> None:
        if self.item_id == self.substitute_item_id:
            raise ValidationError("O item substituto deve ser diferente do item principal.")
        if self.substitute_quantity_per_primary <= 0:
            raise ValidationError(
                {"substitute_quantity_per_primary": "A relação de equivalência deve ser positiva."}
            )
        if self.effective_from and self.effective_to and self.effective_to < self.effective_from:
            raise ValidationError({"effective_to": "A data final deve ser posterior à inicial."})

    def is_effective_on(self, on_date) -> bool:
        if not self.is_active:
            return False
        if self.effective_from and on_date < self.effective_from:
            return False
        if self.effective_to and on_date > self.effective_to:
            return False
        return True

    def __str__(self) -> str:
        return f"{self.plant.code}: {self.item.code} => {self.substitute_item.code}"
