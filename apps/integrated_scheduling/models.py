from django.conf import settings
from django.db import models
from django.utils import timezone

from apps.common.models import Plant, TimeStampedModel
from apps.masterdata.models import WorkCenter
from apps.shopfloor.models import Machine


class IntegratedScheduleScenario(TimeStampedModel):
    class Status(models.TextChoices):
        DRAFT = "DRAFT", "Rascunho"
        RUNNING = "RUNNING", "Executando"
        COMPLETED = "COMPLETED", "Concluído"
        APPLIED = "APPLIED", "Aplicado"
        FAILED = "FAILED", "Falhou"

    name = models.CharField(max_length=160)
    plant = models.ForeignKey(Plant, on_delete=models.PROTECT, related_name="integrated_schedule_scenarios")
    horizon_start = models.DateField()
    horizon_end = models.DateField()
    status = models.CharField(max_length=16, choices=Status.choices, default=Status.DRAFT)
    include_planned_production = models.BooleanField(default=True)
    include_maintenance = models.BooleanField(default=True)
    parameters = models.JSONField(default=dict, blank=True)
    baseline_summary = models.JSONField(default=dict, blank=True)
    simulated_summary = models.JSONField(default=dict, blank=True)
    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL, related_name="integrated_schedule_scenarios_created")
    applied_by = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL, related_name="integrated_schedule_scenarios_applied")
    applied_at = models.DateTimeField(null=True, blank=True)
    error_message = models.TextField(blank=True)
    scheduling_direction = models.CharField(max_length=12, choices=[("FORWARD", "Forward"), ("BACKWARD", "Backward")], default="FORWARD")
    finite_by_machine = models.BooleanField(default=True)
    allow_alternate_resources = models.BooleanField(default=True)
    respect_industrial_calendar = models.BooleanField(default=True)
    dispatch_rule = models.CharField(max_length=16, choices=[
        ("EDD", "Earliest Due Date"), ("SPT", "Shortest Processing Time"),
        ("CR", "Critical Ratio"), ("PRIORITY", "Prioridade comercial"),
        ("SETUP_MIN", "Minimizar setup"),
    ], default="EDD")
    minimize_setups = models.BooleanField(default=True)
    campaign_mode = models.BooleanField(default=False)

    class Meta:
        ordering = ["-created_at"]
        constraints = [
            models.CheckConstraint(condition=models.Q(horizon_end__gte=models.F("horizon_start")), name="ck_intsched_horizon"),
        ]
        indexes = [models.Index(fields=["plant", "status", "horizon_start"], name="ix_intsched_plant_status")]

    def __str__(self):
        return self.name


class IntegratedScheduleBlock(TimeStampedModel):
    class BlockType(models.TextChoices):
        PRODUCTION = "PRODUCTION", "Produção"
        MAINTENANCE = "MAINTENANCE", "Manutenção"
        CAPACITY_LOSS = "CAPACITY_LOSS", "Perda de capacidade"

    scenario = models.ForeignKey(IntegratedScheduleScenario, on_delete=models.CASCADE, related_name="blocks")
    block_type = models.CharField(max_length=20, choices=BlockType.choices)
    work_center = models.ForeignKey(WorkCenter, on_delete=models.PROTECT, related_name="integrated_schedule_blocks")
    machine = models.ForeignKey(Machine, null=True, blank=True, on_delete=models.SET_NULL, related_name="integrated_schedule_blocks")
    source_type = models.CharField(max_length=40)
    source_id = models.CharField(max_length=64)
    source_number = models.CharField(max_length=80, blank=True)
    description = models.CharField(max_length=220, blank=True)
    original_start = models.DateTimeField()
    original_end = models.DateTimeField()
    simulated_start = models.DateTimeField()
    simulated_end = models.DateTimeField()
    required_hours = models.DecimalField(max_digits=12, decimal_places=4, default=0)
    lost_capacity_hours = models.DecimalField(max_digits=12, decimal_places=4, default=0)
    late_hours = models.DecimalField(max_digits=12, decimal_places=4, default=0)
    details = models.JSONField(default=dict, blank=True)
    assignment_reason = models.CharField(max_length=220, blank=True)
    manually_locked = models.BooleanField(default=False)
    sequence_setup_hours = models.DecimalField(max_digits=10, decimal_places=4, default=0)
    dispatch_score = models.DecimalField(max_digits=18, decimal_places=6, default=0)
    sequence_position = models.PositiveIntegerField(default=0)

    class Meta:
        ordering = ["simulated_start", "work_center__code", "block_type"]
        indexes = [
            models.Index(fields=["scenario", "work_center", "simulated_start"], name="ix_intblock_center_time"),
            models.Index(fields=["scenario", "source_type", "source_id"], name="ix_intblock_source"),
        ]
        constraints = [
            models.CheckConstraint(condition=models.Q(original_end__gte=models.F("original_start")), name="ck_intblock_original"),
            models.CheckConstraint(condition=models.Q(simulated_end__gte=models.F("simulated_start")), name="ck_intblock_simulated"),
            models.CheckConstraint(condition=models.Q(required_hours__gte=0), name="ck_intblock_req_nonneg"),
            models.CheckConstraint(condition=models.Q(lost_capacity_hours__gte=0), name="ck_intblock_loss_nonneg"),
            models.CheckConstraint(condition=models.Q(late_hours__gte=0), name="ck_intblock_late_nonneg"),
        ]


class IntegratedScheduleConflict(TimeStampedModel):
    class ConflictType(models.TextChoices):
        MAINTENANCE_PRODUCTION = "MAINT_PROD", "Manutenção × produção"
        CAPACITY_OVERLOAD = "CAPACITY", "Sobrecarga de capacidade"
        DUE_DATE = "DUE_DATE", "Risco de atraso"
        MACHINE_OVERLAP = "MACHINE", "Conflito de máquina"

    class Severity(models.TextChoices):
        INFO = "INFO", "Informação"
        WARNING = "WARNING", "Atenção"
        CRITICAL = "CRITICAL", "Crítico"

    scenario = models.ForeignKey(IntegratedScheduleScenario, on_delete=models.CASCADE, related_name="conflicts")
    conflict_type = models.CharField(max_length=20, choices=ConflictType.choices)
    severity = models.CharField(max_length=10, choices=Severity.choices, default=Severity.WARNING)
    work_center = models.ForeignKey(WorkCenter, null=True, blank=True, on_delete=models.PROTECT, related_name="integrated_schedule_conflicts")
    production_block = models.ForeignKey(IntegratedScheduleBlock, null=True, blank=True, on_delete=models.CASCADE, related_name="production_conflicts")
    maintenance_block = models.ForeignKey(IntegratedScheduleBlock, null=True, blank=True, on_delete=models.CASCADE, related_name="maintenance_conflicts")
    overlap_hours = models.DecimalField(max_digits=12, decimal_places=4, default=0)
    message = models.TextField()
    details = models.JSONField(default=dict, blank=True)

    class Meta:
        ordering = ["severity", "work_center__code", "created_at"]
        indexes = [models.Index(fields=["scenario", "conflict_type", "severity"], name="ix_intconf_type_sev")]

class PublishedOperationSchedule(TimeStampedModel):
    """Recurso e janela publicados por operação após aprovação de um cenário."""
    operation = models.OneToOneField(
        "production.WorkOrderOperation", on_delete=models.CASCADE, related_name="published_schedule"
    )
    scenario = models.ForeignKey(
        IntegratedScheduleScenario, on_delete=models.PROTECT, related_name="published_operations"
    )
    work_center = models.ForeignKey(
        WorkCenter, on_delete=models.PROTECT, related_name="published_operation_schedules"
    )
    machine = models.ForeignKey(
        Machine, null=True, blank=True, on_delete=models.SET_NULL, related_name="published_operation_schedules"
    )
    planned_start = models.DateTimeField()
    planned_end = models.DateTimeField()
    published_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL,
        related_name="published_operation_schedules"
    )
    published_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["planned_start", "work_center__code"]
        indexes = [models.Index(fields=["work_center", "planned_start"], name="ix_pubop_center_start")]
        constraints = [
            models.CheckConstraint(condition=models.Q(planned_end__gt=models.F("planned_start")), name="ck_pubop_window")
        ]

class IndustrialShiftBreak(TimeStampedModel):
    """Intervalo sem capacidade dentro de um turno regular."""
    shift = models.ForeignKey("masterdata.WorkCenterShift", on_delete=models.CASCADE, related_name="industrial_breaks")
    name = models.CharField(max_length=80, default="Intervalo")
    start_time = models.TimeField()
    end_time = models.TimeField()
    is_active = models.BooleanField(default=True)

    class Meta:
        ordering = ["shift", "start_time"]
        constraints = [
            models.CheckConstraint(condition=models.Q(end_time__gt=models.F("start_time")), name="ck_intshiftbreak_window"),
        ]

    def __str__(self):
        return f"{self.shift} · {self.name}"


class IndustrialCalendarWindow(TimeStampedModel):
    """Exceções de capacidade: hora extra ou fechamento parcial por centro/máquina."""
    class WindowType(models.TextChoices):
        OVERTIME = "OVERTIME", "Hora extra"
        CLOSURE = "CLOSURE", "Fechamento"

    plant = models.ForeignKey(Plant, on_delete=models.CASCADE, related_name="industrial_calendar_windows")
    work_center = models.ForeignKey(WorkCenter, null=True, blank=True, on_delete=models.CASCADE, related_name="industrial_calendar_windows")
    machine = models.ForeignKey(Machine, null=True, blank=True, on_delete=models.CASCADE, related_name="industrial_calendar_windows")
    date = models.DateField()
    start_time = models.TimeField()
    end_time = models.TimeField()
    window_type = models.CharField(max_length=12, choices=WindowType.choices)
    capacity_factor = models.DecimalField(max_digits=6, decimal_places=3, default=1)
    note = models.CharField(max_length=200, blank=True)

    class Meta:
        ordering = ["date", "start_time"]
        indexes = [models.Index(fields=["plant", "date", "window_type"], name="ix_intcal_plant_date")]
        constraints = [
            models.CheckConstraint(condition=models.Q(end_time__gt=models.F("start_time")), name="ck_intcal_window"),
            models.CheckConstraint(condition=models.Q(capacity_factor__gt=0), name="ck_intcal_factor_pos"),
        ]

    def __str__(self):
        return f"{self.plant.code} {self.date} {self.window_type} {self.start_time}-{self.end_time}"


class IntegratedScheduleSegment(TimeStampedModel):
    """Trecho efetivamente trabalhado de um bloco, permitindo operações atravessarem turnos/dias."""
    class SegmentType(models.TextChoices):
        REGULAR = "REGULAR", "Turno regular"
        OVERTIME = "OVERTIME", "Hora extra"

    block = models.ForeignKey(IntegratedScheduleBlock, on_delete=models.CASCADE, related_name="segments")
    segment_type = models.CharField(max_length=12, choices=SegmentType.choices, default=SegmentType.REGULAR)
    start = models.DateTimeField()
    end = models.DateTimeField()
    effective_hours = models.DecimalField(max_digits=12, decimal_places=4, default=0)
    capacity_factor = models.DecimalField(max_digits=7, decimal_places=4, default=1)

    class Meta:
        ordering = ["start"]
        indexes = [models.Index(fields=["block", "start"], name="ix_intseg_block_start")]
        constraints = [
            models.CheckConstraint(condition=models.Q(end__gt=models.F("start")), name="ck_intseg_window"),
            models.CheckConstraint(condition=models.Q(effective_hours__gte=0), name="ck_intseg_hours_nonneg"),
            models.CheckConstraint(condition=models.Q(capacity_factor__gt=0), name="ck_intseg_factor_pos"),
        ]

    def __str__(self):
        return f"{self.block_id} {self.start:%Y-%m-%d %H:%M}"

class ProductFamily(TimeStampedModel):
    """Família de produto usada para campanhas e setups dependentes da sequência."""
    plant = models.ForeignKey(Plant, on_delete=models.CASCADE, related_name="scheduling_product_families")
    code = models.CharField(max_length=40)
    name = models.CharField(max_length=120)
    is_active = models.BooleanField(default=True)

    class Meta:
        ordering = ["plant__code", "code"]
        constraints = [models.UniqueConstraint(fields=["plant", "code"], name="uq_sched_family_plant_code")]

    def __str__(self):
        return f"{self.plant.code}/{self.code}"


class ItemSchedulingProfile(TimeStampedModel):
    """Dados de sequenciamento do item sem poluir o cadastro mestre básico."""
    plant = models.ForeignKey(Plant, on_delete=models.CASCADE, related_name="item_scheduling_profiles")
    item = models.ForeignKey("masterdata.Item", on_delete=models.CASCADE, related_name="scheduling_profiles")
    family = models.ForeignKey(ProductFamily, null=True, blank=True, on_delete=models.SET_NULL, related_name="items")
    commercial_priority = models.PositiveSmallIntegerField(default=50)
    campaign_code = models.CharField(max_length=40, blank=True)

    class Meta:
        ordering = ["plant__code", "item__code"]
        constraints = [
            models.UniqueConstraint(fields=["plant", "item"], name="uq_sched_profile_plant_item"),
            models.CheckConstraint(condition=models.Q(commercial_priority__lte=100), name="ck_sched_priority_lte_100"),
        ]

    def __str__(self):
        return f"{self.plant.code}/{self.item.code}"


class SequenceSetupRule(TimeStampedModel):
    """Matriz de troca from→to por centro/máquina; from NULL representa partida a frio."""
    plant = models.ForeignKey(Plant, on_delete=models.CASCADE, related_name="sequence_setup_rules")
    work_center = models.ForeignKey(WorkCenter, on_delete=models.CASCADE, related_name="sequence_setup_rules")
    machine = models.ForeignKey(Machine, null=True, blank=True, on_delete=models.CASCADE, related_name="sequence_setup_rules")
    from_family = models.ForeignKey(ProductFamily, null=True, blank=True, on_delete=models.CASCADE, related_name="setup_rules_from")
    to_family = models.ForeignKey(ProductFamily, on_delete=models.CASCADE, related_name="setup_rules_to")
    setup_hours = models.DecimalField(max_digits=10, decimal_places=4, default=0)
    is_active = models.BooleanField(default=True)

    class Meta:
        ordering = ["work_center__code", "machine__code", "from_family__code", "to_family__code"]
        constraints = [
            models.UniqueConstraint(fields=["plant", "work_center", "machine", "from_family", "to_family"], name="uq_sequence_setup_rule"),
            models.CheckConstraint(condition=models.Q(setup_hours__gte=0), name="ck_seqsetup_hours_nonneg"),
        ]

    def __str__(self):
        return f"{self.work_center.code}: {self.from_family or 'START'} → {self.to_family} ({self.setup_hours}h)"


class ScheduleOptimizationRun(TimeStampedModel):
    """Execução de otimização multicritério que gera e ranqueia cenários candidatos."""
    class Status(models.TextChoices):
        DRAFT = "DRAFT", "Rascunho"
        RUNNING = "RUNNING", "Executando"
        COMPLETED = "COMPLETED", "Concluído"
        FAILED = "FAILED", "Falhou"

    base_scenario = models.ForeignKey(IntegratedScheduleScenario, on_delete=models.CASCADE, related_name="optimization_runs")
    status = models.CharField(max_length=16, choices=Status.choices, default=Status.DRAFT)
    candidate_count = models.PositiveSmallIntegerField(default=8)
    weights = models.JSONField(default=dict, blank=True)
    best_candidate = models.ForeignKey("ScheduleOptimizationCandidate", null=True, blank=True, on_delete=models.SET_NULL, related_name="+")
    summary = models.JSONField(default=dict, blank=True)
    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL, related_name="schedule_optimization_runs")
    error_message = models.TextField(blank=True)

    class Meta:
        ordering = ["-created_at"]
        constraints = [models.CheckConstraint(condition=models.Q(candidate_count__gte=2, candidate_count__lte=12), name="ck_opt_candidate_count")]

    def __str__(self):
        return f"OPT-{self.pk or 'novo'} · {self.base_scenario.name}"


class ScheduleOptimizationCandidate(TimeStampedModel):
    """Uma solução candidata produzida pelo otimizador e seus KPIs normalizados."""
    run = models.ForeignKey(ScheduleOptimizationRun, on_delete=models.CASCADE, related_name="candidates")
    scenario = models.OneToOneField(IntegratedScheduleScenario, on_delete=models.CASCADE, related_name="optimization_candidate")
    strategy_code = models.CharField(max_length=80)
    rank = models.PositiveSmallIntegerField(default=0)
    objective_score = models.DecimalField(max_digits=18, decimal_places=8, default=0)
    feasible = models.BooleanField(default=True)
    pareto_front = models.BooleanField(default=False)
    metrics = models.JSONField(default=dict, blank=True)
    normalized_metrics = models.JSONField(default=dict, blank=True)

    class Meta:
        ordering = ["rank", "objective_score", "pk"]
        constraints = [models.UniqueConstraint(fields=["run", "strategy_code"], name="uq_opt_run_strategy")]
        indexes = [models.Index(fields=["run", "rank"], name="ix_opt_candidate_rank")]

    def __str__(self):
        return f"{self.run_id}/{self.rank or '-'} · {self.strategy_code}"


class LaborSkill(TimeStampedModel):
    plant = models.ForeignKey(Plant, on_delete=models.CASCADE, related_name="labor_skills")
    code = models.CharField(max_length=40)
    name = models.CharField(max_length=120)
    is_active = models.BooleanField(default=True)

    class Meta:
        ordering = ["plant__code", "code"]
        constraints = [models.UniqueConstraint(fields=["plant", "code"], name="uq_labor_skill_plant_code")]

    def __str__(self):
        return f"{self.code} · {self.name}"


class LaborResource(TimeStampedModel):
    class ResourceType(models.TextChoices):
        OPERATOR = "OPERATOR", "Operador"
        TECHNICIAN = "TECHNICIAN", "Técnico"

    plant = models.ForeignKey(Plant, on_delete=models.CASCADE, related_name="labor_resources")
    user = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL, related_name="finite_labor_resources")
    employee_code = models.CharField(max_length=40)
    name = models.CharField(max_length=120)
    resource_type = models.CharField(max_length=16, choices=ResourceType.choices, default=ResourceType.OPERATOR)
    operator_profile = models.OneToOneField("shopfloor.OperatorProfile", null=True, blank=True, on_delete=models.SET_NULL, related_name="finite_labor_resource")
    technician_profile = models.OneToOneField("maintenance.TechnicianProfile", null=True, blank=True, on_delete=models.SET_NULL, related_name="finite_labor_resource")
    min_rest_hours = models.DecimalField(max_digits=6, decimal_places=2, default=0)
    hourly_cost = models.DecimalField(max_digits=12, decimal_places=4, default=0)
    preference_score = models.PositiveSmallIntegerField(default=50)
    is_active = models.BooleanField(default=True)

    class Meta:
        ordering = ["plant__code", "employee_code"]
        constraints = [
            models.UniqueConstraint(fields=["plant", "employee_code"], name="uq_labor_resource_plant_code"),
            models.CheckConstraint(condition=models.Q(min_rest_hours__gte=0), name="ck_labor_rest_nonneg"),
            models.CheckConstraint(condition=models.Q(hourly_cost__gte=0), name="ck_labor_hourly_cost_nonneg"),
            models.CheckConstraint(condition=models.Q(preference_score__lte=100), name="ck_labor_preference_lte100"),
        ]

    def __str__(self):
        return f"{self.employee_code} · {self.name}"


