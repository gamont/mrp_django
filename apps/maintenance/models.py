from __future__ import annotations

from decimal import Decimal

from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import models
from django.utils import timezone

from apps.common.models import Plant, TimeStampedModel
from apps.inventory.models import InventoryTransaction, Location
from apps.masterdata.models import Item, WorkCenter
from apps.shopfloor.models import DowntimeEvent, Machine


class MaintenanceAsset(TimeStampedModel):
    class AssetType(models.TextChoices):
        MACHINE = "MACHINE", "Máquina"
        TOOL = "TOOL", "Ferramental"
        UTILITY = "UTILITY", "Utilidade"
        FACILITY = "FACILITY", "Instalação"
        OTHER = "OTHER", "Outro"

    class Criticality(models.TextChoices):
        LOW = "LOW", "Baixa"
        MEDIUM = "MEDIUM", "Média"
        HIGH = "HIGH", "Alta"
        CRITICAL = "CRITICAL", "Crítica"

    plant = models.ForeignKey(Plant, on_delete=models.CASCADE, related_name="maintenance_assets")
    code = models.CharField(max_length=40)
    name = models.CharField(max_length=160)
    asset_type = models.CharField(max_length=20, choices=AssetType.choices, default=AssetType.MACHINE)
    criticality = models.CharField(max_length=20, choices=Criticality.choices, default=Criticality.MEDIUM)
    machine = models.OneToOneField(
        Machine, null=True, blank=True, on_delete=models.SET_NULL, related_name="maintenance_asset"
    )
    work_center = models.ForeignKey(
        WorkCenter, null=True, blank=True, on_delete=models.SET_NULL, related_name="maintenance_assets"
    )
    manufacturer = models.CharField(max_length=120, blank=True)
    model_number = models.CharField(max_length=80, blank=True)
    serial_number = models.CharField(max_length=100, blank=True)
    commissioned_on = models.DateField(null=True, blank=True)
    is_active = models.BooleanField(default=True)

    class Meta:
        ordering = ["plant__code", "code"]
        constraints = [models.UniqueConstraint(fields=["plant", "code"], name="uq_maint_asset_plant_code")]
        indexes = [models.Index(fields=["plant", "criticality", "is_active"], name="ix_maint_asset_crit")]

    def clean(self):
        if self.machine_id and self.machine.plant_id != self.plant_id:
            raise ValidationError({"machine": "A máquina deve pertencer à mesma planta do ativo."})

    def __str__(self):
        return f"{self.plant.code}/{self.code} · {self.name}"


class AssetMeterReading(TimeStampedModel):
    asset = models.ForeignKey(MaintenanceAsset, on_delete=models.CASCADE, related_name="meter_readings")
    reading_at = models.DateTimeField(default=timezone.now)
    meter_value = models.DecimalField(max_digits=18, decimal_places=3)
    source = models.CharField(max_length=40, default="MANUAL")
    recorded_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL, related_name="maintenance_meter_readings"
    )
    notes = models.CharField(max_length=240, blank=True)

    class Meta:
        ordering = ["-reading_at", "-id"]
        indexes = [models.Index(fields=["asset", "reading_at"], name="ix_asset_meter_time")]
        constraints = [models.CheckConstraint(condition=models.Q(meter_value__gte=0), name="ck_asset_meter_nonneg")]

    def __str__(self):
        return f"{self.asset.code}: {self.meter_value}"


