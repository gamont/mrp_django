from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):
    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ("integrated_scheduling", "0004_advanced_sequence_063"),
    ]

    operations = [
        migrations.CreateModel(
            name="ScheduleOptimizationRun",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("status", models.CharField(choices=[("DRAFT", "Rascunho"), ("RUNNING", "Executando"), ("COMPLETED", "Concluído"), ("FAILED", "Falhou")], default="DRAFT", max_length=16)),
                ("candidate_count", models.PositiveSmallIntegerField(default=8)),
                ("weights", models.JSONField(blank=True, default=dict)),
                ("summary", models.JSONField(blank=True, default=dict)),
                ("error_message", models.TextField(blank=True)),
                ("base_scenario", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="optimization_runs", to="integrated_scheduling.integratedschedulescenario")),
                ("created_by", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="schedule_optimization_runs", to=settings.AUTH_USER_MODEL)),
            ],
            options={"ordering": ["-created_at"]},
        ),
        migrations.AddConstraint(model_name="scheduleoptimizationrun", constraint=models.CheckConstraint(condition=models.Q(("candidate_count__gte", 2), ("candidate_count__lte", 12)), name="ck_opt_candidate_count")),
        migrations.CreateModel(
            name="ScheduleOptimizationCandidate",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("strategy_code", models.CharField(max_length=80)),
                ("rank", models.PositiveSmallIntegerField(default=0)),
                ("objective_score", models.DecimalField(decimal_places=8, default=0, max_digits=18)),
                ("feasible", models.BooleanField(default=True)),
                ("pareto_front", models.BooleanField(default=False)),
                ("metrics", models.JSONField(blank=True, default=dict)),
                ("normalized_metrics", models.JSONField(blank=True, default=dict)),
                ("run", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="candidates", to="integrated_scheduling.scheduleoptimizationrun")),
                ("scenario", models.OneToOneField(on_delete=django.db.models.deletion.CASCADE, related_name="optimization_candidate", to="integrated_scheduling.integratedschedulescenario")),
            ],
            options={"ordering": ["rank", "objective_score", "pk"]},
        ),
        migrations.AddConstraint(model_name="scheduleoptimizationcandidate", constraint=models.UniqueConstraint(fields=("run", "strategy_code"), name="uq_opt_run_strategy")),
        migrations.AddIndex(model_name="scheduleoptimizationcandidate", index=models.Index(fields=["run", "rank"], name="ix_opt_candidate_rank")),
        migrations.AddField(
            model_name="scheduleoptimizationrun", name="best_candidate",
            field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="+", to="integrated_scheduling.scheduleoptimizationcandidate"),
        ),
    ]