class LaborResourceSkill(TimeStampedModel):
    labor_resource = models.ForeignKey(LaborResource, on_delete=models.CASCADE, related_name="skills")
    skill = models.ForeignKey(LaborSkill, on_delete=models.PROTECT, related_name="resource_skills")
    proficiency = models.PositiveSmallIntegerField(default=1)
    valid_until = models.DateField(null=True, blank=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=["labor_resource", "skill"], name="uq_labor_resource_skill"),
            models.CheckConstraint(condition=models.Q(proficiency__gte=1) & models.Q(proficiency__lte=5), name="ck_labor_prof_1_5"),
        ]


class LaborShiftAssignment(TimeStampedModel):
    labor_resource = models.ForeignKey(LaborResource, on_delete=models.CASCADE, related_name="shift_assignments")
    shift = models.ForeignKey("masterdata.WorkCenterShift", on_delete=models.CASCADE, related_name="labor_assignments")
    effective_from = models.DateField(null=True, blank=True)
    effective_to = models.DateField(null=True, blank=True)
    is_active = models.BooleanField(default=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=["labor_resource", "shift", "effective_from"], name="uq_labor_shift_effective"),
            models.CheckConstraint(condition=models.Q(effective_to__isnull=True) | models.Q(effective_from__isnull=True) | models.Q(effective_to__gte=models.F("effective_from")), name="ck_labor_shift_dates"),
        ]


class LaborUnavailability(TimeStampedModel):
    labor_resource = models.ForeignKey(LaborResource, on_delete=models.CASCADE, related_name="unavailability")
    start = models.DateTimeField()
    end = models.DateTimeField()
    reason = models.CharField(max_length=160, blank=True)

    class Meta:
        ordering = ["start"]
        constraints = [models.CheckConstraint(condition=models.Q(end__gt=models.F("start")), name="ck_labor_unavailability_window")]


class OperationLaborRequirement(TimeStampedModel):
    operation = models.ForeignKey("production.WorkOrderOperation", on_delete=models.CASCADE, related_name="labor_requirements")
    skill = models.ForeignKey(LaborSkill, on_delete=models.PROTECT, related_name="operation_requirements")
    min_workers = models.PositiveSmallIntegerField(default=1)
    min_proficiency = models.PositiveSmallIntegerField(default=1)
    allow_shift_handoff = models.BooleanField(default=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=["operation", "skill"], name="uq_operation_labor_skill"),
            models.CheckConstraint(condition=models.Q(min_workers__gte=1), name="ck_operation_labor_workers_pos"),
            models.CheckConstraint(condition=models.Q(min_proficiency__gte=1) & models.Q(min_proficiency__lte=5), name="ck_operation_labor_prof_1_5"),
        ]


class ScheduleSolverLaborAssignment(TimeStampedModel):
    run = models.ForeignKey("ScheduleSolverRun", on_delete=models.CASCADE, related_name="labor_assignments")
    assignment = models.ForeignKey("ScheduleSolverAssignment", on_delete=models.CASCADE, related_name="labor_assignments")
    segment = models.ForeignKey("ScheduleSolverSegment", null=True, blank=True, on_delete=models.CASCADE, related_name="labor_assignments")
    operation = models.ForeignKey("production.WorkOrderOperation", on_delete=models.CASCADE, related_name="solver_labor_assignments")
    labor_resource = models.ForeignKey(LaborResource, on_delete=models.PROTECT, related_name="solver_assignments")
    skill = models.ForeignKey(LaborSkill, on_delete=models.PROTECT, related_name="solver_assignments")
    start = models.DateTimeField()
    end = models.DateTimeField()
    shift_name = models.CharField(max_length=60, blank=True)
    is_handoff = models.BooleanField(default=False)

    class Meta:
        ordering = ["start", "labor_resource__employee_code"]
        indexes = [models.Index(fields=["run", "labor_resource", "start"], name="ix_solver_labor_run_time")]
        constraints = [models.CheckConstraint(condition=models.Q(end__gt=models.F("start")), name="ck_solver_labor_window")]


class LaborRuleSet(TimeStampedModel):
    """Política parametrizável de jornada/custo. Não codifica uma legislação específica; a empresa configura sua regra vigente."""
    plant = models.ForeignKey(Plant, on_delete=models.CASCADE, related_name="labor_rule_sets")
    code = models.CharField(max_length=40)
    name = models.CharField(max_length=120)
    effective_from = models.DateField()
    effective_to = models.DateField(null=True, blank=True)
    normal_daily_hours = models.DecimalField(max_digits=6, decimal_places=2, default=8)
    max_daily_hours = models.DecimalField(max_digits=6, decimal_places=2, default=10)
    max_weekly_hours = models.DecimalField(max_digits=6, decimal_places=2, default=44)
    minimum_rest_hours = models.DecimalField(max_digits=6, decimal_places=2, default=11)
    overtime_multiplier = models.DecimalField(max_digits=6, decimal_places=3, default=1.5)
    night_premium_percent = models.DecimalField(max_digits=6, decimal_places=3, default=20)
    night_start = models.TimeField(default="22:00")
    night_end = models.TimeField(default="05:00")
    overtime_allowed = models.BooleanField(default=True)
    is_active = models.BooleanField(default=True)

    class Meta:
        ordering = ["plant__code", "-effective_from"]
        constraints = [
            models.UniqueConstraint(fields=["plant", "code", "effective_from"], name="uq_labor_ruleset_effective"),
            models.CheckConstraint(condition=models.Q(normal_daily_hours__gte=0), name="ck_labor_rule_normal_nonneg"),
            models.CheckConstraint(condition=models.Q(max_daily_hours__gte=models.F("normal_daily_hours")), name="ck_labor_rule_daily_ge_normal"),
            models.CheckConstraint(condition=models.Q(max_weekly_hours__gt=0), name="ck_labor_rule_weekly_pos"),
            models.CheckConstraint(condition=models.Q(overtime_multiplier__gte=1), name="ck_labor_rule_ot_ge1"),
            models.CheckConstraint(condition=models.Q(night_premium_percent__gte=0), name="ck_labor_rule_night_nonneg"),
        ]

    def __str__(self):
        return f"{self.plant.code}/{self.code}"


class ScheduleSolverLaborCost(TimeStampedModel):
    labor_assignment = models.OneToOneField(ScheduleSolverLaborAssignment, on_delete=models.CASCADE, related_name="cost_breakdown")
    normal_minutes = models.PositiveIntegerField(default=0)
    overtime_minutes = models.PositiveIntegerField(default=0)
    night_minutes = models.PositiveIntegerField(default=0)
    base_cost = models.DecimalField(max_digits=16, decimal_places=4, default=0)
    overtime_premium = models.DecimalField(max_digits=16, decimal_places=4, default=0)
    night_premium = models.DecimalField(max_digits=16, decimal_places=4, default=0)
    total_cost = models.DecimalField(max_digits=16, decimal_places=4, default=0)
    rule_set = models.ForeignKey(LaborRuleSet, null=True, blank=True, on_delete=models.SET_NULL, related_name="solver_costs")
    details = models.JSONField(default=dict, blank=True)

    class Meta:
        ordering = ["labor_assignment__start", "labor_assignment__labor_resource__employee_code"]
        constraints = [
            models.CheckConstraint(condition=models.Q(base_cost__gte=0), name="ck_labor_cost_base_nonneg"),
            models.CheckConstraint(condition=models.Q(total_cost__gte=0), name="ck_labor_cost_total_nonneg"),
        ]


class ScheduleSolverRun(TimeStampedModel):
    """Execução do solver CP-SAT para programação finita global."""
    class Status(models.TextChoices):
        DRAFT = "DRAFT", "Rascunho"
        RUNNING = "RUNNING", "Executando"
        OPTIMAL = "OPTIMAL", "Ótimo / dentro do gap"
        FEASIBLE = "FEASIBLE", "Factível"
        INFEASIBLE = "INFEASIBLE", "Inviável"
        UNKNOWN = "UNKNOWN", "Sem solução"
        FAILED = "FAILED", "Falhou"
        CANCELLED = "CANCELLED", "Cancelado"

    scenario = models.ForeignKey(IntegratedScheduleScenario, on_delete=models.CASCADE, related_name="solver_runs")
    status = models.CharField(max_length=16, choices=Status.choices, default=Status.DRAFT)
    solver = models.CharField(max_length=24, default="CP-SAT")
    time_limit_seconds = models.PositiveIntegerField(default=30)
    workers = models.PositiveSmallIntegerField(default=8)
    time_granularity_minutes = models.PositiveSmallIntegerField(default=5)
    weights = models.JSONField(default=dict, blank=True)
    objective_value = models.DecimalField(max_digits=24, decimal_places=6, null=True, blank=True)
    best_bound = models.DecimalField(max_digits=24, decimal_places=6, null=True, blank=True)
    wall_time_seconds = models.DecimalField(max_digits=16, decimal_places=4, default=0)
    conflicts = models.PositiveIntegerField(default=0)
    branches = models.PositiveBigIntegerField(default=0)
    summary = models.JSONField(default=dict, blank=True)
    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL, related_name="schedule_solver_runs")
    error_message = models.TextField(blank=True)
    execution_mode = models.CharField(max_length=12, choices=[("SYNC", "Síncrono"), ("ASYNC", "Assíncrono")], default="SYNC")
    relative_gap_limit = models.DecimalField(max_digits=8, decimal_places=6, default=0)
    warm_start_enabled = models.BooleanField(default=True)
    preemptive_operations = models.BooleanField(default=False)
    max_consecutive_minutes = models.PositiveIntegerField(default=240)
    handoff_penalty = models.PositiveIntegerField(default=5)
    use_labor_constraints = models.BooleanField(default=True)
    use_labor_costs = models.BooleanField(default=True)
    labor_rule_set = models.ForeignKey(LaborRuleSet, null=True, blank=True, on_delete=models.SET_NULL, related_name="solver_runs")
    labor_cost_total = models.DecimalField(max_digits=18, decimal_places=4, default=0)
    warm_start_source = models.CharField(max_length=40, blank=True)
    warm_start_scenario = models.ForeignKey(
        IntegratedScheduleScenario, null=True, blank=True, on_delete=models.SET_NULL,
        related_name="solver_warm_start_runs"
    )
    celery_task_id = models.CharField(max_length=255, blank=True, db_index=True)
    cancel_requested_at = models.DateTimeField(null=True, blank=True)
    cancellation_reason = models.CharField(max_length=255, blank=True)
    started_at = models.DateTimeField(null=True, blank=True)
    finished_at = models.DateTimeField(null=True, blank=True)
    last_incumbent_at = models.DateTimeField(null=True, blank=True)
    progress = models.JSONField(default=dict, blank=True)

    class Meta:
        ordering = ["-created_at"]
        constraints = [
            models.CheckConstraint(condition=models.Q(time_limit_seconds__gte=1), name="ck_solver_time_limit_pos"),
            models.CheckConstraint(condition=models.Q(workers__gte=1), name="ck_solver_workers_pos"),
            models.CheckConstraint(condition=models.Q(time_granularity_minutes__gte=1), name="ck_solver_granularity_pos"),
            models.CheckConstraint(condition=models.Q(max_consecutive_minutes__gte=1), name="ck_solver_max_consecutive_pos"),
        ]
        indexes = [models.Index(fields=["scenario", "status"], name="ix_solver_scenario_status")]

    def __str__(self):
        return f"SOLVER-{self.pk or 'novo'} · {self.scenario.name}"


class ScheduleSolverAssignment(TimeStampedModel):
    """Resultado persistido do CP-SAT por operação."""
    run = models.ForeignKey(ScheduleSolverRun, on_delete=models.CASCADE, related_name="assignments")
    operation = models.ForeignKey("production.WorkOrderOperation", on_delete=models.CASCADE, related_name="solver_assignments")
    work_center = models.ForeignKey(WorkCenter, on_delete=models.PROTECT, related_name="solver_assignments")
    machine = models.ForeignKey(Machine, null=True, blank=True, on_delete=models.SET_NULL, related_name="solver_assignments")
    start = models.DateTimeField()
    end = models.DateTimeField()
    duration_minutes = models.PositiveIntegerField()
    setup_minutes_before = models.PositiveIntegerField(default=0)
    is_alternate_resource = models.BooleanField(default=False)
    tardiness_minutes = models.PositiveIntegerField(default=0)
    details = models.JSONField(default=dict, blank=True)

    class Meta:
        ordering = ["start", "work_center__code", "machine__code"]
        constraints = [
            models.UniqueConstraint(fields=["run", "operation"], name="uq_solver_run_operation"),
            models.CheckConstraint(condition=models.Q(end__gte=models.F("start")), name="ck_solver_assignment_window"),
        ]
        indexes = [
            models.Index(fields=["run", "machine", "start"], name="ix_solver_assignment_machine"),
            models.Index(fields=["run", "work_center", "start"], name="ix_solver_assignment_center"),
        ]


class ScheduleSolverSegment(TimeStampedModel):
    """Trecho de execução CP-SAT de uma operação preemptiva/segmentável."""
    assignment = models.ForeignKey(ScheduleSolverAssignment, on_delete=models.CASCADE, related_name="segments")
    sequence = models.PositiveSmallIntegerField()
    start = models.DateTimeField()
    end = models.DateTimeField()
    processing_minutes = models.PositiveIntegerField()
    calendar_kind = models.CharField(max_length=20, default="REGULAR")
    shift_name = models.CharField(max_length=60, blank=True)
    handoff_after = models.BooleanField(default=False)
    details = models.JSONField(default=dict, blank=True)

    class Meta:
        ordering = ["assignment", "sequence"]
        constraints = [
            models.UniqueConstraint(fields=["assignment", "sequence"], name="uq_solver_segment_sequence"),
            models.CheckConstraint(condition=models.Q(end__gt=models.F("start")), name="ck_solver_segment_window"),
            models.CheckConstraint(condition=models.Q(processing_minutes__gt=0), name="ck_solver_segment_minutes_pos"),
        ]
        indexes = [models.Index(fields=["assignment", "start"], name="ix_solver_segment_start")]

    def __str__(self):
        return f"{self.assignment_id} · segmento {self.sequence}"


class ScheduleSolverIncumbent(TimeStampedModel):
    """Histórico dos incumbents encontrados durante uma execução CP-SAT."""
    run = models.ForeignKey(ScheduleSolverRun, on_delete=models.CASCADE, related_name="incumbents")
    sequence = models.PositiveIntegerField()
    objective_value = models.DecimalField(max_digits=24, decimal_places=6)
    best_bound = models.DecimalField(max_digits=24, decimal_places=6, null=True, blank=True)
    relative_gap = models.DecimalField(max_digits=12, decimal_places=8, null=True, blank=True)
    wall_time_seconds = models.DecimalField(max_digits=16, decimal_places=4, default=0)
    solution_count = models.PositiveIntegerField(default=0)
    summary = models.JSONField(default=dict, blank=True)

    class Meta:
        ordering = ["run", "sequence"]
        constraints = [models.UniqueConstraint(fields=["run", "sequence"], name="uq_solver_incumbent_sequence")]
        indexes = [models.Index(fields=["run", "sequence"], name="ix_solver_incumbent_run_seq")]

    def __str__(self):
        return f"{self.run_id} · incumbent {self.sequence}"


class ProductionSchedulePublication(TimeStampedModel):
    """Versão oficial publicada da programação de produção."""
    class Status(models.TextChoices):
        PUBLISHED = "PUBLISHED", "Publicada"
        SUPERSEDED = "SUPERSEDED", "Substituída"
        CANCELLED = "CANCELLED", "Cancelada"

    plant = models.ForeignKey(Plant, on_delete=models.PROTECT, related_name="schedule_publications")
    scenario = models.ForeignKey(IntegratedScheduleScenario, on_delete=models.PROTECT, related_name="publications")
    solver_run = models.ForeignKey("ScheduleSolverRun", null=True, blank=True, on_delete=models.PROTECT, related_name="publications")
    version = models.PositiveIntegerField()
    status = models.CharField(max_length=16, choices=Status.choices, default=Status.PUBLISHED)
    frozen_until = models.DateTimeField(null=True, blank=True)
    published_by = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL, related_name="production_schedule_publications")
    published_at = models.DateTimeField(auto_now_add=True)
    notes = models.TextField(blank=True)
    metrics = models.JSONField(default=dict, blank=True)

    class Meta:
        ordering = ["-published_at", "-version"]
        constraints = [models.UniqueConstraint(fields=["plant", "version"], name="uq_schedule_publication_version")]
        indexes = [models.Index(fields=["plant", "status", "published_at"], name="ix_schedpub_plant_status")]

    def __str__(self):
        return f"{self.plant.code} · v{self.version}"


class PublishedExecutionSlot(TimeStampedModel):
    """Slot oficial versionado usado pelo chão de fábrica e pelo planned × actual."""
    class Status(models.TextChoices):
        PLANNED = "PLANNED", "Planejado"
        READY = "READY", "Pronto"
        RUNNING = "RUNNING", "Executando"
        COMPLETED = "COMPLETED", "Concluído"
        MISSED = "MISSED", "Não executado"

    publication = models.ForeignKey(ProductionSchedulePublication, on_delete=models.CASCADE, related_name="slots")
    operation = models.ForeignKey("production.WorkOrderOperation", on_delete=models.PROTECT, related_name="official_schedule_slots")
    work_center = models.ForeignKey(WorkCenter, on_delete=models.PROTECT, related_name="official_schedule_slots")
    machine = models.ForeignKey(Machine, null=True, blank=True, on_delete=models.SET_NULL, related_name="official_schedule_slots")
    planned_start = models.DateTimeField()
    planned_end = models.DateTimeField()
    frozen = models.BooleanField(default=False)
    status = models.CharField(max_length=16, choices=Status.choices, default=Status.PLANNED)
    actual_start = models.DateTimeField(null=True, blank=True)
    actual_end = models.DateTimeField(null=True, blank=True)
    team_snapshot = models.JSONField(default=list, blank=True)
    source_assignment = models.ForeignKey("ScheduleSolverAssignment", null=True, blank=True, on_delete=models.SET_NULL, related_name="published_execution_slots")
    details = models.JSONField(default=dict, blank=True)

    class Meta:
        ordering = ["planned_start", "work_center__code"]
        constraints = [
            models.UniqueConstraint(fields=["publication", "operation"], name="uq_pubslot_publication_operation"),
            models.CheckConstraint(condition=models.Q(planned_end__gt=models.F("planned_start")), name="ck_pubslot_window"),
        ]
        indexes = [
            models.Index(fields=["publication", "planned_start"], name="ix_pubslot_pub_start"),
            models.Index(fields=["machine", "planned_start"], name="ix_pubslot_machine_start"),
        ]


class ScheduleExecutionDeviation(TimeStampedModel):
    class DeviationType(models.TextChoices):
        LATE_START = "LATE_START", "Início atrasado"
        LATE_FINISH = "LATE_FINISH", "Fim atrasado"
        MACHINE_BREAKDOWN = "MACHINE_BREAKDOWN", "Quebra de máquina"
        MATERIAL_SHORTAGE = "MATERIAL_SHORTAGE", "Falta de material"
        LABOR_ABSENCE = "LABOR_ABSENCE", "Ausência de operador"
        MANUAL = "MANUAL", "Ocorrência manual"

    slot = models.ForeignKey(PublishedExecutionSlot, on_delete=models.CASCADE, related_name="deviations")
    deviation_type = models.CharField(max_length=24, choices=DeviationType.choices)
    detected_at = models.DateTimeField()
    deviation_minutes = models.IntegerField(default=0)
    details = models.JSONField(default=dict, blank=True)
    resolved_at = models.DateTimeField(null=True, blank=True)
    
    class Meta:
        ordering = ["-detected_at"]
        indexes = [models.Index(fields=["slot", "deviation_type", "detected_at"], name="ix_execdev_slot_type")]


