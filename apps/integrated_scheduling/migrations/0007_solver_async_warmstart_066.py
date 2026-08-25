from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):
    dependencies = [
        ("integrated_scheduling", "0006_cp_sat_solver_065"),
    ]

    operations = [
        migrations.AlterField(
            model_name="schedulesolverrun",
            name="status",
            field=models.CharField(choices=[("DRAFT", "Rascunho"), ("RUNNING", "Executando"), ("OPTIMAL", "Ótimo / dentro do gap"), ("FEASIBLE", "Factível"), ("INFEASIBLE", "Inviável"), ("UNKNOWN", "Sem solução"), ("FAILED", "Falhou"), ("CANCELLED", "Cancelado")], default="DRAFT", max_length=16),
        ),
        migrations.AddField(
            model_name="schedulesolverrun",
            name="execution_mode",
            field=models.CharField(choices=[("SYNC", "Síncrono"), ("ASYNC", "Assíncrono")], default="SYNC", max_length=12),
        ),
        migrations.AddField(
            model_name="schedulesolverrun",
            name="relative_gap_limit",
            field=models.DecimalField(decimal_places=6, default=0, max_digits=8),
        ),
        migrations.AddField(
            model_name="schedulesolverrun",
            name="warm_start_enabled",
            field=models.BooleanField(default=True),
        ),
        migrations.AddField(
            model_name="schedulesolverrun",
            name="warm_start_source",
            field=models.CharField(blank=True, max_length=40),
        ),
        migrations.AddField(
            model_name="schedulesolverrun",
            name="warm_start_scenario",
            field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="solver_warm_start_runs", to="integrated_scheduling.integratedschedulescenario"),
        ),
        migrations.AddField(
            model_name="schedulesolverrun",
            name="celery_task_id",
            field=models.CharField(blank=True, db_index=True, max_length=255),
        ),
        migrations.AddField(model_name="schedulesolverrun", name="cancel_requested_at", field=models.DateTimeField(blank=True, null=True)),
        migrations.AddField(model_name="schedulesolverrun", name="cancellation_reason", field=models.CharField(blank=True, max_length=255)),
        migrations.AddField(model_name="schedulesolverrun", name="started_at", field=models.DateTimeField(blank=True, null=True)),
        migrations.AddField(model_name="schedulesolverrun", name="finished_at", field=models.DateTimeField(blank=True, null=True)),
        migrations.AddField(model_name="schedulesolverrun", name="last_incumbent_at", field=models.DateTimeField(blank=True, null=True)),
        migrations.AddField(model_name="schedulesolverrun", name="progress", field=models.JSONField(blank=True, default=dict)),
        migrations.CreateModel(
            name="ScheduleSolverIncumbent",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("sequence", models.PositiveIntegerField()),
                ("objective_value", models.DecimalField(decimal_places=6, max_digits=24)),
                ("best_bound", models.DecimalField(blank=True, decimal_places=6, max_digits=24, null=True)),
                ("relative_gap", models.DecimalField(blank=True, decimal_places=8, max_digits=12, null=True)),
                ("wall_time_seconds", models.DecimalField(decimal_places=4, default=0, max_digits=16)),
                ("solution_count", models.PositiveIntegerField(default=0)),
                ("summary", models.JSONField(blank=True, default=dict)),
                ("run", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="incumbents", to="integrated_scheduling.schedulesolverrun")),
            ],
            options={"ordering": ["run", "sequence"]},
        ),
        migrations.AddConstraint(
            model_name="schedulesolverincumbent",
            constraint=models.UniqueConstraint(fields=("run", "sequence"), name="uq_solver_incumbent_sequence"),
        ),
        migrations.AddIndex(
            model_name="schedulesolverincumbent",
            index=models.Index(fields=["run", "sequence"], name="ix_solver_incumbent_run_seq"),
        ),
    ]
