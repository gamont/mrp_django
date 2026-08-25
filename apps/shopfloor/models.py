from __future__ import annotations

from decimal import Decimal

from django.conf import settings
from django.contrib.auth.hashers import check_password, make_password
from django.db import models
from django.utils import timezone

from apps.common.models import Plant, TimeStampedModel
from apps.masterdata.models import WorkCenter
from apps.production.models import WorkOrderOperation


class OperatorProfile(TimeStampedModel):
    user = models.OneToOneField(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="shopfloor_profile")
    badge_code = models.CharField(max_length=40, unique=True)
    pin_hash = models.CharField(max_length=128)
    is_active = models.BooleanField(default=True)
    failed_attempts = models.PositiveSmallIntegerField(default=0)
    locked_until = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ["badge_code"]
        permissions = [("use_shopfloor_terminal", "Pode usar terminal de chão de fábrica")]

    def set_pin(self, raw_pin: str) -> None:
        self.pin_hash = make_password(raw_pin)

    def check_pin(self, raw_pin: str) -> bool:
        return check_password(raw_pin, self.pin_hash)

    @property
    def is_locked(self) -> bool:
        return bool(self.locked_until and self.locked_until > timezone.now())

    def __str__(self) -> str:
        return f"{self.badge_code} · {self.user.get_username()}"


class Machine(TimeStampedModel):
    class Status(models.TextChoices):
        INACTIVE = "INACTIVE", "Inativa"
        IDLE = "IDLE", "Ociosa"
        SETUP = "SETUP", "Setup"
        RUNNING = "RUNNING", "Em operação"
        DOWN = "DOWN", "Parada"
        REPAIR = "REPAIR", "Em reparo"
        PREVENTIVE = "PREVENTIVE", "Manutenção preventiva"

    plant = models.ForeignKey(Plant, on_delete=models.CASCADE, related_name="machines")
    work_center = models.ForeignKey(WorkCenter, on_delete=models.PROTECT, related_name="machines")
    code = models.CharField(max_length=40)
    name = models.CharField(max_length=120)
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.IDLE)
    current_operation = models.ForeignKey(
        WorkOrderOperation,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="machine_assignments",
    )
    status_since = models.DateTimeField(default=timezone.now)
    is_active = models.BooleanField(default=True)
    planned_minutes_per_day = models.DecimalField(max_digits=8, decimal_places=2, default=480)
    ideal_cycle_seconds = models.DecimalField(max_digits=12, decimal_places=4, default=0)

    class Meta:
        ordering = ["plant__code", "code"]
        constraints = [
            models.UniqueConstraint(fields=["plant", "code"], name="uq_machine_plant_code"),
            models.CheckConstraint(condition=models.Q(planned_minutes_per_day__gte=0), name="ck_machine_plan_minutes_nonneg"),
            models.CheckConstraint(condition=models.Q(ideal_cycle_seconds__gte=0), name="ck_machine_cycle_nonneg"),
        ]
        indexes = [
            models.Index(fields=["plant", "work_center", "status"], name="ix_machine_wc_status"),
        ]

    def __str__(self) -> str:
        return f"{self.plant.code}/{self.code}"


class TerminalStation(TimeStampedModel):
    plant = models.ForeignKey(Plant, on_delete=models.CASCADE, related_name="terminal_stations")
    code = models.CharField(max_length=40)
    name = models.CharField(max_length=120)
    work_center = models.ForeignKey(
        WorkCenter, null=True, blank=True, on_delete=models.PROTECT, related_name="terminal_stations"
    )
    machine = models.ForeignKey(
        Machine, null=True, blank=True, on_delete=models.SET_NULL, related_name="terminal_stations"
    )
    is_active = models.BooleanField(default=True)

    class Meta:
        ordering = ["plant__code", "code"]
        constraints = [
            models.UniqueConstraint(fields=["plant", "code"], name="uq_terminal_plant_code"),
        ]

    def __str__(self) -> str:
        return f"{self.plant.code}/{self.code}"


class DowntimeReason(TimeStampedModel):
    class Category(models.TextChoices):
        UNPLANNED = "UNPLANNED", "Não planejada"
        PLANNED = "PLANNED", "Planejada"
        QUALITY = "QUALITY", "Qualidade"
        MATERIAL = "MATERIAL", "Falta de material"
        TOOLING = "TOOLING", "Ferramental"
        OTHER = "OTHER", "Outros"

    plant = models.ForeignKey(Plant, on_delete=models.CASCADE, related_name="downtime_reasons")
    code = models.CharField(max_length=30)
    description = models.CharField(max_length=160)
    category = models.CharField(max_length=20, choices=Category.choices, default=Category.UNPLANNED)
    is_active = models.BooleanField(default=True)

    class Meta:
        ordering = ["plant__code", "code"]
        constraints = [
            models.UniqueConstraint(fields=["plant", "code"], name="uq_downtime_reason_plant_code"),
        ]

    def __str__(self) -> str:
        return f"{self.code} · {self.description}"