class ReschedulingTrigger(TimeStampedModel):
    """Evento operacional que pode disparar um novo cenário e solver."""
    class TriggerType(models.TextChoices):
        MACHINE_BREAKDOWN = "MACHINE_BREAKDOWN", "Quebra de máquina"
        MATERIAL_SHORTAGE = "MATERIAL_SHORTAGE", "Falta de material"
        LABOR_ABSENCE = "LABOR_ABSENCE", "Ausência de operador"
        PRIORITY_CHANGE = "PRIORITY_CHANGE", "Mudança de prioridade"
        MANUAL = "MANUAL", "Manual"

    class Status(models.TextChoices):
        NEW = "NEW", "Novo"
        PROCESSING = "PROCESSING", "Processando"
        RESCHEDULED = "RESCHEDULED", "Cenário preparado"
        SOLVING = "SOLVING", "Otimizando"
        READY = "READY", "Plano recuperado pronto"
        PUBLISHED = "PUBLISHED", "Plano recuperado publicado"
        IGNORED = "IGNORED", "Ignorado"
        FAILED = "FAILED", "Falhou"

    plant = models.ForeignKey(Plant, on_delete=models.PROTECT, related_name="rescheduling_triggers")
    publication = models.ForeignKey(ProductionSchedulePublication, null=True, blank=True, on_delete=models.SET_NULL, related_name="rescheduling_triggers")
    trigger_type = models.CharField(max_length=24, choices=TriggerType.choices)
    source_type = models.CharField(max_length=60, blank=True)
    source_id = models.CharField(max_length=80, blank=True)
    affected_from = models.DateTimeField()
    idempotency_key = models.CharField(max_length=160, unique=True)
    status = models.CharField(max_length=16, choices=Status.choices, default=Status.NEW)
    auto_reschedule = models.BooleanField(default=True)
    payload = models.JSONField(default=dict, blank=True)
    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL, related_name="rescheduling_triggers")
    resulting_scenario = models.ForeignKey(IntegratedScheduleScenario, null=True, blank=True, on_delete=models.SET_NULL, related_name="rescheduling_triggers")
    resulting_solver_run = models.ForeignKey("ScheduleSolverRun", null=True, blank=True, on_delete=models.SET_NULL, related_name="rescheduling_triggers")
    processed_at = models.DateTimeField(null=True, blank=True)
    error_message = models.TextField(blank=True)
    recovery_summary = models.JSONField(default=dict, blank=True)
    auto_solver_enqueued_at = models.DateTimeField(null=True, blank=True)
    approved_at = models.DateTimeField(null=True, blank=True)
    approved_by = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL, related_name="approved_rescheduling_triggers")
    severity = models.CharField(max_length=12, choices=[("LOW", "Baixa"), ("MEDIUM", "Média"), ("HIGH", "Alta"), ("CRITICAL", "Crítica")], default="MEDIUM")
    impact_summary = models.JSONField(default=dict, blank=True)
    recovery_eta_seconds = models.PositiveIntegerField(default=0)
    auto_publish_attempted_at = models.DateTimeField(null=True, blank=True)
    auto_published_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ["-created_at"]
        indexes = [models.Index(fields=["plant", "status", "affected_from"], name="ix_replantrigger_status")]


class RecoveryPolicy(TimeStampedModel):
    """Política por planta para triagem, geração e auto-publicação de recovery plans."""
    plant = models.OneToOneField(Plant, on_delete=models.CASCADE, related_name="recovery_policy")
    is_active = models.BooleanField(default=True)
    candidate_count = models.PositiveSmallIntegerField(default=3)
    solver_time_limit_seconds = models.PositiveIntegerField(default=180)
    auto_publish_enabled = models.BooleanField(default=False)
    max_risk_score = models.DecimalField(max_digits=6, decimal_places=2, default=20)
    max_moved_operations = models.PositiveIntegerField(default=3)
    max_late_operations = models.PositiveIntegerField(default=0)
    max_machine_changes = models.PositiveIntegerField(default=1)
    max_impacted_sales_orders = models.PositiveIntegerField(default=0)
    max_delay_minutes = models.PositiveIntegerField(default=30)

    class Meta:
        ordering = ["plant__code"]
        constraints = [
            models.CheckConstraint(condition=models.Q(candidate_count__gte=1), name="ck_recovery_policy_candidates"),
            models.CheckConstraint(condition=models.Q(solver_time_limit_seconds__gte=1), name="ck_recovery_policy_time"),
            models.CheckConstraint(condition=models.Q(max_risk_score__gte=0), name="ck_recovery_policy_risk"),
        ]

    def __str__(self):
        return f"Recovery policy · {self.plant.code}"


class RecoveryPlan(TimeStampedModel):
    """Alternativa de recuperação pertencente a um único evento de ruptura."""
    class Status(models.TextChoices):
        DRAFT = "DRAFT", "Rascunho"
        QUEUED = "QUEUED", "Na fila"
        SOLVING = "SOLVING", "Otimizando"
        READY = "READY", "Pronto"
        FAILED = "FAILED", "Falhou"
        PUBLISHED = "PUBLISHED", "Publicado"

    trigger = models.ForeignKey("ReschedulingTrigger", on_delete=models.CASCADE, related_name="recovery_plans")
    name = models.CharField(max_length=160)
    strategy = models.CharField(max_length=60, default="BALANCED")
    scenario = models.ForeignKey(IntegratedScheduleScenario, null=True, blank=True, on_delete=models.SET_NULL, related_name="recovery_plans")
    solver_run = models.ForeignKey("ScheduleSolverRun", null=True, blank=True, on_delete=models.SET_NULL, related_name="recovery_plans")
    status = models.CharField(max_length=16, choices=Status.choices, default=Status.DRAFT)
    rank = models.PositiveSmallIntegerField(default=0)
    risk_score = models.DecimalField(max_digits=8, decimal_places=2, default=0)
    low_risk = models.BooleanField(default=False)
    auto_publish_eligible = models.BooleanField(default=False)
    metrics = models.JSONField(default=dict, blank=True)
    impact = models.JSONField(default=dict, blank=True)
    error_message = models.TextField(blank=True)

    class Meta:
        ordering = ["trigger", "rank", "risk_score", "created_at"]
        indexes = [models.Index(fields=["trigger", "status", "rank"], name="ix_recovery_plan_status")]
        constraints = [models.UniqueConstraint(fields=["trigger", "name"], name="uq_recovery_plan_name")]

    def __str__(self):
        return f"Recovery #{self.trigger_id} · {self.name}"

class RecoveryCommercialImpact(TimeStampedModel):
    """Exact SalesOrderLine impact for a recovery trigger/plan when source-aware pegging exists."""
    class PromiseStatus(models.TextChoices):
        ON_TIME = "ON_TIME", "No prazo"
        AT_RISK = "AT_RISK", "Em risco"
        LATE = "LATE", "Atrasado"
        RECOVERED = "RECOVERED", "Recuperado"
        UNKNOWN = "UNKNOWN", "Indeterminado"

    trigger = models.ForeignKey(ReschedulingTrigger, on_delete=models.CASCADE, related_name="commercial_impacts")
    recovery_plan = models.ForeignKey(RecoveryPlan, null=True, blank=True, on_delete=models.CASCADE, related_name="commercial_impacts")
    sales_order_line = models.ForeignKey("demand.SalesOrderLine", on_delete=models.CASCADE, related_name="recovery_impacts")
    pegged_quantity = models.DecimalField(max_digits=18, decimal_places=4)
    requested_date = models.DateField()
    current_promise_date = models.DateField(null=True, blank=True)
    recovered_promise_date = models.DateField(null=True, blank=True)
    promise_delta_days = models.IntegerField(default=0)
    promise_status = models.CharField(max_length=16, choices=PromiseStatus.choices, default=PromiseStatus.UNKNOWN)
    pegging_method = models.CharField(max_length=32, default="EXACT_MRP_SOURCE")
    details = models.JSONField(default=dict, blank=True)
    # 0.9.8 — ownership for SLA reporting/escalation routing.
    responsible_area = models.CharField(max_length=40, blank=True)
    responsible_user = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL,
        related_name="responsible_recovery_commercial_impacts",
    )

    class Meta:
        ordering = ["sales_order_line__sales_order__number", "sales_order_line__line_number"]
        constraints = [models.UniqueConstraint(fields=["trigger", "recovery_plan", "sales_order_line"], name="uq_recovery_commercial_impact")]
        indexes = [models.Index(fields=["trigger", "promise_status"], name="ix_reccomm_trigger_status")]


class CommercialPromiseAlert(TimeStampedModel):
    class Status(models.TextChoices):
        OPEN = "OPEN", "Aberto"
        ACKNOWLEDGED = "ACKNOWLEDGED", "Reconhecido"
        RESOLVED = "RESOLVED", "Resolvido"
    trigger = models.ForeignKey(ReschedulingTrigger, on_delete=models.CASCADE, related_name="commercial_alerts")
    recovery_plan = models.ForeignKey(RecoveryPlan, null=True, blank=True, on_delete=models.CASCADE, related_name="commercial_alerts")
    sales_order_line = models.ForeignKey("demand.SalesOrderLine", on_delete=models.CASCADE, related_name="promise_alerts")
    severity = models.CharField(max_length=12, choices=[("LOW","Baixa"),("MEDIUM","Média"),("HIGH","Alta"),("CRITICAL","Crítica")], default="MEDIUM")
    status = models.CharField(max_length=16, choices=Status.choices, default=Status.OPEN)
    message = models.TextField()
    acknowledged_by = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL, related_name="acknowledged_commercial_alerts")
    acknowledged_at = models.DateTimeField(null=True, blank=True)
    details = models.JSONField(default=dict, blank=True)
    class Meta:
        ordering = ["-created_at"]
        indexes = [models.Index(fields=["status", "severity", "created_at"], name="ix_commalert_status_sev")]


# 0.7.4 — ATP/CTP comercial e gestão formal de promessas
class SalesOrderPromise(TimeStampedModel):
    class Source(models.TextChoices):
        ATP_CTP = "ATP_CTP", "ATP/CTP"
        RECOVERY = "RECOVERY", "Recovery"
        MANUAL = "MANUAL", "Manual"
    class Status(models.TextChoices):
        PENDING = "PENDING", "Pendente"
        APPROVED = "APPROVED", "Aprovada"
        REJECTED = "REJECTED", "Rejeitada"
        SUPERSEDED = "SUPERSEDED", "Substituída"

    sales_order_line = models.ForeignKey("demand.SalesOrderLine", on_delete=models.CASCADE, related_name="promise_history")
    source = models.CharField(max_length=16, choices=Source.choices)
    proposed_date = models.DateField()
    previous_approved_date = models.DateField(null=True, blank=True)
    quantity = models.DecimalField(max_digits=18, decimal_places=4)
    status = models.CharField(max_length=16, choices=Status.choices, default=Status.PENDING)
    trigger = models.ForeignKey(ReschedulingTrigger, null=True, blank=True, on_delete=models.SET_NULL, related_name="promise_proposals")
    recovery_plan = models.ForeignKey(RecoveryPlan, null=True, blank=True, on_delete=models.SET_NULL, related_name="promise_proposals")
    atp_result = models.JSONField(default=dict, blank=True)
    ctp_result = models.JSONField(default=dict, blank=True)
    rationale = models.TextField(blank=True)
    proposed_by = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL, related_name="sales_promises_proposed")
    decided_by = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL, related_name="sales_promises_decided")
    decided_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["sales_order_line", "status", "created_at"], name="ix_solpromise_line_status"),
            models.Index(fields=["status", "proposed_date"], name="ix_solpromise_status_date"),
        ]


class CommercialServiceCase(TimeStampedModel):
    class Status(models.TextChoices):
        OPEN = "OPEN", "Aberto"
        IN_REVIEW = "IN_REVIEW", "Em análise"
        WAITING_CUSTOMER = "WAITING_CUSTOMER", "Aguardando cliente"
        CLOSED = "CLOSED", "Fechado"
    class Priority(models.TextChoices):
        LOW = "LOW", "Baixa"
        MEDIUM = "MEDIUM", "Média"
        HIGH = "HIGH", "Alta"
        CRITICAL = "CRITICAL", "Crítica"

    sales_order_line = models.ForeignKey("demand.SalesOrderLine", on_delete=models.CASCADE, related_name="commercial_cases")
    trigger = models.ForeignKey(ReschedulingTrigger, null=True, blank=True, on_delete=models.SET_NULL, related_name="commercial_cases")
    recovery_plan = models.ForeignKey(RecoveryPlan, null=True, blank=True, on_delete=models.SET_NULL, related_name="commercial_cases")
    promise = models.ForeignKey(SalesOrderPromise, null=True, blank=True, on_delete=models.SET_NULL, related_name="service_cases")
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.OPEN)
    priority = models.CharField(max_length=12, choices=Priority.choices, default=Priority.MEDIUM)
    reason = models.CharField(max_length=40, default="PROMISE_CHANGE")
    owner = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL, related_name="commercial_service_cases")
    notes = models.TextField(blank=True)

    class Meta:
        ordering = ["-created_at"]
        indexes = [models.Index(fields=["status", "priority", "created_at"], name="ix_comcase_status_priority")]


# 0.7.5 — confirmação comercial e comunicação ao cliente
class SalesOrderCommercialContact(TimeStampedModel):
    class Channel(models.TextChoices):
        EMAIL = "EMAIL", "E-mail"
        API = "API", "API"
        MANUAL = "MANUAL", "Manual"

    sales_order = models.ForeignKey("demand.SalesOrder", on_delete=models.CASCADE, related_name="commercial_contacts")
    name = models.CharField(max_length=160)
    email = models.EmailField(blank=True)
    api_url = models.URLField(blank=True)
    preferred_channel = models.CharField(max_length=12, choices=Channel.choices, default=Channel.EMAIL)
    is_active = models.BooleanField(default=True)

    class Meta:
        ordering = ["sales_order", "name"]
        indexes = [models.Index(fields=["sales_order", "is_active"], name="ix_socontact_order_active")]


class CustomerPromiseResponse(TimeStampedModel):
    class Response(models.TextChoices):
        ACCEPTED = "ACCEPTED", "Aceita"
        REJECTED = "REJECTED", "Rejeitada"
        COUNTERPROPOSED = "COUNTERPROPOSED", "Contraproposta"
    class Channel(models.TextChoices):
        EMAIL = "EMAIL", "E-mail"
        API = "API", "API"
        PHONE = "PHONE", "Telefone"
        MANUAL = "MANUAL", "Manual"

    promise = models.ForeignKey(SalesOrderPromise, on_delete=models.CASCADE, related_name="customer_responses")
    response = models.CharField(max_length=20, choices=Response.choices)
    channel = models.CharField(max_length=12, choices=Channel.choices, default=Channel.MANUAL)
    confirmed_date = models.DateField(null=True, blank=True)
    counterproposed_date = models.DateField(null=True, blank=True)
    notes = models.TextField(blank=True)
    external_reference = models.CharField(max_length=120, blank=True)
    received_at = models.DateTimeField(default=timezone.now)
    received_by = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL, related_name="customer_promise_responses_received")

    class Meta:
        ordering = ["-received_at", "-created_at"]
        indexes = [models.Index(fields=["promise", "response", "received_at"], name="ix_custresp_promise_resp")]


class CommercialCommunication(TimeStampedModel):
    class Channel(models.TextChoices):
        EMAIL = "EMAIL", "E-mail"
        API = "API", "API"
        MANUAL = "MANUAL", "Manual"
    class Direction(models.TextChoices):
        OUTBOUND = "OUTBOUND", "Saída"
        INBOUND = "INBOUND", "Entrada"
    class Status(models.TextChoices):
        PENDING = "PENDING", "Pendente"
        SENT = "SENT", "Enviada"
        FAILED = "FAILED", "Falhou"

    promise = models.ForeignKey(SalesOrderPromise, on_delete=models.CASCADE, related_name="communications")
    service_case = models.ForeignKey(CommercialServiceCase, null=True, blank=True, on_delete=models.SET_NULL, related_name="communications")
    contact = models.ForeignKey(SalesOrderCommercialContact, null=True, blank=True, on_delete=models.SET_NULL, related_name="communications")
    channel = models.CharField(max_length=12, choices=Channel.choices)
    direction = models.CharField(max_length=12, choices=Direction.choices, default=Direction.OUTBOUND)
    status = models.CharField(max_length=12, choices=Status.choices, default=Status.PENDING)
    subject = models.CharField(max_length=240, blank=True)
    body = models.TextField(blank=True)
    payload = models.JSONField(default=dict, blank=True)
    external_reference = models.CharField(max_length=160, blank=True)
    idempotency_key = models.CharField(max_length=160, unique=True)
    sent_at = models.DateTimeField(null=True, blank=True)
    error = models.TextField(blank=True)

    class Meta:
        ordering = ["-created_at"]
        indexes = [models.Index(fields=["promise", "status", "created_at"], name="ix_comm_promise_status")]


# 0.7.6 — OTIF e gestão de nível de serviço
class OTIFLineResult(TimeStampedModel):
    class Reference(models.TextChoices):
        REQUESTED = "REQUESTED", "Solicitada"
        APPROVED_PROMISE = "APPROVED_PROMISE", "Promessa aprovada"
        CUSTOMER_ACCEPTED = "CUSTOMER_ACCEPTED", "Aceita pelo cliente"

    sales_order_line = models.ForeignKey("demand.SalesOrderLine", on_delete=models.CASCADE, related_name="otif_results")
    reference = models.CharField(max_length=24, choices=Reference.choices, default=Reference.CUSTOMER_ACCEPTED)
    requested_date = models.DateField()
    approved_promise_date = models.DateField(null=True, blank=True)
    accepted_date = models.DateField(null=True, blank=True)
    reference_date = models.DateField()
    ordered_quantity = models.DecimalField(max_digits=18, decimal_places=4)
    delivered_quantity = models.DecimalField(max_digits=18, decimal_places=4, default=0)
    first_delivery_date = models.DateField(null=True, blank=True)
    full_delivery_date = models.DateField(null=True, blank=True)
    on_time = models.BooleanField(default=False)
    in_full = models.BooleanField(default=False)
    otif = models.BooleanField(default=False)
    days_late = models.IntegerField(default=0)
    primary_cause = models.CharField(max_length=32, blank=True)
    cause_details = models.JSONField(default=dict, blank=True)
    evaluated_at = models.DateTimeField(default=timezone.now)

    class Meta:
        ordering = ["-evaluated_at"]
        constraints = [models.UniqueConstraint(fields=["sales_order_line", "reference"], name="uq_otif_line_reference")]
        indexes = [
            models.Index(fields=["reference", "otif", "reference_date"], name="ix_otif_ref_flag_date"),
            models.Index(fields=["sales_order_line", "evaluated_at"], name="ix_otif_line_eval"),
        ]


