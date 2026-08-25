from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):
    dependencies = [
        ("integrated_scheduling", "0005_multicriteria_optimizer_064"),
        ("production", "0001_initial"),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name="ScheduleSolverRun",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("status", models.CharField(choices=[("DRAFT", "Rascunho"), ("RUNNING", "Executando"), ("OPTIMAL", "Ótimo"), ("FEASIBLE", "Factível"), ("INFEASIBLE", "Inviável"), ("UNKNOWN", "Sem solução"), ("FAILED", "Falhou")], default="DRAFT", max_length=16)),
                ("solver", models.CharField(default="CP-SAT", max_length=24)),
                ("time_limit_seconds", models.PositiveIntegerField(default=30)),
                ("workers", models.PositiveSmallIntegerField(default=8)),
                ("time_granularity_minutes", models.PositiveSmallIntegerField(default=5)),
                ("weights", models.JSONField(blank=True, default=dict)),
                ("objective_value", models.DecimalField(blank=True, decimal_places=6, max_digits=24, null=True)),
                ("best_bound", models.DecimalField(blank=True, decimal_places=6, max_digits=24, null=True)),
                ("wall_time_seconds", models.DecimalField(decimal_places=4, default=0, max_digits=16)),
                ("conflicts", models.PositiveIntegerField(default=0)),
                ("branches", models.PositiveBigIntegerField(default=0)),
                ("summary", models.JSONField(blank=True, default=dict)),
                ("error_message", models.TextField(blank=True)),
                ("created_by", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="schedule_solver_runs", to=settings.AUTH_USER_MODEL)),
                ("scenario", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="solver_runs", to="integrated_scheduling.integratedschedulescenario")),
            ],
            options={"ordering": ["-created_at"]},
        ),
        migrations.CreateModel(
            name="ScheduleSolverAssignment",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("start", models.DateTimeField()),
                ("end", models.DateTimeField()),
                ("duration_minutes", models.PositiveIntegerField()),
                ("setup_minutes_before", models.PositiveIntegerField(default=0)),
                ("is_alternate_resource", models.BooleanField(default=False)),
                ("tardiness_minutes", models.PositiveIntegerField(default=0)),
                ("details", models.JSONField(blank=True, default=dict)),
                ("machine", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="solver_assignments", to="shopfloor.machine")),
                ("operation", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="solver_assignments", to="production.workorderoperation")),
                ("run", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="assignments", to="integrated_scheduling.schedulesolverrun")),
                ("work_center", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name="solver_assignments", to="masterdata.workcenter")),
            ],
            options={"ordering": ["start", "work_center__code", "machine__code"]},
        ),
        migrations.AddConstraint(model_name="schedulesolverrun", constraint=models.CheckConstraint(condition=models.Q(("time_limit_seconds__gte", 1)), name="ck_solver_time_limit_pos")),
        migrations.AddConstraint(model_name="schedulesolverrun", constraint=models.CheckConstraint(condition=models.Q(("workers__gte", 1)), name="ck_solver_workers_pos")),
        migrations.AddConstraint(model_name="schedulesolverrun", constraint=models.CheckConstraint(condition=models.Q(("time_granularity_minutes__gte", 1)), name="ck_solver_granularity_pos")),
        migrations.AddIndex(model_name="schedulesolverrun", index=models.Index(fields=["scenario", "status"], name="ix_solver_scenario_status")),
        migrations.AddConstraint(model_name="schedulesolverassignment", constraint=models.UniqueConstraint(fields=("run", "operation"), name="uq_solver_run_operation")),
        migrations.AddConstraint(model_name="schedulesolverassignment", constraint=models.CheckConstraint(condition=models.Q(("end__gte", models.F("start"))), name="ck_solver_assignment_window")),
        migrations.AddIndex(model_name="schedulesolverassignment", index=models.Index(fields=["run", "machine", "start"], name="ix_solver_assignment_machine")),
        migrations.AddIndex(model_name="schedulesolverassignment", index=models.Index(fields=["run", "work_center", "start"], name="ix_solver_assignment_center")),
    ]