class DowntimeEvent(TimeStampedModel):
    machine = models.ForeignKey(Machine, on_delete=models.PROTECT, related_name="downtime_events")
    operation = models.ForeignKey(
        WorkOrderOperation, null=True, blank=True, on_delete=models.SET_NULL, related_name="downtime_events"
    )
    reason = models.ForeignKey(DowntimeReason, on_delete=models.PROTECT, related_name="events")
    started_at = models.DateTimeField()
    ended_at = models.DateTimeField(null=True, blank=True)
    notes = models.TextField(blank=True)
    reported_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL, related_name="reported_downtimes"
    )

    class Meta:
        ordering = ["-started_at"]
        indexes = [models.Index(fields=["machine", "ended_at", "started_at"], name="ix_downtime_machine_open")]
        constraints = [
            models.CheckConstraint(
                condition=models.Q(ended_at__isnull=True) | models.Q(ended_at__gte=models.F("started_at")),
                name="ck_downtime_end_after_start",
            ),
            models.UniqueConstraint(
                fields=["machine"],
                condition=models.Q(ended_at__isnull=True),
                name="uq_machine_open_downtime",
            ),
        ]

    @property
    def duration_seconds(self) -> int:
        end = self.ended_at or timezone.now()
        return max(0, int((end - self.started_at).total_seconds()))

    def __str__(self) -> str:
        return f"{self.machine} · {self.reason.code} · {self.started_at:%Y-%m-%d %H:%M}"


class MachineProductionRecord(TimeStampedModel):
    """Vincula um apontamento de produção à máquina que o executou.

    Mantém a rastreabilidade necessária para OEE sem alterar o modelo legado
    de ProductionReport, que também pode ser gerado fora do terminal.
    """

    machine = models.ForeignKey(Machine, on_delete=models.PROTECT, related_name="production_records")
    report = models.OneToOneField(
        "production.ProductionReport",
        on_delete=models.PROTECT,
        related_name="shopfloor_machine_record",
    )
    operation = models.ForeignKey(
        WorkOrderOperation,
        on_delete=models.PROTECT,
        related_name="shopfloor_machine_records",
    )
    reported_at = models.DateTimeField()

    class Meta:
        ordering = ["-reported_at"]
        indexes = [
            models.Index(fields=["machine", "reported_at"], name="ix_sf_prod_machine_time"),
        ]

    def __str__(self) -> str:
        return f"{self.machine.code} · apontamento #{self.report_id}"


class OEEPeriodSnapshot(TimeStampedModel):
    """Snapshot diário dos indicadores OEE e confiabilidade de uma máquina."""

    machine = models.ForeignKey(Machine, on_delete=models.CASCADE, related_name="oee_snapshots")
    metric_date = models.DateField()
    planned_minutes = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    downtime_minutes = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    run_minutes = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    ideal_cycle_seconds = models.DecimalField(max_digits=12, decimal_places=4, default=0)
    good_quantity = models.DecimalField(max_digits=18, decimal_places=4, default=0)
    scrap_quantity = models.DecimalField(max_digits=18, decimal_places=4, default=0)
    availability = models.DecimalField(max_digits=7, decimal_places=4, default=0)
    performance = models.DecimalField(max_digits=7, decimal_places=4, default=0)
    quality = models.DecimalField(max_digits=7, decimal_places=4, default=0)
    oee = models.DecimalField(max_digits=7, decimal_places=4, default=0)
    availability_loss_minutes = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    performance_loss_minutes = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    quality_loss_minutes = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    failures = models.PositiveIntegerField(default=0)
    mtbf_minutes = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    mttr_minutes = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    calculated_at = models.DateTimeField(default=timezone.now)

    class Meta:
        ordering = ["-metric_date", "machine__code"]
        constraints = [
            models.UniqueConstraint(fields=["machine", "metric_date"], name="uq_oee_machine_date"),
            models.CheckConstraint(condition=models.Q(planned_minutes__gte=0), name="ck_oee_planned_nonneg"),
            models.CheckConstraint(condition=models.Q(run_minutes__gte=0), name="ck_oee_run_nonneg"),
            models.CheckConstraint(condition=models.Q(downtime_minutes__gte=0), name="ck_oee_down_nonneg"),
        ]
        indexes = [models.Index(fields=["metric_date", "machine"], name="ix_oee_date_machine")]

    @property
    def availability_pct(self):
        return self.availability * 100

    @property
    def performance_pct(self):
        return self.performance * 100

    @property
    def quality_pct(self):
        return self.quality * 100

    @property
    def oee_pct(self):
        return self.oee * 100

    def __str__(self) -> str:
        return f"{self.machine.code} · {self.metric_date} · OEE {self.oee_pct:.1f}%"