class ServiceLevelCause(TimeStampedModel):
    class Category(models.TextChoices):
        MATERIAL = "MATERIAL", "Material"
        CAPACITY = "CAPACITY", "Capacidade"
        MACHINE = "MACHINE", "Máquina"
        LABOR = "LABOR", "Mão de obra"
        QUALITY = "QUALITY", "Qualidade"
        LOGISTICS = "LOGISTICS", "Logística"
        COMMERCIAL = "COMMERCIAL", "Comercial"
        CUSTOMER = "CUSTOMER", "Cliente"
        UNKNOWN = "UNKNOWN", "Não identificada"

    otif_result = models.ForeignKey(OTIFLineResult, on_delete=models.CASCADE, related_name="causes")
    category = models.CharField(max_length=20, choices=Category.choices, default=Category.UNKNOWN)
    code = models.CharField(max_length=50, blank=True)
    description = models.CharField(max_length=240)
    source_type = models.CharField(max_length=60, blank=True)
    source_id = models.CharField(max_length=80, blank=True)
    minutes_impact = models.PositiveIntegerField(default=0)
    is_primary = models.BooleanField(default=False)
    details = models.JSONField(default=dict, blank=True)

    class Meta:
        ordering = ["-is_primary", "category", "created_at"]
        indexes = [models.Index(fields=["category", "is_primary"], name="ix_slcause_category_primary")]

# 0.7.7 — gestão gerencial de nível de serviço
class ServiceLevelTarget(TimeStampedModel):
    class Scope(models.TextChoices):
        PLANT = "PLANT", "Planta"
        CUSTOMER = "CUSTOMER", "Cliente"
        FAMILY = "FAMILY", "Família"
        ITEM = "ITEM", "Item"

    plant = models.ForeignKey(Plant, on_delete=models.CASCADE, related_name="service_level_targets")
    scope = models.CharField(max_length=16, choices=Scope.choices, default=Scope.PLANT)
    scope_key = models.CharField(max_length=80, blank=True)
    scope_label = models.CharField(max_length=180, blank=True)
    effective_from = models.DateField()
    effective_to = models.DateField(null=True, blank=True)
    otif_target_pct = models.DecimalField(max_digits=6, decimal_places=2, default=95)
    on_time_target_pct = models.DecimalField(max_digits=6, decimal_places=2, default=97)
    in_full_target_pct = models.DecimalField(max_digits=6, decimal_places=2, default=98)
    fill_rate_target_pct = models.DecimalField(max_digits=6, decimal_places=2, default=98)
    perfect_order_target_pct = models.DecimalField(max_digits=6, decimal_places=2, default=95)
    late_day_cost = models.DecimalField(max_digits=18, decimal_places=2, default=0)
    incomplete_unit_cost = models.DecimalField(max_digits=18, decimal_places=4, default=0)
    is_active = models.BooleanField(default=True)

    class Meta:
        ordering = ["plant__code", "scope", "scope_key", "-effective_from"]
        constraints = [
            models.UniqueConstraint(fields=["plant", "scope", "scope_key", "effective_from"], name="uq_sl_target_scope_date"),
            models.CheckConstraint(condition=models.Q(effective_to__isnull=True) | models.Q(effective_to__gte=models.F("effective_from")), name="ck_sl_target_dates"),
        ]
        indexes = [models.Index(fields=["plant", "scope", "scope_key", "is_active"], name="ix_sl_target_scope")]


class ServiceLevelPeriodSnapshot(TimeStampedModel):
    class Scope(models.TextChoices):
        PLANT = "PLANT", "Planta"
        CUSTOMER = "CUSTOMER", "Cliente"
        FAMILY = "FAMILY", "Família"
        ITEM = "ITEM", "Item"

    plant = models.ForeignKey(Plant, on_delete=models.CASCADE, related_name="service_level_snapshots")
    reference = models.CharField(max_length=24, choices=OTIFLineResult.Reference.choices, default=OTIFLineResult.Reference.CUSTOMER_ACCEPTED)
    period_start = models.DateField()
    period_end = models.DateField()
    scope = models.CharField(max_length=16, choices=Scope.choices, default=Scope.PLANT)
    scope_key = models.CharField(max_length=80, blank=True)
    scope_label = models.CharField(max_length=180, blank=True)
    lines = models.PositiveIntegerField(default=0)
    orders = models.PositiveIntegerField(default=0)
    ordered_quantity = models.DecimalField(max_digits=22, decimal_places=4, default=0)
    delivered_quantity = models.DecimalField(max_digits=22, decimal_places=4, default=0)
    overdue_backlog_quantity = models.DecimalField(max_digits=22, decimal_places=4, default=0)
    on_time_pct = models.DecimalField(max_digits=7, decimal_places=2, default=0)
    in_full_pct = models.DecimalField(max_digits=7, decimal_places=2, default=0)
    otif_pct = models.DecimalField(max_digits=7, decimal_places=2, default=0)
    fill_rate_pct = models.DecimalField(max_digits=7, decimal_places=2, default=0)
    perfect_order_proxy_pct = models.DecimalField(max_digits=7, decimal_places=2, default=0)
    estimated_service_failure_cost = models.DecimalField(max_digits=22, decimal_places=2, default=0)
    target_otif_pct = models.DecimalField(max_digits=7, decimal_places=2, null=True, blank=True)
    target_met = models.BooleanField(default=False)
    cause_summary = models.JSONField(default=list, blank=True)
    details = models.JSONField(default=dict, blank=True)
    calculated_at = models.DateTimeField(default=timezone.now)

    class Meta:
        ordering = ["-period_start", "scope", "scope_key"]
        constraints = [
            models.UniqueConstraint(fields=["plant", "reference", "period_start", "period_end", "scope", "scope_key"], name="uq_sl_snapshot_period_scope"),
            models.CheckConstraint(condition=models.Q(period_end__gte=models.F("period_start")), name="ck_sl_snapshot_dates"),
        ]
        indexes = [models.Index(fields=["plant", "reference", "period_start", "scope"], name="ix_sl_snapshot_period")]


# 0.7.8 — S&OP / Executive Service Dashboard
class ForecastAccuracySnapshot(TimeStampedModel):
    plant = models.ForeignKey(Plant, on_delete=models.CASCADE, related_name="forecast_accuracy_snapshots")
    period_start = models.DateField()
    period_end = models.DateField()
    forecast_quantity = models.DecimalField(max_digits=22, decimal_places=4, default=0)
    actual_quantity = models.DecimalField(max_digits=22, decimal_places=4, default=0)
    absolute_error_quantity = models.DecimalField(max_digits=22, decimal_places=4, default=0)
    wape_pct = models.DecimalField(max_digits=8, decimal_places=2, default=0)
    forecast_accuracy_pct = models.DecimalField(max_digits=8, decimal_places=2, default=0)
    bias_pct = models.DecimalField(max_digits=8, decimal_places=2, default=0)
    item_count = models.PositiveIntegerField(default=0)
    details = models.JSONField(default=dict, blank=True)
    calculated_at = models.DateTimeField(default=timezone.now)

    class Meta:
        ordering = ["-period_start", "plant__code"]
        constraints = [models.UniqueConstraint(fields=["plant", "period_start", "period_end"], name="uq_fcacc_plant_period")]
        indexes = [models.Index(fields=["plant", "period_start"], name="ix_fcacc_plant_period")]


class ExecutiveSAndOPSnapshot(TimeStampedModel):
    plant = models.ForeignKey(Plant, on_delete=models.CASCADE, related_name="executive_sop_snapshots")
    period_start = models.DateField()
    period_end = models.DateField()
    otif_pct = models.DecimalField(max_digits=8, decimal_places=2, default=0)
    fill_rate_pct = models.DecimalField(max_digits=8, decimal_places=2, default=0)
    forecast_accuracy_pct = models.DecimalField(max_digits=8, decimal_places=2, default=0)
    forecast_bias_pct = models.DecimalField(max_digits=8, decimal_places=2, default=0)
    overdue_backlog_quantity = models.DecimalField(max_digits=22, decimal_places=4, default=0)
    backlog_value = models.DecimalField(max_digits=22, decimal_places=2, default=0)
    revenue_at_risk = models.DecimalField(max_digits=22, decimal_places=2, default=0)
    revenue_coverage_pct = models.DecimalField(max_digits=8, decimal_places=2, default=0)
    inventory_quantity = models.DecimalField(max_digits=22, decimal_places=4, default=0)
    inventory_value = models.DecimalField(max_digits=22, decimal_places=2, default=0)
    oee_pct = models.DecimalField(max_digits=8, decimal_places=2, default=0)
    capacity_utilization_pct = models.DecimalField(max_digits=8, decimal_places=2, default=0)
    open_demand_quantity = models.DecimalField(max_digits=22, decimal_places=4, default=0)
    approved_forecast_quantity = models.DecimalField(max_digits=22, decimal_places=4, default=0)
    planned_supply_quantity = models.DecimalField(max_digits=22, decimal_places=4, default=0)
    details = models.JSONField(default=dict, blank=True)
    calculated_at = models.DateTimeField(default=timezone.now)

    class Meta:
        ordering = ["-period_start", "plant__code"]
        constraints = [models.UniqueConstraint(fields=["plant", "period_start", "period_end"], name="uq_execsop_plant_period")]
        indexes = [models.Index(fields=["plant", "period_start"], name="ix_execsop_plant_period")]


class SAndOPScenario(TimeStampedModel):
    class Status(models.TextChoices):
        DRAFT = "DRAFT", "Rascunho"
        SIMULATED = "SIMULATED", "Simulado"
        APPROVED = "APPROVED", "Aprovado"
        ARCHIVED = "ARCHIVED", "Arquivado"

    plant = models.ForeignKey(Plant, on_delete=models.CASCADE, related_name="sop_scenarios")
    name = models.CharField(max_length=160)
    horizon_start = models.DateField()
    horizon_end = models.DateField()
    status = models.CharField(max_length=16, choices=Status.choices, default=Status.DRAFT)
    demand_change_pct = models.DecimalField(max_digits=8, decimal_places=2, default=0)
    capacity_change_pct = models.DecimalField(max_digits=8, decimal_places=2, default=0)
    inventory_change_pct = models.DecimalField(max_digits=8, decimal_places=2, default=0)
    baseline = models.JSONField(default=dict, blank=True)
    simulated = models.JSONField(default=dict, blank=True)
    assumptions = models.JSONField(default=dict, blank=True)
    created_by = models.ForeignKey('auth.User', null=True, blank=True, on_delete=models.SET_NULL, related_name='created_sop_scenarios')
    approved_by = models.ForeignKey('auth.User', null=True, blank=True, on_delete=models.SET_NULL, related_name='approved_sop_scenarios')
    approved_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ["-created_at"]
        constraints = [models.CheckConstraint(condition=models.Q(horizon_end__gte=models.F("horizon_start")), name="ck_sop_scenario_dates")]
        indexes = [models.Index(fields=["plant", "status", "horizon_start"], name="ix_sop_plant_status")]


# 0.7.9 — ciclo S&OP mensal formal e versionado
class SAndOPCycle(TimeStampedModel):
    class Status(models.TextChoices):
        DRAFT = "DRAFT", "Rascunho"
        DEMAND_REVIEW = "DEMAND_REVIEW", "Demand Review"
        SUPPLY_REVIEW = "SUPPLY_REVIEW", "Supply Review"
        PRE_SOP = "PRE_SOP", "Pre-S&OP"
        EXECUTIVE_REVIEW = "EXECUTIVE_REVIEW", "Executive S&OP"
        APPROVED = "APPROVED", "Aprovado"
        PUBLISHED = "PUBLISHED", "Publicado"
        ARCHIVED = "ARCHIVED", "Arquivado"

    plant = models.ForeignKey(Plant, on_delete=models.PROTECT, related_name="sop_cycles")
    code = models.CharField(max_length=40)
    version = models.PositiveIntegerField(default=1)
    cycle_month = models.DateField(help_text="Primeiro dia do mês do ciclo S&OP.")
    horizon_start = models.DateField()
    horizon_end = models.DateField()
    meeting_date = models.DateField(null=True, blank=True)
    status = models.CharField(max_length=24, choices=Status.choices, default=Status.DRAFT)
    source_snapshot = models.ForeignKey(ExecutiveSAndOPSnapshot, null=True, blank=True, on_delete=models.SET_NULL, related_name="sop_cycles")
    demand_baseline = models.JSONField(default=dict, blank=True)
    demand_consensus_summary = models.JSONField(default=dict, blank=True)
    supply_summary = models.JSONField(default=dict, blank=True)
    constraints_summary = models.JSONField(default=dict, blank=True)
    executive_summary = models.JSONField(default=dict, blank=True)
    notes = models.TextField(blank=True)
    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL, related_name="sop_cycles_created")
    approved_by = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL, related_name="sop_cycles_approved")
    approved_at = models.DateTimeField(null=True, blank=True)
    published_by = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL, related_name="sop_cycles_published")
    published_at = models.DateTimeField(null=True, blank=True)
    published_planning_run = models.ForeignKey("planning.PlanningRun", null=True, blank=True, on_delete=models.SET_NULL, related_name="source_sop_cycles")

    class Meta:
        ordering = ["-cycle_month", "-version"]
        constraints = [
            models.UniqueConstraint(fields=["plant", "code", "version"], name="uq_sop_cycle_version"),
            models.CheckConstraint(condition=models.Q(horizon_end__gte=models.F("horizon_start")), name="ck_sop_cycle_horizon"),
        ]
        indexes = [models.Index(fields=["plant", "cycle_month", "status"], name="ix_sop_cycle_month_status")]

    def __str__(self):
        return f"{self.code} v{self.version}"


class SAndOPDemandConsensusLine(TimeStampedModel):
    cycle = models.ForeignKey(SAndOPCycle, on_delete=models.CASCADE, related_name="demand_lines")
    item = models.ForeignKey("masterdata.Item", on_delete=models.PROTECT, related_name="sop_demand_lines")
    bucket_date = models.DateField()
    baseline_forecast_quantity = models.DecimalField(max_digits=22, decimal_places=4, default=0)
    open_order_quantity = models.DecimalField(max_digits=22, decimal_places=4, default=0)
    commercial_adjustment_quantity = models.DecimalField(max_digits=22, decimal_places=4, default=0)
    consensus_quantity = models.DecimalField(max_digits=22, decimal_places=4, default=0)
    rationale = models.TextField(blank=True)

    class Meta:
        ordering = ["bucket_date", "item__code"]
        constraints = [models.UniqueConstraint(fields=["cycle", "item", "bucket_date"], name="uq_sop_demand_bucket")]
        indexes = [models.Index(fields=["cycle", "bucket_date"], name="ix_sop_demand_cycle_bucket")]


class SAndOPSupplyPlanLine(TimeStampedModel):
    cycle = models.ForeignKey(SAndOPCycle, on_delete=models.CASCADE, related_name="supply_lines")
    item = models.ForeignKey("masterdata.Item", on_delete=models.PROTECT, related_name="sop_supply_lines")
    bucket_date = models.DateField()
    demand_quantity = models.DecimalField(max_digits=22, decimal_places=4, default=0)
    opening_inventory_quantity = models.DecimalField(max_digits=22, decimal_places=4, default=0)
    planned_supply_quantity = models.DecimalField(max_digits=22, decimal_places=4, default=0)
    capacity_constrained_quantity = models.DecimalField(max_digits=22, decimal_places=4, default=0)
    projected_ending_inventory_quantity = models.DecimalField(max_digits=22, decimal_places=4, default=0)
    gap_quantity = models.DecimalField(max_digits=22, decimal_places=4, default=0)
    notes = models.TextField(blank=True)

    class Meta:
        ordering = ["bucket_date", "item__code"]
        constraints = [models.UniqueConstraint(fields=["cycle", "item", "bucket_date"], name="uq_sop_supply_bucket")]
        indexes = [models.Index(fields=["cycle", "bucket_date"], name="ix_sop_supply_cycle_bucket")]


class SAndOPConstraint(TimeStampedModel):
    class Category(models.TextChoices):
        MATERIAL = "MATERIAL", "Material"
        CAPACITY = "CAPACITY", "Capacidade"
        LABOR = "LABOR", "Mão de obra"
        MAINTENANCE = "MAINTENANCE", "Manutenção"
        SUPPLIER = "SUPPLIER", "Fornecedor"
        SERVICE = "SERVICE", "Serviço"
        FINANCIAL = "FINANCIAL", "Financeiro"
        OTHER = "OTHER", "Outro"
    class Severity(models.TextChoices):
        LOW = "LOW", "Baixa"
        MEDIUM = "MEDIUM", "Média"
        HIGH = "HIGH", "Alta"
        CRITICAL = "CRITICAL", "Crítica"
    class Status(models.TextChoices):
        OPEN = "OPEN", "Aberta"
        MITIGATED = "MITIGATED", "Mitigada"
        ACCEPTED = "ACCEPTED", "Aceita"
        CLOSED = "CLOSED", "Encerrada"

    cycle = models.ForeignKey(SAndOPCycle, on_delete=models.CASCADE, related_name="constraints_register")
    category = models.CharField(max_length=20, choices=Category.choices)
    severity = models.CharField(max_length=12, choices=Severity.choices, default=Severity.MEDIUM)
    title = models.CharField(max_length=180)
    description = models.TextField(blank=True)
    impact = models.JSONField(default=dict, blank=True)
    mitigation = models.TextField(blank=True)
    owner = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL, related_name="sop_constraints_owned")
    status = models.CharField(max_length=12, choices=Status.choices, default=Status.OPEN)

    class Meta:
        ordering = ["-severity", "category", "title"]
        indexes = [models.Index(fields=["cycle", "status", "severity"], name="ix_sop_constraint_status")]


class SAndOPDecision(TimeStampedModel):
    class Category(models.TextChoices):
        DEMAND = "DEMAND", "Demanda"
        SUPPLY = "SUPPLY", "Suprimento"
        CAPACITY = "CAPACITY", "Capacidade"
        INVENTORY = "INVENTORY", "Estoque"
        SERVICE = "SERVICE", "Nível de serviço"
        COMMERCIAL = "COMMERCIAL", "Comercial"
        FINANCIAL = "FINANCIAL", "Financeiro"
        OTHER = "OTHER", "Outro"
    class Status(models.TextChoices):
        OPEN = "OPEN", "Aberta"
        DONE = "DONE", "Concluída"
        CANCELLED = "CANCELLED", "Cancelada"

    cycle = models.ForeignKey(SAndOPCycle, on_delete=models.CASCADE, related_name="decisions")
    category = models.CharField(max_length=20, choices=Category.choices)
    title = models.CharField(max_length=180)
    decision = models.TextField()
    owner = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL, related_name="sop_decisions_owned")
    due_date = models.DateField(null=True, blank=True)
    status = models.CharField(max_length=12, choices=Status.choices, default=Status.OPEN)

    class Meta:
        ordering = ["status", "due_date", "title"]
        indexes = [models.Index(fields=["cycle", "status", "due_date"], name="ix_sop_decision_status")]


class SAndOPPublication(TimeStampedModel):
    cycle = models.OneToOneField(SAndOPCycle, on_delete=models.CASCADE, related_name="publication")
    mps_source = models.CharField(max_length=60)
    mps_lines = models.PositiveIntegerField(default=0)
    planning_run = models.ForeignKey("planning.PlanningRun", null=True, blank=True, on_delete=models.SET_NULL, related_name="sop_publications")
    published_by = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL, related_name="sop_publications_created")
    published_at = models.DateTimeField(default=timezone.now)
    details = models.JSONField(default=dict, blank=True)

    class Meta:
        ordering = ["-published_at"]