class MaintenancePlan(TimeStampedModel):
    class Strategy(models.TextChoices):
        CALENDAR = "CALENDAR", "Calendário"
        METER = "METER", "Medidor"
        HYBRID = "HYBRID", "Calendário ou medidor"

    asset = models.ForeignKey(MaintenanceAsset, on_delete=models.CASCADE, related_name="maintenance_plans")
    code = models.CharField(max_length=50)
    title = models.CharField(max_length=180)
    strategy = models.CharField(max_length=20, choices=Strategy.choices, default=Strategy.CALENDAR)
    interval_days = models.PositiveIntegerField(default=0)
    interval_meter = models.DecimalField(max_digits=18, decimal_places=3, default=0)
    planned_duration_hours = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    next_due_date = models.DateField(null=True, blank=True)
    next_due_meter = models.DecimalField(max_digits=18, decimal_places=3, null=True, blank=True)
    instructions = models.TextField(blank=True)
    is_active = models.BooleanField(default=True)

    class Meta:
        ordering = ["asset__code", "code"]
        constraints = [
            models.UniqueConstraint(fields=["asset", "code"], name="uq_maint_plan_asset_code"),
            models.CheckConstraint(condition=models.Q(interval_meter__gte=0), name="ck_maint_plan_meter_nonneg"),
            models.CheckConstraint(condition=models.Q(planned_duration_hours__gte=0), name="ck_maint_plan_duration_nonneg"),
        ]

    def clean(self):
        if self.strategy in {self.Strategy.CALENDAR, self.Strategy.HYBRID} and self.interval_days <= 0:
            raise ValidationError({"interval_days": "Informe um intervalo em dias para esta estratégia."})
        if self.strategy in {self.Strategy.METER, self.Strategy.HYBRID} and self.interval_meter <= 0:
            raise ValidationError({"interval_meter": "Informe um intervalo de medidor para esta estratégia."})

    def __str__(self):
        return f"{self.asset.code}/{self.code} · {self.title}"


class MaintenanceWorkOrder(TimeStampedModel):
    class OrderType(models.TextChoices):
        PREVENTIVE = "PREVENTIVE", "Preventiva"
        CORRECTIVE = "CORRECTIVE", "Corretiva"
        PREDICTIVE = "PREDICTIVE", "Preditiva"
        INSPECTION = "INSPECTION", "Inspeção"

    class Priority(models.TextChoices):
        LOW = "LOW", "Baixa"
        NORMAL = "NORMAL", "Normal"
        HIGH = "HIGH", "Alta"
        EMERGENCY = "EMERGENCY", "Emergência"

    class Status(models.TextChoices):
        PLANNED = "PLANNED", "Planejada"
        RELEASED = "RELEASED", "Liberada"
        IN_PROGRESS = "IN_PROGRESS", "Em execução"
        WAITING_PARTS = "WAITING_PARTS", "Aguardando peças"
        COMPLETED = "COMPLETED", "Concluída"
        CANCELLED = "CANCELLED", "Cancelada"

    plant = models.ForeignKey(Plant, on_delete=models.PROTECT, related_name="maintenance_work_orders")
    number = models.CharField(max_length=50, unique=True)
    asset = models.ForeignKey(MaintenanceAsset, on_delete=models.PROTECT, related_name="work_orders")
    plan = models.ForeignKey(MaintenancePlan, null=True, blank=True, on_delete=models.SET_NULL, related_name="work_orders")
    order_type = models.CharField(max_length=20, choices=OrderType.choices, default=OrderType.PREVENTIVE)
    priority = models.CharField(max_length=20, choices=Priority.choices, default=Priority.NORMAL)
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.PLANNED)
    title = models.CharField(max_length=180)
    description = models.TextField(blank=True)
    requested_at = models.DateTimeField(default=timezone.now)
    scheduled_start = models.DateTimeField(null=True, blank=True)
    scheduled_end = models.DateTimeField(null=True, blank=True)
    started_at = models.DateTimeField(null=True, blank=True)
    completed_at = models.DateTimeField(null=True, blank=True)
    downtime_event = models.OneToOneField(
        DowntimeEvent, null=True, blank=True, on_delete=models.SET_NULL, related_name="maintenance_work_order"
    )
    assigned_to = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL, related_name="assigned_maintenance_orders"
    )
    requested_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL, related_name="requested_maintenance_orders"
    )
    completion_notes = models.TextField(blank=True)
    meter_at_completion = models.DecimalField(max_digits=18, decimal_places=3, null=True, blank=True)
    priority_score = models.DecimalField(max_digits=8, decimal_places=2, default=0)
    priority_reason = models.JSONField(default=dict, blank=True)
    scheduling_locked = models.BooleanField(default=False)

    class Meta:
        ordering = ["-requested_at", "number"]
        indexes = [
            models.Index(fields=["plant", "status", "priority"], name="ix_maint_wo_status"),
            models.Index(fields=["asset", "scheduled_start"], name="ix_maint_wo_asset_date"),
        ]
        constraints = [
            models.CheckConstraint(
                condition=models.Q(scheduled_end__isnull=True) | models.Q(scheduled_start__isnull=True) | models.Q(scheduled_end__gte=models.F("scheduled_start")),
                name="ck_maint_wo_schedule_order",
            )
        ]

    def clean(self):
        if self.asset_id and self.plant_id and self.asset.plant_id != self.plant_id:
            raise ValidationError({"asset": "O ativo deve pertencer à mesma planta da ordem."})

    def __str__(self):
        return f"{self.number} · {self.asset.code} · {self.get_status_display()}"