class OEETarget(TimeStampedModel):
    """Metas de OEE por planta, centro de trabalho ou máquina.

    A resolução usa a regra mais específica disponível: máquina > centro > planta.
    As metas são versionadas por vigência para preservar comparação histórica.
    """

    plant = models.ForeignKey(Plant, on_delete=models.CASCADE, related_name="oee_targets")
    work_center = models.ForeignKey(
        WorkCenter, null=True, blank=True, on_delete=models.CASCADE, related_name="oee_targets"
    )
    machine = models.ForeignKey(
        Machine, null=True, blank=True, on_delete=models.CASCADE, related_name="oee_targets"
    )
    effective_from = models.DateField()
    effective_to = models.DateField(null=True, blank=True)
    oee_target = models.DecimalField(max_digits=7, decimal_places=4, default=Decimal("0.8500"))
    availability_target = models.DecimalField(max_digits=7, decimal_places=4, default=Decimal("0.9000"))
    performance_target = models.DecimalField(max_digits=7, decimal_places=4, default=Decimal("0.9500"))
    quality_target = models.DecimalField(max_digits=7, decimal_places=4, default=Decimal("0.9900"))
    is_active = models.BooleanField(default=True)

    class Meta:
        ordering = ["-effective_from", "plant__code", "work_center__code", "machine__code"]
        indexes = [
            models.Index(fields=["plant", "effective_from", "effective_to"], name="ix_oee_target_plant_date"),
            models.Index(fields=["machine", "effective_from"], name="ix_oee_target_machine"),
        ]
        constraints = [
            models.CheckConstraint(condition=models.Q(oee_target__gte=0, oee_target__lte=1), name="ck_oee_target_oee_0_1"),
            models.CheckConstraint(condition=models.Q(availability_target__gte=0, availability_target__lte=1), name="ck_oee_target_avail_0_1"),
            models.CheckConstraint(condition=models.Q(performance_target__gte=0, performance_target__lte=1), name="ck_oee_target_perf_0_1"),
            models.CheckConstraint(condition=models.Q(quality_target__gte=0, quality_target__lte=1), name="ck_oee_target_quality_0_1"),
            models.CheckConstraint(condition=models.Q(effective_to__isnull=True) | models.Q(effective_to__gte=models.F("effective_from")), name="ck_oee_target_dates"),
        ]

    def __str__(self) -> str:
        scope = self.machine.code if self.machine_id else (self.work_center.code if self.work_center_id else self.plant.code)
        return f"Meta OEE {scope} desde {self.effective_from}"


class OEEShiftSnapshot(TimeStampedModel):
    """Snapshot de OEE por turno, máquina e data operacional."""

    machine = models.ForeignKey(Machine, on_delete=models.CASCADE, related_name="oee_shift_snapshots")
    shift = models.ForeignKey("masterdata.WorkCenterShift", on_delete=models.PROTECT, related_name="oee_snapshots")
    metric_date = models.DateField()
    window_start = models.DateTimeField()
    window_end = models.DateTimeField()
    planned_minutes = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    downtime_minutes = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    run_minutes = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    ideal_cycle_seconds = models.DecimalField(max_digits=12, decimal_places=4, default=0)
    good_quantity = models.DecimalField(max_digits=18, decimal_places=4, default=0)
    scrap_quantity = models.DecimalField(max_digits=18, decimal_places=4, default=0)
    availability = models.DecimalField(max_digits=7, decimal_places=4, default=0)
    performance = models.DecimalField(max_digits=7, decimal_places=4, default=0)
    quality = models.DecimalField(max_digits=7, decimal_places=4, default=0)
    oee = models.DecimalField(max_digits=7, decimal_places=4, default=0)
    availability_loss_minutes = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    performance_loss_minutes = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    quality_loss_minutes = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    failures = models.PositiveIntegerField(default=0)
    mtbf_minutes = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    mttr_minutes = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    calculated_at = models.DateTimeField(default=timezone.now)

    class Meta:
        ordering = ["-metric_date", "shift__start_time", "machine__code"]
        constraints = [
            models.UniqueConstraint(fields=["machine", "shift", "metric_date"], name="uq_oee_machine_shift_date"),
            models.CheckConstraint(condition=models.Q(planned_minutes__gte=0), name="ck_oees_plan_nonneg"),
            models.CheckConstraint(condition=models.Q(run_minutes__gte=0), name="ck_oees_run_nonneg"),
            models.CheckConstraint(condition=models.Q(downtime_minutes__gte=0), name="ck_oees_down_nonneg"),
        ]
        indexes = [
            models.Index(fields=["metric_date", "shift", "machine"], name="ix_oees_date_shift_machine"),
        ]

    @property
    def availability_pct(self):
        return self.availability * 100

    @property
    def performance_pct(self):
        return self.performance * 100

    @property
    def quality_pct(self):
        return self.quality * 100

    @property
    def oee_pct(self):
        return self.oee * 100

    def __str__(self) -> str:
        return f"{self.metric_date} · {self.shift.name} · {self.machine.code}"