# 0.8.0 — publicação operacional S&OP → MPS semanal + RCCP/time fences
class MPSOperationalPolicy(TimeStampedModel):
    plant = models.OneToOneField(Plant, on_delete=models.CASCADE, related_name="mps_operational_policy")
    bucket_days = models.PositiveSmallIntegerField(default=7)
    demand_time_fence_days = models.PositiveIntegerField(default=14)
    planning_time_fence_days = models.PositiveIntegerField(default=42)
    require_rccp_clear = models.BooleanField(default=True)
    overload_tolerance_percent = models.DecimalField(max_digits=7, decimal_places=3, default=0)
    auto_create_planning_run = models.BooleanField(default=True)
    require_mrp_whatif_before_approval = models.BooleanField(default=True)

    class Meta:
        constraints = [
            models.CheckConstraint(condition=models.Q(bucket_days__gt=0), name="ck_mpsop_bucket_pos"),
            models.CheckConstraint(condition=models.Q(planning_time_fence_days__gte=models.F("demand_time_fence_days")), name="ck_mpsop_fences_order"),
            models.CheckConstraint(condition=models.Q(overload_tolerance_percent__gte=0), name="ck_mpsop_tol_nonneg"),
        ]

    def __str__(self):
        return f"{self.plant.code} MPS policy"


class OperationalMPSPublication(TimeStampedModel):
    class Status(models.TextChoices):
        DRAFT = "DRAFT", "Rascunho"
        VALIDATED = "VALIDATED", "Validado"
        BLOCKED = "BLOCKED", "Bloqueado"
        PUBLISHED = "PUBLISHED", "Publicado"
        MRP_RUNNING = "MRP_RUNNING", "MRP executando"
        MRP_COMPLETED = "MRP_COMPLETED", "MRP concluído"
        FAILED = "FAILED", "Falhou"

    cycle = models.ForeignKey(SAndOPCycle, on_delete=models.PROTECT, related_name="operational_mps_publications")
    policy = models.ForeignKey(MPSOperationalPolicy, on_delete=models.PROTECT, related_name="publications")
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.DRAFT)
    as_of_date = models.DateField(default=timezone.localdate)
    horizon_start = models.DateField()
    horizon_end = models.DateField()
    source = models.CharField(max_length=80, unique=True)
    summary = models.JSONField(default=dict, blank=True)
    validation_summary = models.JSONField(default=dict, blank=True)
    planning_run = models.ForeignKey("planning.PlanningRun", null=True, blank=True, on_delete=models.SET_NULL, related_name="operational_mps_publications")
    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL, related_name="operational_mps_publications_created")
    published_by = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL, related_name="operational_mps_publications_published")
    published_at = models.DateTimeField(null=True, blank=True)
    mrp_started_at = models.DateTimeField(null=True, blank=True)
    mrp_completed_at = models.DateTimeField(null=True, blank=True)
    error_message = models.TextField(blank=True)

    class Meta:
        ordering = ["-created_at"]
        constraints = [models.CheckConstraint(condition=models.Q(horizon_end__gte=models.F("horizon_start")), name="ck_opmps_horizon")]
        indexes = [models.Index(fields=["cycle", "status"], name="ix_opmps_cycle_status")]

    def __str__(self):
        return self.source


class MPSWeeklyBucket(TimeStampedModel):
    publication = models.ForeignKey(OperationalMPSPublication, on_delete=models.CASCADE, related_name="weekly_buckets")
    item = models.ForeignKey("masterdata.Item", on_delete=models.PROTECT, related_name="operational_mps_buckets")
    bucket_start = models.DateField()
    bucket_end = models.DateField()
    quantity = models.DecimalField(max_digits=22, decimal_places=4)
    baseline_quantity = models.DecimalField(max_digits=22, decimal_places=4, default=0)
    source_demand_quantity = models.DecimalField(max_digits=22, decimal_places=4, default=0)
    source_supply_quantity = models.DecimalField(max_digits=22, decimal_places=4, default=0)
    mps_status = models.CharField(max_length=15, choices=[("PLANNED","Planejado"),("FIRM","Firme"),("FROZEN","Congelado")], default="PLANNED")
    frozen_reason = models.CharField(max_length=160, blank=True)
    published_mps = models.ForeignKey("demand.MasterProductionSchedule", null=True, blank=True, on_delete=models.SET_NULL, related_name="operational_weekly_buckets")

    class Meta:
        ordering = ["bucket_start", "item__code"]
        constraints = [
            models.UniqueConstraint(fields=["publication","item","bucket_start"], name="uq_opmps_week_item"),
            models.CheckConstraint(condition=models.Q(quantity__gte=0), name="ck_opmps_week_qty_nonneg"),
            models.CheckConstraint(condition=models.Q(bucket_end__gte=models.F("bucket_start")), name="ck_opmps_week_dates"),
        ]
        indexes = [models.Index(fields=["publication","bucket_start","mps_status"], name="ix_opmps_week_status")]


class MPSBucketChangeRequest(TimeStampedModel):
    class Status(models.TextChoices):
        PENDING = "PENDING", "Pendente"
        APPROVED = "APPROVED", "Aprovada"
        REJECTED = "REJECTED", "Rejeitada"
    class Violation(models.TextChoices):
        NONE = "NONE", "Sem violação"
        DEMAND_TIME_FENCE = "DEMAND_TIME_FENCE", "Demand time fence"
        FROZEN_BUCKET = "FROZEN_BUCKET", "Bucket congelado"

    publication = models.ForeignKey(OperationalMPSPublication, on_delete=models.CASCADE, related_name="bucket_change_requests")
    source_bucket = models.ForeignKey(MPSWeeklyBucket, on_delete=models.CASCADE, related_name="change_requests_as_source")
    target_bucket = models.ForeignKey(MPSWeeklyBucket, null=True, blank=True, on_delete=models.CASCADE, related_name="change_requests_as_target")
    source_quantity_before = models.DecimalField(max_digits=22, decimal_places=4)
    source_quantity_after = models.DecimalField(max_digits=22, decimal_places=4)
    target_quantity_before = models.DecimalField(max_digits=22, decimal_places=4, null=True, blank=True)
    target_quantity_after = models.DecimalField(max_digits=22, decimal_places=4, null=True, blank=True)
    violation = models.CharField(max_length=24, choices=Violation.choices, default=Violation.NONE)
    status = models.CharField(max_length=12, choices=Status.choices, default=Status.PENDING)
    reason = models.TextField(blank=True)
    requested_by = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL, related_name="mps_bucket_changes_requested")
    requested_at = models.DateTimeField(default=timezone.now)
    decided_by = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL, related_name="mps_bucket_changes_decided")
    decided_at = models.DateTimeField(null=True, blank=True)
    decision_notes = models.TextField(blank=True)

    class Meta:
        ordering = ["-requested_at"]
        indexes = [models.Index(fields=["publication","status"], name="ix_mpschg_pub_status")]

    def __str__(self):
        return f"MPS change #{self.pk} {self.status}"


class MPSRCCPException(TimeStampedModel):
    class Severity(models.TextChoices):
        INFO = "INFO", "Informação"
        WARNING = "WARNING", "Atenção"
        CRITICAL = "CRITICAL", "Crítica"
    class Status(models.TextChoices):
        OPEN = "OPEN", "Aberta"
        ACCEPTED = "ACCEPTED", "Aceita"
        RESOLVED = "RESOLVED", "Resolvida"

    publication = models.ForeignKey(OperationalMPSPublication, on_delete=models.CASCADE, related_name="rccp_exceptions")
    work_center = models.ForeignKey(WorkCenter, on_delete=models.PROTECT, related_name="mps_rccp_exceptions")
    bucket_start = models.DateField()
    required_hours = models.DecimalField(max_digits=18, decimal_places=4, default=0)
    available_hours = models.DecimalField(max_digits=18, decimal_places=4, default=0)
    overload_hours = models.DecimalField(max_digits=18, decimal_places=4, default=0)
    overload_percent = models.DecimalField(max_digits=10, decimal_places=3, default=0)
    severity = models.CharField(max_length=10, choices=Severity.choices, default=Severity.WARNING)
    status = models.CharField(max_length=12, choices=Status.choices, default=Status.OPEN)
    message = models.TextField(blank=True)
    details = models.JSONField(default=dict, blank=True)

    class Meta:
        ordering = ["-severity", "bucket_start", "work_center__code"]
        constraints = [models.UniqueConstraint(fields=["publication","work_center","bucket_start"], name="uq_mpsrccp_center_week")]
        indexes = [models.Index(fields=["publication","status","severity"], name="ix_mpsrccp_status")]


# 0.8.2 — versionamento, comparação e rollback do MPS operacional
class MPSRevision(TimeStampedModel):
    class Status(models.TextChoices):
        DRAFT = "DRAFT", "Rascunho"
        PENDING_APPROVAL = "PENDING_APPROVAL", "Aguardando aprovação"
        APPROVED = "APPROVED", "Aprovada"
        REJECTED = "REJECTED", "Rejeitada"
        SUPERSEDED = "SUPERSEDED", "Substituída"
    class Kind(models.TextChoices):
        BASELINE = "BASELINE", "Baseline"
        WORKING = "WORKING", "Revisão"
        ROLLBACK = "ROLLBACK", "Rollback"

    publication = models.ForeignKey(OperationalMPSPublication, on_delete=models.CASCADE, related_name="revisions")
    number = models.PositiveIntegerField()
    parent = models.ForeignKey("self", null=True, blank=True, on_delete=models.SET_NULL, related_name="children")
    kind = models.CharField(max_length=12, choices=Kind.choices, default=Kind.WORKING)
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.DRAFT)
    label = models.CharField(max_length=160, blank=True)
    notes = models.TextField(blank=True)
    summary = models.JSONField(default=dict, blank=True)
    rccp_summary = models.JSONField(default=dict, blank=True)
    mrp_impact_summary = models.JSONField(default=dict, blank=True)
    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL, related_name="mps_revisions_created")
    submitted_by = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL, related_name="mps_revisions_submitted")
    submitted_at = models.DateTimeField(null=True, blank=True)
    approved_by = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL, related_name="mps_revisions_approved")
    approved_at = models.DateTimeField(null=True, blank=True)
    decision_notes = models.TextField(blank=True)

    class Meta:
        ordering = ["publication", "-number"]
        constraints = [models.UniqueConstraint(fields=["publication", "number"], name="uq_mpsrev_pub_number")]
        indexes = [models.Index(fields=["publication", "status"], name="ix_mpsrev_pub_status")]

    def __str__(self):
        return f"{self.publication.source} r{self.number}"


class MPSRevisionLine(TimeStampedModel):
    revision = models.ForeignKey(MPSRevision, on_delete=models.CASCADE, related_name="lines")
    item = models.ForeignKey("masterdata.Item", on_delete=models.PROTECT, related_name="mps_revision_lines")
    bucket_start = models.DateField()
    bucket_end = models.DateField()
    quantity = models.DecimalField(max_digits=22, decimal_places=4)
    baseline_quantity = models.DecimalField(max_digits=22, decimal_places=4, default=0)
    mps_status = models.CharField(max_length=15, choices=[("PLANNED","Planejado"),("FIRM","Firme"),("FROZEN","Congelado")], default="PLANNED")
    frozen_reason = models.CharField(max_length=160, blank=True)

    class Meta:
        ordering = ["bucket_start", "item__code"]
        constraints = [models.UniqueConstraint(fields=["revision", "item", "bucket_start"], name="uq_mpsrevline_item_week")]
        indexes = [models.Index(fields=["revision", "bucket_start"], name="ix_mpsrevline_week")]


class MPSRevisionRCCPLine(TimeStampedModel):
    revision = models.ForeignKey(MPSRevision, on_delete=models.CASCADE, related_name="rccp_lines")
    work_center = models.ForeignKey(WorkCenter, on_delete=models.PROTECT, related_name="mps_revision_rccp_lines")
    bucket_start = models.DateField()
    required_hours = models.DecimalField(max_digits=18, decimal_places=4, default=0)
    available_hours = models.DecimalField(max_digits=18, decimal_places=4, default=0)
    overload_hours = models.DecimalField(max_digits=18, decimal_places=4, default=0)
    overload_percent = models.DecimalField(max_digits=10, decimal_places=3, default=0)
    severity = models.CharField(max_length=10, choices=MPSRCCPException.Severity.choices, default=MPSRCCPException.Severity.WARNING)

    class Meta:
        ordering = ["bucket_start", "work_center__code"]
        constraints = [models.UniqueConstraint(fields=["revision", "work_center", "bucket_start"], name="uq_mpsrevrccp_center_week")]

# 0.8.3 — MRP what-if por revisão do MPS
class MPSRevisionSimulation(TimeStampedModel):
    class Status(models.TextChoices):
        DRAFT = "DRAFT", "Rascunho"
        RUNNING = "RUNNING", "Executando"
        COMPLETED = "COMPLETED", "Concluída"
        FAILED = "FAILED", "Falhou"

    revision = models.ForeignKey(MPSRevision, on_delete=models.CASCADE, related_name="mrp_simulations")
    compare_revision = models.ForeignKey(MPSRevision, on_delete=models.PROTECT, related_name="mrp_comparisons_as_baseline")
    status = models.CharField(max_length=12, choices=Status.choices, default=Status.DRAFT)
    target_planning_run = models.ForeignKey("planning.PlanningRun", null=True, blank=True, on_delete=models.SET_NULL, related_name="mps_revision_target_simulations")
    compare_planning_run = models.ForeignKey("planning.PlanningRun", null=True, blank=True, on_delete=models.SET_NULL, related_name="mps_revision_compare_simulations")
    summary = models.JSONField(default=dict, blank=True)
    diff_summary = models.JSONField(default=dict, blank=True)
    cost_version = models.ForeignKey("costing.CostVersion", null=True, blank=True, on_delete=models.SET_NULL, related_name="mps_revision_simulations")
    financial_summary = models.JSONField(default=dict, blank=True)
    planning_overrides = models.JSONField(default=dict, blank=True)
    started_at = models.DateTimeField(null=True, blank=True)
    completed_at = models.DateTimeField(null=True, blank=True)
    error_message = models.TextField(blank=True)
    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL, related_name="mps_revision_simulations_created")

    class Meta:
        ordering = ["-created_at"]
        indexes = [models.Index(fields=["revision", "status"], name="ix_mpssim_rev_status")]

    def __str__(self):
        return f"MRP what-if r{self.revision.number} vs r{self.compare_revision.number}"


class MPSRevisionSimulationDiffLine(TimeStampedModel):
    class DiffType(models.TextChoices):
        MAKE = "MAKE", "OP planejada"
        PURCHASE = "PURCHASE", "Compra planejada"
        SHORTAGE = "SHORTAGE", "Falta / exceção"
        PEGGING = "PEGGING", "Pegging"

    simulation = models.ForeignKey(MPSRevisionSimulation, on_delete=models.CASCADE, related_name="diff_lines")
    diff_type = models.CharField(max_length=12, choices=DiffType.choices)
    item = models.ForeignKey("masterdata.Item", null=True, blank=True, on_delete=models.PROTECT, related_name="mps_simulation_diffs")
    event_date = models.DateField(null=True, blank=True)
    reference_key = models.CharField(max_length=180)
    left_quantity = models.DecimalField(max_digits=22, decimal_places=4, default=0)
    right_quantity = models.DecimalField(max_digits=22, decimal_places=4, default=0)
    delta_quantity = models.DecimalField(max_digits=22, decimal_places=4, default=0)
    details = models.JSONField(default=dict, blank=True)

    class Meta:
        ordering = ["diff_type", "event_date", "reference_key"]
        indexes = [models.Index(fields=["simulation", "diff_type"], name="ix_mpssimdiff_type")]
        constraints = [models.UniqueConstraint(fields=["simulation", "diff_type", "reference_key"], name="uq_mpssimdiff_key")]


# 0.8.4 — impacto financeiro do MRP what-if
class MPSRevisionSimulationFinancialLine(TimeStampedModel):
    class Category(models.TextChoices):
        PURCHASE_SPEND = "PURCHASE_SPEND", "Compras planejadas"
        MATERIAL_COST = "MATERIAL_COST", "Material MAKE"
        LABOR_COST = "LABOR_COST", "Mão de obra MAKE"
        MACHINE_COST = "MACHINE_COST", "Máquina MAKE"
        OVERHEAD_COST = "OVERHEAD_COST", "Overhead/setup MAKE"
        INVENTORY_EXPOSURE = "INVENTORY_EXPOSURE", "Estoque projetado"
        WIP_PROXY = "WIP_PROXY", "WIP planejado (proxy)"
        CASH_OUTFLOW_PROXY = "CASH_OUTFLOW_PROXY", "Saída de caixa (proxy)"

    simulation = models.ForeignKey(MPSRevisionSimulation, on_delete=models.CASCADE, related_name="financial_lines")
    category = models.CharField(max_length=32, choices=Category.choices)
    item = models.ForeignKey("masterdata.Item", null=True, blank=True, on_delete=models.PROTECT, related_name="mps_financial_whatif_lines")
    left_value = models.DecimalField(max_digits=24, decimal_places=2, default=0)
    right_value = models.DecimalField(max_digits=24, decimal_places=2, default=0)
    delta_value = models.DecimalField(max_digits=24, decimal_places=2, default=0)
    details = models.JSONField(default=dict, blank=True)

    class Meta:
        ordering = ["category", "item__code"]
        constraints = [models.UniqueConstraint(fields=["simulation", "category", "item"], name="uq_mpssimfin_cat_item")]
        indexes = [models.Index(fields=["simulation", "category"], name="ix_mpssimfin_category")]


# 0.8.5 — orçamento e cash-flow temporal do MPS what-if
class MPSFinancialBudget(TimeStampedModel):
    class BucketType(models.TextChoices):
        WEEKLY = "WEEKLY", "Semanal"
        MONTHLY = "MONTHLY", "Mensal"
    class Status(models.TextChoices):
        DRAFT = "DRAFT", "Rascunho"
        APPROVED = "APPROVED", "Aprovado"
        ARCHIVED = "ARCHIVED", "Arquivado"
    plant = models.ForeignKey("common.Plant", on_delete=models.PROTECT, related_name="mps_financial_budgets")
    code = models.CharField(max_length=60)
    name = models.CharField(max_length=160)
    period_start = models.DateField()
    period_end = models.DateField()
    bucket_type = models.CharField(max_length=10, choices=BucketType.choices, default=BucketType.MONTHLY)
    status = models.CharField(max_length=12, choices=Status.choices, default=Status.DRAFT)
    notes = models.TextField(blank=True)
    approved_by = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL, related_name="mps_financial_budgets_approved")
    approved_at = models.DateTimeField(null=True, blank=True)
    class Meta:
        ordering = ["-period_start", "code"]
        constraints = [
            models.UniqueConstraint(fields=["plant","code"], name="uq_mpsfinbudget_plant_code"),
            models.CheckConstraint(condition=models.Q(period_end__gte=models.F("period_start")), name="ck_mpsfinbudget_period"),
        ]
    def __str__(self): return f"{self.plant.code} {self.code}"