class MaintenancePart(TimeStampedModel):
    work_order = models.ForeignKey(MaintenanceWorkOrder, on_delete=models.CASCADE, related_name="parts")
    item = models.ForeignKey(Item, on_delete=models.PROTECT, related_name="maintenance_parts")
    planned_quantity = models.DecimalField(max_digits=18, decimal_places=4, default=0)
    issued_quantity = models.DecimalField(max_digits=18, decimal_places=4, default=0)
    source_location = models.ForeignKey(
        Location, null=True, blank=True, on_delete=models.PROTECT, related_name="maintenance_part_issues"
    )
    issue_transaction = models.ForeignKey(
        InventoryTransaction, null=True, blank=True, on_delete=models.SET_NULL, related_name="maintenance_part_lines"
    )

    class Meta:
        ordering = ["work_order__number", "item__code"]
        constraints = [
            models.UniqueConstraint(fields=["work_order", "item"], name="uq_maint_part_wo_item"),
            models.CheckConstraint(condition=models.Q(planned_quantity__gte=0), name="ck_maint_part_plan_nonneg"),
            models.CheckConstraint(condition=models.Q(issued_quantity__gte=0), name="ck_maint_part_issue_nonneg"),
        ]

    @property
    def remaining_quantity(self) -> Decimal:
        return max(Decimal("0"), self.planned_quantity - self.issued_quantity)

    def __str__(self):
        return f"{self.work_order.number}: {self.item.code}"


class FailureEvent(TimeStampedModel):
    class FailureClass(models.TextChoices):
        MECHANICAL = "MECHANICAL", "Mecânica"
        ELECTRICAL = "ELECTRICAL", "Elétrica"
        AUTOMATION = "AUTOMATION", "Automação"
        QUALITY = "QUALITY", "Qualidade"
        OTHER = "OTHER", "Outra"

    asset = models.ForeignKey(MaintenanceAsset, on_delete=models.PROTECT, related_name="failure_events")
    work_order = models.ForeignKey(
        MaintenanceWorkOrder, null=True, blank=True, on_delete=models.SET_NULL, related_name="failure_events"
    )
    downtime_event = models.ForeignKey(
        DowntimeEvent, null=True, blank=True, on_delete=models.SET_NULL, related_name="failure_events"
    )
    failure_class = models.CharField(max_length=20, choices=FailureClass.choices, default=FailureClass.OTHER)
    occurred_at = models.DateTimeField(default=timezone.now)
    symptom = models.TextField()
    cause = models.TextField(blank=True)
    corrective_action = models.TextField(blank=True)
    resolved_at = models.DateTimeField(null=True, blank=True)
    reported_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL, related_name="reported_failures"
    )

    class Meta:
        ordering = ["-occurred_at"]
        indexes = [models.Index(fields=["asset", "occurred_at"], name="ix_failure_asset_time")]

    def __str__(self):
        return f"{self.asset.code} · {self.get_failure_class_display()} · {self.occurred_at:%Y-%m-%d %H:%M}"