class MPSFinancialBudgetLine(TimeStampedModel):
    class Category(models.TextChoices):
        PURCHASE_CASH = "PURCHASE_CASH", "Desembolso de compras"
        LABOR = "LABOR", "Mão de obra"
        MACHINE = "MACHINE", "Máquina"
        OVERHEAD = "OVERHEAD", "Overhead/setup"
        TOTAL_CASH = "TOTAL_CASH", "Caixa operacional total"
        INVENTORY_VALUE = "INVENTORY_VALUE", "Estoque em valor"
    budget = models.ForeignKey(MPSFinancialBudget, on_delete=models.CASCADE, related_name="lines")
    bucket_date = models.DateField()
    category = models.CharField(max_length=24, choices=Category.choices)
    amount = models.DecimalField(max_digits=24, decimal_places=2, default=0)
    notes = models.CharField(max_length=240, blank=True)
    class Meta:
        ordering = ["bucket_date", "category"]
        constraints = [models.UniqueConstraint(fields=["budget","bucket_date","category"], name="uq_mpsfinbudget_line")]
        indexes = [models.Index(fields=["budget","bucket_date"], name="ix_mpsfinbudget_bucket")]


class MPSRevisionSimulationCashFlowBucket(TimeStampedModel):
    class Category(models.TextChoices):
        PURCHASE_CASH = "PURCHASE_CASH", "Desembolso de compras"
        LABOR = "LABOR", "Mão de obra"
        MACHINE = "MACHINE", "Máquina"
        OVERHEAD = "OVERHEAD", "Overhead/setup"
        TOTAL_CASH = "TOTAL_CASH", "Caixa operacional total"
        INVENTORY_VALUE = "INVENTORY_VALUE", "Estoque em valor"
    simulation = models.ForeignKey(MPSRevisionSimulation, on_delete=models.CASCADE, related_name="cashflow_buckets")
    budget = models.ForeignKey(MPSFinancialBudget, null=True, blank=True, on_delete=models.SET_NULL, related_name="simulation_buckets")
    bucket_date = models.DateField()
    category = models.CharField(max_length=24, choices=Category.choices)
    left_value = models.DecimalField(max_digits=24, decimal_places=2, default=0)
    right_value = models.DecimalField(max_digits=24, decimal_places=2, default=0)
    delta_value = models.DecimalField(max_digits=24, decimal_places=2, default=0)
    budget_value = models.DecimalField(max_digits=24, decimal_places=2, null=True, blank=True)
    variance_to_budget = models.DecimalField(max_digits=24, decimal_places=2, null=True, blank=True)
    details = models.JSONField(default=dict, blank=True)
    class Meta:
        ordering = ["bucket_date", "category"]
        constraints = [models.UniqueConstraint(fields=["simulation","bucket_date","category"], name="uq_mpssimcash_bucket")]
        indexes = [models.Index(fields=["simulation","bucket_date"], name="ix_mpssimcash_bucket")]


# 0.8.6 — capital de giro / cash conversion planning
class WorkingCapitalPolicy(TimeStampedModel):
    plant = models.OneToOneField("common.Plant", on_delete=models.CASCADE, related_name="working_capital_policy")
    initial_cash_balance = models.DecimalField(max_digits=24, decimal_places=2, default=0)
    minimum_cash_buffer = models.DecimalField(max_digits=24, decimal_places=2, default=0)
    default_customer_terms_days = models.PositiveIntegerField(default=30)
    sales_tax_percent = models.DecimalField(max_digits=8, decimal_places=4, default=0)
    freight_percent = models.DecimalField(max_digits=8, decimal_places=4, default=0)
    include_tax_freight = models.BooleanField(default=True)
    notes = models.TextField(blank=True)
    class Meta:
        constraints = [
            models.CheckConstraint(condition=models.Q(initial_cash_balance__gte=0), name="ck_wcpol_initial_cash_nonneg"),
            models.CheckConstraint(condition=models.Q(minimum_cash_buffer__gte=0), name="ck_wcpol_buffer_nonneg"),
            models.CheckConstraint(condition=models.Q(sales_tax_percent__gte=0), name="ck_wcpol_tax_nonneg"),
            models.CheckConstraint(condition=models.Q(freight_percent__gte=0), name="ck_wcpol_freight_nonneg"),
        ]
    def __str__(self): return f"Working capital {self.plant.code}"


class MPSRevisionSimulationWorkingCapitalBucket(TimeStampedModel):
    simulation = models.ForeignKey(MPSRevisionSimulation, on_delete=models.CASCADE, related_name="working_capital_buckets")
    bucket_date = models.DateField()
    left_cash_inflow = models.DecimalField(max_digits=24, decimal_places=2, default=0)
    right_cash_inflow = models.DecimalField(max_digits=24, decimal_places=2, default=0)
    left_cash_outflow = models.DecimalField(max_digits=24, decimal_places=2, default=0)
    right_cash_outflow = models.DecimalField(max_digits=24, decimal_places=2, default=0)
    left_net_cash = models.DecimalField(max_digits=24, decimal_places=2, default=0)
    right_net_cash = models.DecimalField(max_digits=24, decimal_places=2, default=0)
    left_cumulative_cash = models.DecimalField(max_digits=24, decimal_places=2, default=0)
    right_cumulative_cash = models.DecimalField(max_digits=24, decimal_places=2, default=0)
    left_working_capital_need = models.DecimalField(max_digits=24, decimal_places=2, default=0)
    right_working_capital_need = models.DecimalField(max_digits=24, decimal_places=2, default=0)
    left_ar_outstanding = models.DecimalField(max_digits=24, decimal_places=2, default=0)
    right_ar_outstanding = models.DecimalField(max_digits=24, decimal_places=2, default=0)
    left_ap_outstanding = models.DecimalField(max_digits=24, decimal_places=2, default=0)
    right_ap_outstanding = models.DecimalField(max_digits=24, decimal_places=2, default=0)
    left_inventory_value = models.DecimalField(max_digits=24, decimal_places=2, default=0)
    right_inventory_value = models.DecimalField(max_digits=24, decimal_places=2, default=0)
    details = models.JSONField(default=dict, blank=True)
    class Meta:
        ordering = ["bucket_date"]
        constraints = [models.UniqueConstraint(fields=["simulation","bucket_date"], name="uq_mpssim_wc_bucket")]
        indexes = [models.Index(fields=["simulation","bucket_date"], name="ix_mpssim_wc_bucket")]


# 0.8.7 — financing capacity / credit limits for MPS what-if
class FinancingPolicy(TimeStampedModel):
    plant = models.OneToOneField("common.Plant", on_delete=models.CASCADE, related_name="financing_policy")
    block_revision_approval_when_exceeded = models.BooleanField(default=False)
    max_financing_utilization_percent = models.DecimalField(max_digits=8, decimal_places=4, default=100)
    notes = models.TextField(blank=True)
    class Meta:
        constraints = [
            models.CheckConstraint(condition=models.Q(max_financing_utilization_percent__gt=0), name="ck_finpol_util_gt0"),
            models.CheckConstraint(condition=models.Q(max_financing_utilization_percent__lte=100), name="ck_finpol_util_lte100"),
        ]
    def __str__(self): return f"Financing policy {self.plant.code}"


class FinancingFacility(TimeStampedModel):
    plant = models.ForeignKey("common.Plant", on_delete=models.CASCADE, related_name="financing_facilities")
    code = models.CharField(max_length=40)
    name = models.CharField(max_length=140)
    limit_amount = models.DecimalField(max_digits=24, decimal_places=2, default=0)
    annual_interest_rate_percent = models.DecimalField(max_digits=10, decimal_places=6, default=0)
    priority = models.PositiveIntegerField(default=100)
    effective_from = models.DateField(null=True, blank=True)
    effective_to = models.DateField(null=True, blank=True)
    is_active = models.BooleanField(default=True)
    notes = models.TextField(blank=True)
    class Meta:
        ordering = ["priority", "code"]
        constraints = [
            models.UniqueConstraint(fields=["plant","code"], name="uq_fin_facility_plant_code"),
            models.CheckConstraint(condition=models.Q(limit_amount__gte=0), name="ck_fin_facility_limit_nonneg"),
            models.CheckConstraint(condition=models.Q(annual_interest_rate_percent__gte=0), name="ck_fin_facility_rate_nonneg"),
        ]
        indexes = [models.Index(fields=["plant","is_active","priority"], name="ix_fin_facility_active")]
    def __str__(self): return f"{self.plant.code} {self.code}"

# 0.8.8 — otimização multicritério do MPS (MRP + RCCP + serviço + caixa)
class MPSOptimizationPolicy(TimeStampedModel):
    plant = models.OneToOneField(
        "common.Plant",
        on_delete=models.CASCADE,
        related_name="mps_optimization_policy",
    )
    max_candidates = models.PositiveIntegerField(default=5)
    move_fraction_percent = models.DecimalField(max_digits=7, decimal_places=3, default=20)
    max_week_shift = models.PositiveIntegerField(default=1)
    allow_supplier_switch = models.BooleanField(default=True)
    require_optimizer_before_approval = models.BooleanField(default=False)
    supplier_price_tolerance_percent = models.DecimalField(max_digits=7, decimal_places=3, default=10)

    weight_shortage = models.DecimalField(max_digits=10, decimal_places=4, default=100)
    weight_rccp_overload = models.DecimalField(max_digits=10, decimal_places=4, default=10)
    weight_uncovered_financing = models.DecimalField(max_digits=10, decimal_places=4, default=1)
    weight_interest = models.DecimalField(max_digits=10, decimal_places=4, default=1)
    weight_inventory = models.DecimalField(max_digits=10, decimal_places=4, default=0.10)
    weight_purchase_spend = models.DecimalField(max_digits=10, decimal_places=4, default=0.10)

    # 0.8.9 — CP-SAT Pareto frontier generation
    enable_cp_sat_pareto = models.BooleanField(default=True)
    pareto_candidate_limit = models.PositiveIntegerField(default=12)
    pareto_solver_time_limit_seconds = models.PositiveIntegerField(default=20)
    pareto_quantity_scale = models.PositiveIntegerField(default=100)
    pareto_max_change_percent = models.DecimalField(
        max_digits=7,
        decimal_places=3,
        default=30,
    )

    notes = models.TextField(blank=True)

    class Meta:
        constraints = [
            models.CheckConstraint(
                condition=models.Q(max_candidates__gt=0),
                name="ck_mpsopt_candidates_gt0",
            ),
            models.CheckConstraint(
                condition=models.Q(move_fraction_percent__gt=0),
                name="ck_mpsopt_move_gt0",
            ),
            models.CheckConstraint(
                condition=models.Q(move_fraction_percent__lte=100),
                name="ck_mpsopt_move_lte100",
            ),
            models.CheckConstraint(
                condition=models.Q(pareto_candidate_limit__gt=0),
                name="ck_mpsopt_pareto_limit_gt0",
            ),
            models.CheckConstraint(
                condition=(
                    models.Q(pareto_max_change_percent__gte=0)
                    & models.Q(pareto_max_change_percent__lte=100)
                ),
                name="ck_mpsopt_pareto_change_pct",
            ),
        ]

    def __str__(self):
        return f"MPS optimizer {self.plant.code}"


class MPSRevisionSimulationFinancingBucket(TimeStampedModel):
    simulation = models.ForeignKey(MPSRevisionSimulation, on_delete=models.CASCADE, related_name="financing_buckets")
    bucket_date = models.DateField()
    left_required_financing = models.DecimalField(max_digits=24, decimal_places=2, default=0)
    right_required_financing = models.DecimalField(max_digits=24, decimal_places=2, default=0)
    left_financing_outstanding = models.DecimalField(max_digits=24, decimal_places=2, default=0)
    right_financing_outstanding = models.DecimalField(max_digits=24, decimal_places=2, default=0)
    left_available_credit = models.DecimalField(max_digits=24, decimal_places=2, default=0)
    right_available_credit = models.DecimalField(max_digits=24, decimal_places=2, default=0)
    left_uncovered_need = models.DecimalField(max_digits=24, decimal_places=2, default=0)
    right_uncovered_need = models.DecimalField(max_digits=24, decimal_places=2, default=0)
    left_interest_expense = models.DecimalField(max_digits=24, decimal_places=2, default=0)
    right_interest_expense = models.DecimalField(max_digits=24, decimal_places=2, default=0)
    details = models.JSONField(default=dict, blank=True)
    class Meta:
        ordering = ["bucket_date"]
        constraints = [models.UniqueConstraint(fields=["simulation","bucket_date"], name="uq_mpssim_fin_bucket")]
        indexes = [models.Index(fields=["simulation","bucket_date"], name="ix_mpssim_fin_bucket")]


class MPSRevisionOptimizationRun(TimeStampedModel):
    class Status(models.TextChoices):
        DRAFT = "DRAFT", "Rascunho"
        RUNNING = "RUNNING", "Executando"
        COMPLETED = "COMPLETED", "Concluído"
        FAILED = "FAILED", "Falhou"

    revision = models.ForeignKey(MPSRevision, on_delete=models.CASCADE, related_name="optimization_runs")
    compare_revision = models.ForeignKey(MPSRevision, on_delete=models.PROTECT, related_name="optimization_baselines")
    status = models.CharField(max_length=12, choices=Status.choices, default=Status.DRAFT)
    summary = models.JSONField(default=dict, blank=True)
    optimizer_mode = models.CharField(max_length=20, default="HEURISTIC", choices=[("HEURISTIC","Heurístico"),("CP_SAT_PARETO","CP-SAT Pareto")])
    solver_status = models.CharField(max_length=30, blank=True)
    started_at = models.DateTimeField(null=True, blank=True)
    completed_at = models.DateTimeField(null=True, blank=True)
    error_message = models.TextField(blank=True)
    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL, related_name="mps_optimization_runs_created")

    class Meta:
        ordering = ["-created_at"]
        indexes = [models.Index(fields=["revision", "status"], name="ix_mpsopt_run_status")]


class MPSRevisionOptimizationCandidate(TimeStampedModel):
    class Strategy(models.TextChoices):
        BASELINE = "BASELINE", "Revisão atual"
        SHIFT_LATER = "SHIFT_LATER", "Postergar volume"
        SHIFT_EARLIER = "SHIFT_EARLIER", "Antecipar volume"
        LEVEL_LOAD = "LEVEL_LOAD", "Nivelar buckets"
        SUPPLIER_TERMS = "SUPPLIER_TERMS", "Fornecedor/prazo financeiro"
        CP_SAT_PARETO = "CP_SAT_PARETO", "CP-SAT / fronteira Pareto"

    optimization_run = models.ForeignKey(MPSRevisionOptimizationRun, on_delete=models.CASCADE, related_name="candidates")
    strategy = models.CharField(max_length=24, choices=Strategy.choices)
    name = models.CharField(max_length=160)
    generated_revision = models.ForeignKey(MPSRevision, null=True, blank=True, on_delete=models.SET_NULL, related_name="optimization_candidates")
    simulation = models.ForeignKey(MPSRevisionSimulation, null=True, blank=True, on_delete=models.SET_NULL, related_name="optimization_candidates")
    planning_overrides = models.JSONField(default=dict, blank=True)
    metrics = models.JSONField(default=dict, blank=True)
    score = models.DecimalField(max_digits=24, decimal_places=6, null=True, blank=True)
    rank = models.PositiveIntegerField(null=True, blank=True)
    is_recommended = models.BooleanField(default=False)
    notes = models.TextField(blank=True)
    # 0.8.9 — multiobjective decision support; score remains only a tie-breaker
    objective_vector = models.JSONField(default=dict, blank=True)
    pareto_rank = models.PositiveIntegerField(null=True, blank=True)
    is_pareto = models.BooleanField(default=False)
    dominated_by_count = models.PositiveIntegerField(default=0)

    class Meta:
        ordering = ["pareto_rank", "rank", "score", "id"]
        indexes = [models.Index(fields=["optimization_run", "rank"], name="ix_mpsopt_candidate_rank")]


class MPSRevisionOptimizationAction(TimeStampedModel):
    candidate = models.ForeignKey(MPSRevisionOptimizationCandidate, on_delete=models.CASCADE, related_name="actions")
    action_type = models.CharField(max_length=30)
    item = models.ForeignKey("masterdata.Item", null=True, blank=True, on_delete=models.PROTECT, related_name="mps_optimization_actions")
    source_date = models.DateField(null=True, blank=True)
    target_date = models.DateField(null=True, blank=True)
    quantity = models.DecimalField(max_digits=22, decimal_places=4, default=0)
    supplier_from = models.ForeignKey("masterdata.Supplier", null=True, blank=True, on_delete=models.PROTECT, related_name="optimization_actions_from")
    supplier_to = models.ForeignKey("masterdata.Supplier", null=True, blank=True, on_delete=models.PROTECT, related_name="optimization_actions_to")
    details = models.JSONField(default=dict, blank=True)

    class Meta:
        ordering = ["candidate", "id"]

# 0.9.0 — cockpit executivo de decisão MRP/MPS
class MPSDecisionCockpit(TimeStampedModel):
    class Status(models.TextChoices):
        OPEN = "OPEN", "Aberto"
        SELECTED = "SELECTED", "Cenário selecionado"
        PENDING_APPROVAL = "PENDING_APPROVAL", "Aguardando aprovação executiva"
        APPROVED = "APPROVED", "Aprovado"
        FROZEN = "FROZEN", "Congelado como plano oficial"
        REJECTED = "REJECTED", "Rejeitado"

    publication = models.ForeignKey(OperationalMPSPublication, on_delete=models.CASCADE, related_name="decision_cockpits")
    optimization_run = models.OneToOneField(MPSRevisionOptimizationRun, on_delete=models.PROTECT, related_name="decision_cockpit")
    baseline_revision = models.ForeignKey(MPSRevision, on_delete=models.PROTECT, related_name="decision_cockpit_baselines")
    selected_candidate = models.ForeignKey(MPSRevisionOptimizationCandidate, null=True, blank=True, on_delete=models.PROTECT, related_name="decision_cockpits_selected")
    official_revision = models.ForeignKey(MPSRevision, null=True, blank=True, on_delete=models.PROTECT, related_name="official_decision_cockpits")
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.OPEN)
    selection_rationale = models.TextField(blank=True)
    executive_notes = models.TextField(blank=True)
    decision_snapshot = models.JSONField(default=dict, blank=True)
    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL, related_name="mps_decision_cockpits_created")
    selected_by = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL, related_name="mps_decision_cockpits_selected")
    selected_at = models.DateTimeField(null=True, blank=True)
    submitted_by = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL, related_name="mps_decision_cockpits_submitted")
    submitted_at = models.DateTimeField(null=True, blank=True)
    approved_by = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL, related_name="mps_decision_cockpits_approved")
    approved_at = models.DateTimeField(null=True, blank=True)
    frozen_by = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL, related_name="mps_decision_cockpits_frozen")
    frozen_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ["-created_at"]
        indexes = [models.Index(fields=["publication", "status"], name="ix_mpsdec_pub_status")]

    def __str__(self):
        return f"Cockpit #{self.pk} · {self.publication.source} · {self.status}"


class MPSDecisionCandidateReview(TimeStampedModel):
    cockpit = models.ForeignKey(MPSDecisionCockpit, on_delete=models.CASCADE, related_name="candidate_reviews")
    candidate = models.ForeignKey(MPSRevisionOptimizationCandidate, on_delete=models.CASCADE, related_name="decision_reviews")
    shortlisted = models.BooleanField(default=False)
    business_label = models.CharField(max_length=120, blank=True)
    executive_note = models.TextField(blank=True)
    priority = models.PositiveIntegerField(default=0)
    reviewed_by = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL, related_name="mps_decision_candidate_reviews")
    reviewed_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ["-shortlisted", "priority", "candidate__pareto_rank", "candidate__rank", "id"]
        constraints = [models.UniqueConstraint(fields=["cockpit", "candidate"], name="uq_mpsdec_cockpit_candidate")]
        indexes = [models.Index(fields=["cockpit", "shortlisted"], name="ix_mpsdec_review_short")]


# 0.9.1 — formal decision minutes and cross-functional approvals
class MPSDecisionGovernancePolicy(TimeStampedModel):
    DEFAULT_AREAS = ["PLANNING", "PRODUCTION", "PURCHASING", "SALES", "FINANCE"]
    plant = models.OneToOneField(Plant, on_delete=models.CASCADE, related_name="mps_decision_governance_policy")
    required_areas = models.JSONField(default=list, blank=True)
    require_area_approvals = models.BooleanField(default=True)
    require_risk_acceptance = models.BooleanField(default=True)
    require_conditions_closed = models.BooleanField(default=False)
    minimum_participants = models.PositiveIntegerField(default=2)
    is_active = models.BooleanField(default=True)

    def effective_required_areas(self):
        return self.required_areas or self.DEFAULT_AREAS

    def __str__(self):
        return f"Governança MPS · {self.plant.code}"


class MPSDecisionMeeting(TimeStampedModel):
    cockpit = models.OneToOneField(MPSDecisionCockpit, on_delete=models.CASCADE, related_name="meeting")
    title = models.CharField(max_length=180, default="Reunião de decisão MRP/MPS")
    meeting_at = models.DateTimeField(null=True, blank=True)
    location = models.CharField(max_length=180, blank=True)
    agenda = models.TextField(blank=True)
    minutes = models.TextField(blank=True)
    conclusion = models.TextField(blank=True)
    minute_number = models.CharField(max_length=60, blank=True)
    closed_at = models.DateTimeField(null=True, blank=True)
    closed_by = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL, related_name="mps_decision_meetings_closed")

    def __str__(self):
        return self.minute_number or f"Ata cockpit #{self.cockpit_id}"


class MPSDecisionParticipant(TimeStampedModel):
    class Area(models.TextChoices):
        PLANNING="PLANNING", "Planejamento"
        PRODUCTION="PRODUCTION", "Produção"
        PURCHASING="PURCHASING", "Compras"
        SALES="SALES", "Comercial"
        FINANCE="FINANCE", "Finanças"
        QUALITY="QUALITY", "Qualidade"
        MAINTENANCE="MAINTENANCE", "Manutenção"
        EXECUTIVE="EXECUTIVE", "Executivo"
        OTHER="OTHER", "Outra"
    meeting = models.ForeignKey(MPSDecisionMeeting, on_delete=models.CASCADE, related_name="participants")
    user = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL, related_name="mps_decision_participations")
    name = models.CharField(max_length=160)
    area = models.CharField(max_length=20, choices=Area.choices)
    role_title = models.CharField(max_length=120, blank=True)
    attended = models.BooleanField(default=True)
    is_decision_maker = models.BooleanField(default=False)

    class Meta:
        ordering=["area","name"]
        indexes=[models.Index(fields=["meeting","area"], name="ix_mpsdec_part_area")]


class MPSDecisionComment(TimeStampedModel):
    cockpit = models.ForeignKey(MPSDecisionCockpit, on_delete=models.CASCADE, related_name="formal_comments")
    author = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL, related_name="mps_decision_formal_comments")
    area = models.CharField(max_length=20, choices=MPSDecisionParticipant.Area.choices, default=MPSDecisionParticipant.Area.OTHER)
    text = models.TextField()
    is_resolved = models.BooleanField(default=False)
    resolved_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering=["created_at"]


class MPSDecisionRiskAcceptance(TimeStampedModel):
    class Status(models.TextChoices):
        OPEN="OPEN", "Aberto"
        ACCEPTED="ACCEPTED", "Risco aceito"
        MITIGATED="MITIGATED", "Mitigado"
        REJECTED="REJECTED", "Não aceito"
    cockpit = models.ForeignKey(MPSDecisionCockpit, on_delete=models.CASCADE, related_name="risk_acceptances")
    category = models.CharField(max_length=40)
    description = models.TextField()
    impact = models.TextField(blank=True)
    mitigation = models.TextField(blank=True)
    owner = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL, related_name="mps_decision_risks_owned")
    status = models.CharField(max_length=16, choices=Status.choices, default=Status.OPEN)
    accepted_by = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL, related_name="mps_decision_risks_accepted")
    accepted_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering=["status","category","id"]


class MPSDecisionCondition(TimeStampedModel):
    class Status(models.TextChoices):
        OPEN="OPEN", "Aberta"
        SATISFIED="SATISFIED", "Atendida"
        WAIVED="WAIVED", "Dispensada"
    cockpit = models.ForeignKey(MPSDecisionCockpit, on_delete=models.CASCADE, related_name="approval_conditions")
    description = models.TextField()
    due_date = models.DateField(null=True, blank=True)
    owner = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL, related_name="mps_decision_conditions_owned")
    status = models.CharField(max_length=16, choices=Status.choices, default=Status.OPEN)
    closed_by = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL, related_name="mps_decision_conditions_closed")
    closed_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering=["status","due_date","id"]


class MPSDecisionAreaApproval(TimeStampedModel):
    class Decision(models.TextChoices):
        PENDING="PENDING", "Pendente"
        APPROVED="APPROVED", "Aprovado"
        REJECTED="REJECTED", "Rejeitado"
        ABSTAINED="ABSTAINED", "Abstenção"
    cockpit = models.ForeignKey(MPSDecisionCockpit, on_delete=models.CASCADE, related_name="area_approvals")
    area = models.CharField(max_length=20, choices=MPSDecisionParticipant.Area.choices)
    is_required = models.BooleanField(default=True)
    decision = models.CharField(max_length=16, choices=Decision.choices, default=Decision.PENDING)
    approver = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL, related_name="mps_decision_area_approvals")
    decided_at = models.DateTimeField(null=True, blank=True)
    comment = models.TextField(blank=True)

    class Meta:
        ordering=["area"]
        constraints=[models.UniqueConstraint(fields=["cockpit","area"], name="uq_mpsdec_cockpit_area")]
        indexes=[models.Index(fields=["cockpit","decision"], name="ix_mpsdec_area_decision")]


class MPSDecisionAttachment(TimeStampedModel):
    cockpit = models.ForeignKey(MPSDecisionCockpit, on_delete=models.CASCADE, related_name="attachments_091")
    file = models.FileField(upload_to="mps_decisions/%Y/%m/")
    title = models.CharField(max_length=180, blank=True)
    uploaded_by = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL, related_name="mps_decision_attachments")
    description = models.TextField(blank=True)

    class Meta:
        ordering=["created_at"]


# 0.9.2 — authority matrix and application electronic signatures
class MPSDecisionApprovalMatrix(TimeStampedModel):
    class Level(models.TextChoices):
        MANAGER="MANAGER", "Gerente"
        DIRECTOR="DIRECTOR", "Diretor"
        EXECUTIVE_COMMITTEE="EXECUTIVE_COMMITTEE", "Comitê executivo"
    plant = models.ForeignKey(Plant, on_delete=models.CASCADE, related_name="mps_decision_approval_matrix")
    name = models.CharField(max_length=120)
    level = models.CharField(max_length=24, choices=Level.choices)
    priority = models.PositiveIntegerField(default=10)
    is_default = models.BooleanField(default=False)
    min_purchase_spend = models.DecimalField(max_digits=22, decimal_places=2, default=0)
    min_peak_working_capital = models.DecimalField(max_digits=22, decimal_places=2, default=0)
    min_peak_financing_need = models.DecimalField(max_digits=22, decimal_places=2, default=0)
    min_service_risk_proxy = models.DecimalField(max_digits=22, decimal_places=4, default=0)
    required_groups = models.JSONField(default=list, blank=True)
    required_signatures = models.PositiveIntegerField(default=1)
    is_active = models.BooleanField(default=True)

    class Meta:
        ordering=["plant","priority","id"]
        indexes=[models.Index(fields=["plant","is_active","priority"], name="ix_mpsdec_matrix_active")]

    def __str__(self):
        return f"{self.plant.code} · {self.get_level_display()} · {self.name}"


class MPSDecisionApprovalRequirement(TimeStampedModel):
    class Status(models.TextChoices):
        PENDING="PENDING", "Pendente"
        SATISFIED="SATISFIED", "Atendida"
        SUPERSEDED="SUPERSEDED", "Substituída"
    cockpit = models.ForeignKey(MPSDecisionCockpit, on_delete=models.CASCADE, related_name="authority_requirements")
    matrix_rule = models.ForeignKey(MPSDecisionApprovalMatrix, null=True, blank=True, on_delete=models.PROTECT, related_name="requirements")
    level = models.CharField(max_length=24, choices=MPSDecisionApprovalMatrix.Level.choices)
    required_groups = models.JSONField(default=list, blank=True)
    required_signatures = models.PositiveIntegerField(default=1)
    exposure_snapshot = models.JSONField(default=dict, blank=True)
    decision_content_hash = models.CharField(max_length=64)
    status = models.CharField(max_length=16, choices=Status.choices, default=Status.PENDING)
    satisfied_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering=["cockpit","-created_at"]
        indexes=[models.Index(fields=["cockpit","status"], name="ix_mpsdec_authreq_status")]


class MPSDecisionElectronicSignature(TimeStampedModel):
    class AuthenticationMethod(models.TextChoices):
        PASSWORD="PASSWORD", "Senha revalidada"
        SESSION="SESSION", "Sessão autenticada/SSO"
    requirement = models.ForeignKey(MPSDecisionApprovalRequirement, on_delete=models.CASCADE, related_name="signatures")
    signer = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="mps_decision_electronic_signatures")
    authentication_method = models.CharField(max_length=16, choices=AuthenticationMethod.choices)
    confirmation_statement = models.CharField(max_length=180)
    signed_at = models.DateTimeField()
    content_hash = models.CharField(max_length=64)
    signature_hash = models.CharField(max_length=64)
    signature_version = models.CharField(max_length=40, default="APP-HMAC-SHA256-V1")
    signer_username = models.CharField(max_length=150)
    signer_groups = models.JSONField(default=list, blank=True)
    client_ip = models.GenericIPAddressField(null=True, blank=True)
    user_agent = models.CharField(max_length=300, blank=True)

    class Meta:
        ordering=["signed_at","id"]
        constraints=[models.UniqueConstraint(fields=["requirement","signer"], name="uq_mpsdec_req_signer")]
        indexes=[models.Index(fields=["requirement","signed_at"], name="ix_mpsdec_sig_req_time")]

# 0.9.3 — tamper-evident chained audit trail and evidence packages
class MPSDecisionAuditEvent(TimeStampedModel):
    class EventType(models.TextChoices):
        COCKPIT_CREATED = "COCKPIT_CREATED", "Cockpit criado"
        CANDIDATE_SELECTED = "CANDIDATE_SELECTED", "Cenário selecionado"
        SIMULATION_REFERENCED = "SIMULATION_REFERENCED", "Simulação referenciada"
        LEGACY_BOOTSTRAP = "LEGACY_BOOTSTRAP", "Bootstrap legado"
        SUBMITTED = "SUBMITTED", "Enviado para aprovação"
        AREA_DECISION = "AREA_DECISION", "Decisão de área"
        RISK_ACCEPTED = "RISK_ACCEPTED", "Risco aceito"
        AUTHORITY_CREATED = "AUTHORITY_CREATED", "Alçada criada"
        ELECTRONIC_SIGNATURE = "ELECTRONIC_SIGNATURE", "Assinatura eletrônica"
        EXECUTIVE_APPROVED = "EXECUTIVE_APPROVED", "Aprovação executiva"
        EXECUTIVE_REJECTED = "EXECUTIVE_REJECTED", "Rejeição executiva"
        OFFICIAL_FROZEN = "OFFICIAL_FROZEN", "Plano oficial congelado"
        EVIDENCE_EXPORTED = "EVIDENCE_EXPORTED", "Pacote de evidências exportado"
        ANCHOR_PUBLISHED = "ANCHOR_PUBLISHED", "Âncora externa publicada"
        ANCHOR_VERIFIED = "ANCHOR_VERIFIED", "Âncora externa verificada"
        NOTE = "NOTE", "Evento informativo"

    cockpit = models.ForeignKey(MPSDecisionCockpit, on_delete=models.CASCADE, related_name="audit_events")
    sequence = models.PositiveIntegerField()
    event_type = models.CharField(max_length=40, choices=EventType.choices)
    occurred_at = models.DateTimeField(default=timezone.now)
    actor = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL, related_name="mps_decision_audit_events")
    actor_username = models.CharField(max_length=150, blank=True)
    payload = models.JSONField(default=dict, blank=True)
    previous_hash = models.CharField(max_length=64, blank=True)
    event_hash = models.CharField(max_length=64, unique=True)
    hash_algorithm = models.CharField(max_length=24, default="SHA256")

    class Meta:
        ordering = ["cockpit", "sequence"]
        constraints = [models.UniqueConstraint(fields=["cockpit", "sequence"], name="uq_mpsdec_audit_seq")]
        indexes = [models.Index(fields=["cockpit", "sequence"], name="ix_mpsdec_audit_seq"), models.Index(fields=["event_type", "occurred_at"], name="ix_mpsdec_audit_type")]

    def __str__(self):
        return f"Cockpit #{self.cockpit_id} · {self.sequence} · {self.event_type}"


class MPSDecisionEvidenceExport(TimeStampedModel):
    cockpit = models.ForeignKey(MPSDecisionCockpit, on_delete=models.CASCADE, related_name="evidence_exports")
    generated_by = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL, related_name="mps_decision_evidence_exports")
    generated_at = models.DateTimeField(default=timezone.now)
    audit_head_hash = models.CharField(max_length=64, blank=True)
    audit_event_count = models.PositiveIntegerField(default=0)
    verification_ok = models.BooleanField(default=False)
    manifest = models.JSONField(default=dict, blank=True)
    package_sha256 = models.CharField(max_length=64, blank=True)
    file_name = models.CharField(max_length=220, blank=True)

    class Meta:
        ordering = ["-generated_at", "-id"]
        indexes = [models.Index(fields=["cockpit", "generated_at"], name="ix_mpsdec_export_time")]

# 0.9.4 — external integrity anchors for the 0.9.3 audit chain
class MPSDecisionAuditAnchor(TimeStampedModel):
    class Provider(models.TextChoices):
        FILE_APPEND_ONLY = "FILE_APPEND_ONLY", "Arquivo append-only primário"
        FILE_SECONDARY = "FILE_SECONDARY", "Arquivo append-only secundário"
        MANUAL_EXTERNAL = "MANUAL_EXTERNAL", "Âncora externa manual"
    class Status(models.TextChoices):
        ANCHORED = "ANCHORED", "Ancorada"
        VERIFIED = "VERIFIED", "Verificada"
        MISMATCH = "MISMATCH", "Divergente"
        ERROR = "ERROR", "Erro"

    cockpit = models.ForeignKey(MPSDecisionCockpit, on_delete=models.CASCADE, related_name="audit_anchors")
    provider = models.CharField(max_length=32, choices=Provider.choices, default=Provider.FILE_APPEND_ONLY)
    anchored_sequence = models.PositiveIntegerField()
    anchored_head_hash = models.CharField(max_length=64)
    anchored_at = models.DateTimeField(default=timezone.now)
    external_reference = models.CharField(max_length=500, blank=True)
    receipt = models.JSONField(default=dict, blank=True)
    receipt_hash = models.CharField(max_length=64, blank=True)
    status = models.CharField(max_length=16, choices=Status.choices, default=Status.ANCHORED)
    verified_at = models.DateTimeField(null=True, blank=True)
    verification_details = models.JSONField(default=dict, blank=True)
    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL, related_name="mps_decision_audit_anchors")

    class Meta:
        ordering = ["cockpit", "anchored_sequence", "id"]
        constraints = [models.UniqueConstraint(fields=["cockpit", "provider", "anchored_sequence", "anchored_head_hash"], name="uq_mpsdec_anchor_provider_point")]
        indexes = [models.Index(fields=["cockpit", "anchored_sequence"], name="ix_mpsdec_anchor_seq"), models.Index(fields=["status", "anchored_at"], name="ix_mpsdec_anchor_status")]

    def __str__(self):
        return f"Cockpit #{self.cockpit_id} · anchor @{self.anchored_sequence} · {self.status}"


# 0.9.5 — automatic external-anchor policy and protection monitoring
class MPSDecisionAnchorPolicy(TimeStampedModel):
    class Cadence(models.TextChoices):
        ON_FREEZE = "ON_FREEZE", "Ao congelar plano"
        DAILY = "DAILY", "Diária"
        BOTH = "BOTH", "Ao congelar + diária"

    plant = models.OneToOneField(Plant, on_delete=models.CASCADE, related_name="mps_decision_anchor_policy")
    is_active = models.BooleanField(default=True)
    cadence = models.CharField(max_length=16, choices=Cadence.choices, default=Cadence.BOTH)
    required_providers = models.JSONField(default=list, blank=True, help_text="Providers independentes exigidos para considerar a decisão protegida.")
    max_anchor_age_hours = models.PositiveIntegerField(default=24)
    retention_days = models.PositiveIntegerField(default=3650)
    verify_after_publish = models.BooleanField(default=True)
    protect_active_cockpits = models.BooleanField(default=False)
    notes = models.TextField(blank=True)

    class Meta:
        ordering = ["plant__code"]

    def __str__(self):
        return f"{self.plant.code} · anchor policy {self.cadence}"

# 0.9.6 — Security & Compliance Center for MPS decision integrity
class MPSDecisionCompliancePolicy(TimeStampedModel):
    plant = models.OneToOneField(Plant, on_delete=models.CASCADE, related_name="mps_decision_compliance_policy")
    is_active = models.BooleanField(default=True)
    alert_recipients = models.JSONField(default=list, blank=True, help_text="Lista de e-mails que recebem alertas de compliance.")
    alert_statuses = models.JSONField(default=list, blank=True, help_text="Statuses que geram alerta; vazio usa STALE/UNPROTECTED/MISMATCH.")
    standard_sla_hours = models.PositiveIntegerField(default=24)
    high_sla_hours = models.PositiveIntegerField(default=12)
    critical_sla_hours = models.PositiveIntegerField(default=4)
    auto_export_evidence = models.BooleanField(default=True)
    evidence_max_age_hours = models.PositiveIntegerField(default=168)
    send_email_alerts = models.BooleanField(default=True)
    snapshot_retention_days = models.PositiveIntegerField(default=1095)
    notes = models.TextField(blank=True)

    class Meta:
        ordering = ["plant__code"]

    def __str__(self):
        return f"{self.plant.code} · compliance policy"