class TechnicianSkill(TimeStampedModel):
    code = models.CharField(max_length=40, unique=True)
    name = models.CharField(max_length=120)
    description = models.TextField(blank=True)
    is_active = models.BooleanField(default=True)

    class Meta:
        ordering = ["code"]

    def __str__(self):
        return f"{self.code} · {self.name}"


class TechnicianProfile(TimeStampedModel):
    user = models.OneToOneField(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="maintenance_technician")
    plant = models.ForeignKey(Plant, on_delete=models.CASCADE, related_name="maintenance_technicians")
    employee_code = models.CharField(max_length=40)
    daily_capacity_hours = models.DecimalField(max_digits=6, decimal_places=2, default=8)
    is_active = models.BooleanField(default=True)

    class Meta:
        ordering = ["plant__code", "employee_code"]
        constraints = [
            models.UniqueConstraint(fields=["plant", "employee_code"], name="uq_maint_tech_plant_code"),
            models.CheckConstraint(condition=models.Q(daily_capacity_hours__gte=0), name="ck_maint_tech_capacity_nonneg"),
        ]

    def __str__(self):
        return f"{self.employee_code} · {self.user.get_username()}"


class TechnicianSkillAssignment(TimeStampedModel):
    technician = models.ForeignKey(TechnicianProfile, on_delete=models.CASCADE, related_name="skill_assignments")
    skill = models.ForeignKey(TechnicianSkill, on_delete=models.PROTECT, related_name="technician_assignments")
    proficiency = models.PositiveSmallIntegerField(default=1)
    valid_until = models.DateField(null=True, blank=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=["technician", "skill"], name="uq_maint_tech_skill"),
            models.CheckConstraint(condition=models.Q(proficiency__gte=1) & models.Q(proficiency__lte=5), name="ck_maint_skill_prof_1_5"),
        ]


class WorkOrderAssignment(TimeStampedModel):
    work_order = models.ForeignKey(MaintenanceWorkOrder, on_delete=models.CASCADE, related_name="technician_assignments")
    technician = models.ForeignKey(TechnicianProfile, on_delete=models.PROTECT, related_name="work_order_assignments")
    planned_hours = models.DecimalField(max_digits=8, decimal_places=2, default=0)
    actual_hours = models.DecimalField(max_digits=8, decimal_places=2, default=0)
    is_lead = models.BooleanField(default=False)

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=["work_order", "technician"], name="uq_maint_wo_technician"),
            models.CheckConstraint(condition=models.Q(planned_hours__gte=0), name="ck_maint_assign_plan_nonneg"),
            models.CheckConstraint(condition=models.Q(actual_hours__gte=0), name="ck_maint_assign_actual_nonneg"),
        ]


class MaintenanceSLA(TimeStampedModel):
    plant = models.ForeignKey(Plant, on_delete=models.CASCADE, related_name="maintenance_slas")
    priority = models.CharField(max_length=20, choices=MaintenanceWorkOrder.Priority.choices)
    response_hours = models.DecimalField(max_digits=8, decimal_places=2, default=0)
    resolution_hours = models.DecimalField(max_digits=8, decimal_places=2, default=0)
    is_active = models.BooleanField(default=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=["plant", "priority"], name="uq_maint_sla_plant_priority"),
            models.CheckConstraint(condition=models.Q(response_hours__gte=0), name="ck_maint_sla_response_nonneg"),
            models.CheckConstraint(condition=models.Q(resolution_hours__gte=0), name="ck_maint_sla_resolution_nonneg"),
        ]


class ConditionReading(TimeStampedModel):
    class Metric(models.TextChoices):
        VIBRATION = "VIBRATION", "Vibração"
        TEMPERATURE = "TEMPERATURE", "Temperatura"
        PRESSURE = "PRESSURE", "Pressão"
        CURRENT = "CURRENT", "Corrente"
        CUSTOM = "CUSTOM", "Outro"

    asset = models.ForeignKey(MaintenanceAsset, on_delete=models.CASCADE, related_name="condition_readings")
    metric = models.CharField(max_length=20, choices=Metric.choices)
    metric_name = models.CharField(max_length=80, blank=True)
    value = models.DecimalField(max_digits=18, decimal_places=4)
    unit = models.CharField(max_length=20, blank=True)
    reading_at = models.DateTimeField(default=timezone.now)
    source = models.CharField(max_length=40, default="MANUAL")
    recorded_by = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL, related_name="maintenance_condition_readings")

    class Meta:
        ordering = ["-reading_at", "-id"]
        indexes = [models.Index(fields=["asset", "metric", "reading_at"], name="ix_cond_asset_metric")]