class MPSDecisionComplianceIncident(TimeStampedModel):
    class Category(models.TextChoices):
        STALE = "STALE", "Âncora vencida"
        UNPROTECTED = "UNPROTECTED", "Sem proteção"
        MISMATCH = "MISMATCH", "Divergência de integridade"
        SLA_BREACH = "SLA_BREACH", "SLA de proteção excedido"
        EVIDENCE_STALE = "EVIDENCE_STALE", "Evidência periódica vencida"
    class Severity(models.TextChoices):
        LOW = "LOW", "Baixa"
        MEDIUM = "MEDIUM", "Média"
        HIGH = "HIGH", "Alta"
        CRITICAL = "CRITICAL", "Crítica"
    class Status(models.TextChoices):
        OPEN = "OPEN", "Aberto"
        ACKNOWLEDGED = "ACKNOWLEDGED", "Reconhecido"
        RESOLVED = "RESOLVED", "Resolvido"

    cockpit = models.ForeignKey(MPSDecisionCockpit, on_delete=models.CASCADE, related_name="compliance_incidents")
    category = models.CharField(max_length=24, choices=Category.choices)
    severity = models.CharField(max_length=16, choices=Severity.choices, default=Severity.MEDIUM)
    status = models.CharField(max_length=16, choices=Status.choices, default=Status.OPEN)
    first_seen_at = models.DateTimeField(default=timezone.now)
    last_seen_at = models.DateTimeField(default=timezone.now)
    message = models.TextField()
    details = models.JSONField(default=dict, blank=True)
    responsible_area = models.CharField(max_length=40, blank=True)
    responsible_user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="responsible_mps_compliance_incidents",
    )
    alerted_at = models.DateTimeField(null=True, blank=True)
    acknowledged_by = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL, related_name="acknowledged_mps_compliance_incidents")
    acknowledged_at = models.DateTimeField(null=True, blank=True)
    resolved_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ["status", "-severity", "-last_seen_at"]
        indexes = [
            models.Index(fields=["status", "severity", "last_seen_at"], name="ix_mpscomp_inc_status"),
            models.Index(fields=["cockpit", "category", "status"], name="ix_mpscomp_inc_cockpit"),
        ]

    def __str__(self):
        return f"Cockpit #{self.cockpit_id} · {self.category} · {self.status}"


class MPSDecisionComplianceSnapshot(TimeStampedModel):
    plant = models.ForeignKey(Plant, on_delete=models.CASCADE, related_name="mps_decision_compliance_snapshots")
    snapshot_date = models.DateField()
    monitored_count = models.PositiveIntegerField(default=0)
    protected_count = models.PositiveIntegerField(default=0)
    stale_count = models.PositiveIntegerField(default=0)
    unprotected_count = models.PositiveIntegerField(default=0)
    mismatch_count = models.PositiveIntegerField(default=0)
    protected_percent = models.DecimalField(max_digits=7, decimal_places=2, default=0)
    evidence_current_percent = models.DecimalField(max_digits=7, decimal_places=2, default=0)
    avg_minutes_to_first_anchor = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    integrity_failures = models.PositiveIntegerField(default=0)
    open_incidents = models.PositiveIntegerField(default=0)
    details = models.JSONField(default=dict, blank=True)

    class Meta:
        ordering = ["-snapshot_date", "plant__code"]
        constraints = [models.UniqueConstraint(fields=["plant", "snapshot_date"], name="uq_mpscomp_snapshot_day")]
        indexes = [models.Index(fields=["plant", "snapshot_date"], name="ix_mpscomp_snapshot_day")]

    def __str__(self):
        return f"{self.plant.code} · compliance {self.snapshot_date}"

# 0.9.7 — Compliance SLA & Escalation Engine
class MPSComplianceEscalationPolicy(TimeStampedModel):
    plant = models.OneToOneField(Plant, on_delete=models.CASCADE, related_name="mps_compliance_escalation_policy")
    is_active = models.BooleanField(default=True)
    repeat_notifications = models.BooleanField(default=True)
    repeat_interval_minutes = models.PositiveIntegerField(default=60)
    max_repeat_notifications = models.PositiveIntegerField(default=6)
    use_on_call_contacts = models.BooleanField(default=True)
    send_email = models.BooleanField(default=True)
    notes = models.TextField(blank=True)

    class Meta:
        ordering = ["plant__code"]

    def __str__(self):
        return f"{self.plant.code} · escalation policy"


class MPSComplianceEscalationRule(TimeStampedModel):
    class Level(models.TextChoices):
        TEAM = "TEAM", "Equipe"
        MANAGER = "MANAGER", "Gerente"
        DIRECTOR = "DIRECTOR", "Diretor"
        EXECUTIVE = "EXECUTIVE", "Executivo"

    policy = models.ForeignKey(MPSComplianceEscalationPolicy, on_delete=models.CASCADE, related_name="rules")
    name = models.CharField(max_length=120)
    level = models.CharField(max_length=16, choices=Level.choices)
    order = models.PositiveIntegerField(default=10)
    after_minutes = models.PositiveIntegerField(help_text="Minutos desde first_seen_at para ativar a regra.")
    severities = models.JSONField(default=list, blank=True, help_text="LOW/MEDIUM/HIGH/CRITICAL; vazio = todas.")
    categories = models.JSONField(default=list, blank=True, help_text="Categorias de incidente; vazio = todas.")
    class ClockBasis(models.TextChoices):
        FIRST_SEEN = "FIRST_SEEN", "Desde abertura"
        ACKNOWLEDGED = "ACKNOWLEDGED", "Desde reconhecimento"
    clock_basis = models.CharField(max_length=20, choices=ClockBasis.choices, default=ClockBasis.FIRST_SEEN)
    recipient_emails = models.JSONField(default=list, blank=True)
    notification_channels = models.JSONField(default=list, blank=True, help_text="EMAIL/API/TEAMS/SLACK; vazio usa EMAIL.")
    channel_endpoints = models.JSONField(default=dict, blank=True, help_text="Endpoints por canal, ex.: {\"SLACK\": \"https://...\"}.")
    recipient_groups = models.JSONField(default=list, blank=True, help_text="Grupos Django cujos usuários ativos com e-mail serão avisados.")
    repeat_interval_minutes = models.PositiveIntegerField(null=True, blank=True, help_text="Override da política.")
    max_notifications = models.PositiveIntegerField(null=True, blank=True, help_text="Override da política.")
    is_active = models.BooleanField(default=True)

    class Meta:
        ordering = ["policy__plant__code", "order", "after_minutes", "id"]
        constraints = [models.UniqueConstraint(fields=["policy", "order"], name="uq_mpscomp_esc_rule_order")]

    def __str__(self):
        return f"{self.policy.plant.code} · {self.level} · {self.after_minutes}m"


class MPSComplianceOnCallContact(TimeStampedModel):
    plant = models.ForeignKey(Plant, on_delete=models.CASCADE, related_name="mps_compliance_on_call_contacts")
    name = models.CharField(max_length=120)
    email = models.EmailField()
    levels = models.JSONField(default=list, blank=True, help_text="Níveis atendidos; vazio = todos.")
    weekdays = models.JSONField(default=list, blank=True, help_text="0=segunda ... 6=domingo; vazio = todos.")
    start_time = models.TimeField(null=True, blank=True)
    end_time = models.TimeField(null=True, blank=True)
    include_holidays = models.BooleanField(default=False, help_text="Atende também em feriados corporativos.")
    channels = models.JSONField(default=list, blank=True, help_text="EMAIL/API/TEAMS/SLACK; vazio = EMAIL.")
    api_url = models.URLField(blank=True)
    teams_webhook_url = models.URLField(blank=True)
    slack_webhook_url = models.URLField(blank=True)
    is_active = models.BooleanField(default=True)

    class Meta:
        ordering = ["plant__code", "name"]
        indexes = [models.Index(fields=["plant", "is_active"], name="ix_mpscomp_oncall")]

    def __str__(self):
        return f"{self.plant.code} · {self.name}"


class MPSComplianceEscalationEvent(TimeStampedModel):
    class Status(models.TextChoices):
        ACTIVE = "ACTIVE", "Ativo"
        STOPPED = "STOPPED", "Encerrado"

    incident = models.ForeignKey(MPSDecisionComplianceIncident, on_delete=models.CASCADE, related_name="escalation_events")
    rule = models.ForeignKey(MPSComplianceEscalationRule, on_delete=models.PROTECT, related_name="events")
    level = models.CharField(max_length=16, choices=MPSComplianceEscalationRule.Level.choices)
    status = models.CharField(max_length=16, choices=Status.choices, default=Status.ACTIVE)
    activated_at = models.DateTimeField(default=timezone.now)
    first_notified_at = models.DateTimeField(null=True, blank=True)
    last_notified_at = models.DateTimeField(null=True, blank=True)
    notification_count = models.PositiveIntegerField(default=0)
    recipients = models.JSONField(default=list, blank=True)
    details = models.JSONField(default=dict, blank=True)
    stopped_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ["-activated_at", "-id"]
        constraints = [models.UniqueConstraint(fields=["incident", "rule"], name="uq_mpscomp_inc_rule_event")]
        indexes = [models.Index(fields=["status", "level", "activated_at"], name="ix_mpscomp_esc_active")]

    def __str__(self):
        return f"Incident #{self.incident_id} · {self.level}"


# 0.9.8 — Corporate escalation calendar, absences, substitutions and channel delivery log.
class MPSComplianceHoliday(TimeStampedModel):
    plant = models.ForeignKey(Plant, on_delete=models.CASCADE, related_name="mps_compliance_holidays")
    date = models.DateField()
    name = models.CharField(max_length=120)
    is_active = models.BooleanField(default=True)

    class Meta:
        ordering = ["plant__code", "date"]
        constraints = [models.UniqueConstraint(fields=["plant", "date"], name="uq_mpscomp_holiday_day")]
        indexes = [models.Index(fields=["plant", "date", "is_active"], name="ix_mpscomp_holiday")]

    def __str__(self):
        return f"{self.plant.code} · {self.date} · {self.name}"


class MPSComplianceOnCallAbsence(TimeStampedModel):
    contact = models.ForeignKey(MPSComplianceOnCallContact, on_delete=models.CASCADE, related_name="absences")
    starts_at = models.DateTimeField()
    ends_at = models.DateTimeField()
    reason = models.CharField(max_length=200, blank=True)
    is_active = models.BooleanField(default=True)

    class Meta:
        ordering = ["-starts_at"]
        indexes = [models.Index(fields=["contact", "starts_at", "ends_at", "is_active"], name="ix_mpscomp_absence")]

    def __str__(self):
        return f"{self.contact} · ausência {self.starts_at:%Y-%m-%d}"


class MPSComplianceOnCallSubstitution(TimeStampedModel):
    primary_contact = models.ForeignKey(MPSComplianceOnCallContact, on_delete=models.CASCADE, related_name="substitutions_as_primary")
    substitute_contact = models.ForeignKey(MPSComplianceOnCallContact, on_delete=models.CASCADE, related_name="substitutions_as_substitute")
    starts_at = models.DateTimeField()
    ends_at = models.DateTimeField()
    levels = models.JSONField(default=list, blank=True, help_text="Níveis cobertos; vazio = todos.")
    reason = models.CharField(max_length=200, blank=True)
    is_active = models.BooleanField(default=True)

    class Meta:
        ordering = ["-starts_at"]
        indexes = [models.Index(fields=["primary_contact", "starts_at", "ends_at", "is_active"], name="ix_mpscomp_subst")]

    def __str__(self):
        return f"{self.primary_contact.name} → {self.substitute_contact.name}"


class MPSComplianceNotificationDelivery(TimeStampedModel):
    class Channel(models.TextChoices):
        EMAIL = "EMAIL", "E-mail"
        API = "API", "API"
        TEAMS = "TEAMS", "Teams webhook"
        SLACK = "SLACK", "Slack webhook"
    class Status(models.TextChoices):
        SENT = "SENT", "Enviado"
        FAILED = "FAILED", "Falhou"
        SKIPPED = "SKIPPED", "Ignorado"

    event = models.ForeignKey(MPSComplianceEscalationEvent, on_delete=models.CASCADE, related_name="deliveries")
    channel = models.CharField(max_length=12, choices=Channel.choices)
    destination = models.CharField(max_length=500, blank=True)
    status = models.CharField(max_length=12, choices=Status.choices)
    attempted_at = models.DateTimeField(default=timezone.now)
    response_code = models.IntegerField(null=True, blank=True)
    error = models.TextField(blank=True)
    details = models.JSONField(default=dict, blank=True)

    class Meta:
        ordering = ["-attempted_at", "-id"]
        indexes = [models.Index(fields=["channel", "status", "attempted_at"], name="ix_mpscomp_delivery")]

    def __str__(self):
        return f"Escalation #{self.event_id} · {self.channel} · {self.status}"


# 0.9.9 — Incident Command & Postmortem
class MPSIncidentCommandPolicy(TimeStampedModel):
    plant = models.OneToOneField(Plant, on_delete=models.CASCADE, related_name="mps_incident_command_policy")
    is_active = models.BooleanField(default=True)
    auto_promote_levels = models.JSONField(default=list, blank=True, help_text="Escalation levels that automatically create a major incident; empty defaults to EXECUTIVE.")
    auto_promote_severities = models.JSONField(default=list, blank=True, help_text="Incident severities eligible for auto promotion; empty defaults to CRITICAL.")
    require_postmortem_for = models.JSONField(default=list, blank=True, help_text="Major incident severities requiring approved postmortem before closure; empty defaults to SEV1/SEV2.")
    notes = models.TextField(blank=True)

    class Meta:
        ordering = ["plant__code"]

    def __str__(self):
        return f"{self.plant.code} · incident command policy"


class MPSMajorIncident(TimeStampedModel):
    class Severity(models.TextChoices):
        SEV1 = "SEV1", "Crítico"
        SEV2 = "SEV2", "Alto"
        SEV3 = "SEV3", "Moderado"
        SEV4 = "SEV4", "Baixo"
    class Status(models.TextChoices):
        DETECTED = "DETECTED", "Detectado"
        ACTIVE = "ACTIVE", "Em resposta"
        MONITORING = "MONITORING", "Monitorando"
        RESOLVED = "RESOLVED", "Resolvido"
        CLOSED = "CLOSED", "Encerrado"

    plant = models.ForeignKey(Plant, on_delete=models.PROTECT, related_name="mps_major_incidents")
    code = models.CharField(max_length=40, unique=True)
    title = models.CharField(max_length=220)
    severity = models.CharField(max_length=8, choices=Severity.choices, default=Severity.SEV2)
    status = models.CharField(max_length=16, choices=Status.choices, default=Status.DETECTED)
    commander = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL, related_name="commanded_mps_major_incidents")
    compliance_incidents = models.ManyToManyField(MPSDecisionComplianceIncident, blank=True, related_name="major_incidents")
    summary = models.TextField(blank=True)
    impact = models.TextField(blank=True)
    war_room_url = models.URLField(blank=True)
    started_at = models.DateTimeField(default=timezone.now)
    acknowledged_at = models.DateTimeField(null=True, blank=True)
    resolved_at = models.DateTimeField(null=True, blank=True)
    closed_at = models.DateTimeField(null=True, blank=True)
    closed_by = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL, related_name="closed_mps_major_incidents")
    details = models.JSONField(default=dict, blank=True)

    class Meta:
        ordering = ["-started_at", "-id"]
        indexes = [models.Index(fields=["plant", "status", "severity"], name="ix_mps_major_incident")]

    def __str__(self):
        return f"{self.code} · {self.title}"


class MPSMajorIncidentTimelineEvent(TimeStampedModel):
    class EventType(models.TextChoices):
        DETECTED = "DETECTED", "Detectado"
        COMMAND = "COMMAND", "Comando"
        UPDATE = "UPDATE", "Atualização"
        DECISION = "DECISION", "Decisão"
        MITIGATION = "MITIGATION", "Mitigação"
        ESCALATION = "ESCALATION", "Escalonamento"
        RECOVERY = "RECOVERY", "Recuperação"
        RESOLVED = "RESOLVED", "Resolvido"
        CLOSED = "CLOSED", "Encerrado"

    incident = models.ForeignKey(MPSMajorIncident, on_delete=models.CASCADE, related_name="timeline")
    event_type = models.CharField(max_length=16, choices=EventType.choices, default=EventType.UPDATE)
    occurred_at = models.DateTimeField(default=timezone.now)
    message = models.TextField()
    actor = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL, related_name="mps_major_incident_timeline_events")
    details = models.JSONField(default=dict, blank=True)

    class Meta:
        ordering = ["occurred_at", "id"]
        indexes = [models.Index(fields=["incident", "occurred_at"], name="ix_mps_major_timeline")]


class MPSMajorIncidentAction(TimeStampedModel):
    class ActionType(models.TextChoices):
        CONTAINMENT = "CONTAINMENT", "Contenção"
        CORRECTIVE = "CORRECTIVE", "Corretiva"
        PREVENTIVE = "PREVENTIVE", "Preventiva"
    class Status(models.TextChoices):
        OPEN = "OPEN", "Aberta"
        IN_PROGRESS = "IN_PROGRESS", "Em andamento"
        DONE = "DONE", "Concluída"
        CANCELLED = "CANCELLED", "Cancelada"

    incident = models.ForeignKey(MPSMajorIncident, on_delete=models.CASCADE, related_name="actions")
    action_type = models.CharField(max_length=16, choices=ActionType.choices, default=ActionType.CORRECTIVE)
    title = models.CharField(max_length=220)
    description = models.TextField(blank=True)
    owner = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL, related_name="owned_mps_major_incident_actions")
    due_at = models.DateTimeField(null=True, blank=True)
    status = models.CharField(max_length=16, choices=Status.choices, default=Status.OPEN)
    completed_at = models.DateTimeField(null=True, blank=True)
    verification = models.TextField(blank=True)

    class Meta:
        ordering = ["status", "due_at", "id"]
        indexes = [models.Index(fields=["incident", "status", "due_at"], name="ix_mps_major_action")]


class MPSMajorIncidentPostmortem(TimeStampedModel):
    class Status(models.TextChoices):
        DRAFT = "DRAFT", "Rascunho"
        REVIEW = "REVIEW", "Em revisão"
        APPROVED = "APPROVED", "Aprovado"

    incident = models.OneToOneField(MPSMajorIncident, on_delete=models.CASCADE, related_name="postmortem")
    status = models.CharField(max_length=16, choices=Status.choices, default=Status.DRAFT)
    executive_summary = models.TextField(blank=True)
    root_cause = models.TextField(blank=True)
    root_cause_category = models.CharField(max_length=40, blank=True)
    five_whys = models.JSONField(default=list, blank=True)
    contributing_factors = models.JSONField(default=list, blank=True)
    what_went_well = models.TextField(blank=True)
    what_went_wrong = models.TextField(blank=True)
    lessons_learned = models.TextField(blank=True)
    prevention_plan = models.TextField(blank=True)
    prepared_by = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL, related_name="prepared_mps_postmortems")
    approved_by = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL, related_name="approved_mps_postmortems")
    approved_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ["-created_at"]


class MPSMajorIncidentLearningAction(TimeStampedModel):
    class TargetType(models.TextChoices):
        MRP_POLICY = "MRP_POLICY", "Política MRP"
        MPS_POLICY = "MPS_POLICY", "Política MPS"
        COMPLIANCE = "COMPLIANCE", "Compliance"
        ESCALATION = "ESCALATION", "Escalonamento"
        MASTER_DATA = "MASTER_DATA", "Dados mestres"
        PROCESS = "PROCESS", "Processo"
    class Status(models.TextChoices):
        PROPOSED = "PROPOSED", "Proposta"
        ACCEPTED = "ACCEPTED", "Aceita"
        APPLIED = "APPLIED", "Aplicada"
        REJECTED = "REJECTED", "Rejeitada"

    postmortem = models.ForeignKey(MPSMajorIncidentPostmortem, on_delete=models.CASCADE, related_name="learning_actions")
    target_type = models.CharField(max_length=24, choices=TargetType.choices)
    description = models.TextField()
    owner = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL, related_name="owned_mps_learning_actions")
    status = models.CharField(max_length=16, choices=Status.choices, default=Status.PROPOSED)
    applied_at = models.DateTimeField(null=True, blank=True)
    evidence = models.TextField(blank=True)

    class Meta:
        ordering = ["status", "id"]