class ConditionRule(TimeStampedModel):
    class Comparator(models.TextChoices):
        GT = "GT", ">"
        GTE = "GTE", ">="
        LT = "LT", "<"
        LTE = "LTE", "<="

    asset = models.ForeignKey(MaintenanceAsset, on_delete=models.CASCADE, related_name="condition_rules")
    code = models.CharField(max_length=50)
    metric = models.CharField(max_length=20, choices=ConditionReading.Metric.choices)
    metric_name = models.CharField(max_length=80, blank=True)
    comparator = models.CharField(max_length=4, choices=Comparator.choices, default=Comparator.GTE)
    threshold = models.DecimalField(max_digits=18, decimal_places=4)
    priority = models.CharField(max_length=20, choices=MaintenanceWorkOrder.Priority.choices, default=MaintenanceWorkOrder.Priority.HIGH)
    title = models.CharField(max_length=180)
    is_active = models.BooleanField(default=True)

    class Meta:
        constraints = [models.UniqueConstraint(fields=["asset", "code"], name="uq_maint_condition_rule")]


class MaintenanceRequiredSkill(TimeStampedModel):
    work_order = models.ForeignKey(MaintenanceWorkOrder, on_delete=models.CASCADE, related_name="required_skills")
    skill = models.ForeignKey(TechnicianSkill, on_delete=models.PROTECT, related_name="maintenance_requirements")
    min_proficiency = models.PositiveSmallIntegerField(default=1)
    technicians_required = models.PositiveSmallIntegerField(default=1)

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=["work_order", "skill"], name="uq_maint_wo_required_skill"),
            models.CheckConstraint(condition=models.Q(min_proficiency__gte=1) & models.Q(min_proficiency__lte=5), name="ck_maint_req_skill_prof"),
            models.CheckConstraint(condition=models.Q(technicians_required__gte=1), name="ck_maint_req_skill_techs"),
        ]


class MaintenancePartReservation(TimeStampedModel):
    part = models.ForeignKey(MaintenancePart, on_delete=models.CASCADE, related_name="reservations")
    reservation = models.OneToOneField("inventory.Reservation", on_delete=models.CASCADE, related_name="maintenance_part_reservation")

    class Meta:
        ordering = ["part__work_order__number", "part__item__code", "reservation__location_id"]


class MaintenanceScheduleConflict(TimeStampedModel):
    class ConflictType(models.TextChoices):
        PRODUCTION = "PRODUCTION", "Produção"
        MACHINE = "MACHINE", "Máquina"
        TECHNICIAN = "TECHNICIAN", "Técnico"
        PARTS = "PARTS", "Peças"

    class Severity(models.TextChoices):
        INFO = "INFO", "Informativa"
        WARNING = "WARNING", "Atenção"
        CRITICAL = "CRITICAL", "Crítica"

    work_order = models.ForeignKey(MaintenanceWorkOrder, on_delete=models.CASCADE, related_name="schedule_conflicts")
    conflict_type = models.CharField(max_length=20, choices=ConflictType.choices)
    severity = models.CharField(max_length=20, choices=Severity.choices, default=Severity.WARNING)
    message = models.CharField(max_length=300)
    related_operation = models.ForeignKey(
        "production.WorkOrderOperation", null=True, blank=True, on_delete=models.SET_NULL, related_name="maintenance_conflicts"
    )
    detected_at = models.DateTimeField(default=timezone.now)
    resolved_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ["-detected_at", "id"]
        indexes = [models.Index(fields=["work_order", "conflict_type", "resolved_at"], name="ix_maint_sched_conflict")]
