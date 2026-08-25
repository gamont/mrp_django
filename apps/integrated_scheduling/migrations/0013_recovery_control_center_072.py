from django.db import migrations, models
import django.db.models.deletion

class Migration(migrations.Migration):
    dependencies = [("integrated_scheduling", "0012_auto_recovery_071")]
    operations = [
        migrations.AddField(model_name="reschedulingtrigger", name="severity", field=models.CharField(choices=[("LOW","Baixa"),("MEDIUM","Média"),("HIGH","Alta"),("CRITICAL","Crítica")], default="MEDIUM", max_length=12)),
        migrations.AddField(model_name="reschedulingtrigger", name="impact_summary", field=models.JSONField(blank=True, default=dict)),
        migrations.AddField(model_name="reschedulingtrigger", name="recovery_eta_seconds", field=models.PositiveIntegerField(default=0)),
        migrations.AddField(model_name="reschedulingtrigger", name="auto_publish_attempted_at", field=models.DateTimeField(blank=True, null=True)),
        migrations.AddField(model_name="reschedulingtrigger", name="auto_published_at", field=models.DateTimeField(blank=True, null=True)),
        migrations.CreateModel(name="RecoveryPolicy", fields=[
            ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
            ("created_at", models.DateTimeField(auto_now_add=True)), ("updated_at", models.DateTimeField(auto_now=True)),
            ("is_active", models.BooleanField(default=True)), ("candidate_count", models.PositiveSmallIntegerField(default=3)),
            ("solver_time_limit_seconds", models.PositiveIntegerField(default=180)), ("auto_publish_enabled", models.BooleanField(default=False)),
            ("max_risk_score", models.DecimalField(decimal_places=2, default=20, max_digits=6)), ("max_moved_operations", models.PositiveIntegerField(default=3)),
            ("max_late_operations", models.PositiveIntegerField(default=0)), ("max_machine_changes", models.PositiveIntegerField(default=1)),
            ("max_impacted_sales_orders", models.PositiveIntegerField(default=0)), ("max_delay_minutes", models.PositiveIntegerField(default=30)),
            ("plant", models.OneToOneField(on_delete=django.db.models.deletion.CASCADE, related_name="recovery_policy", to="common.plant")),
        ], options={"ordering":["plant__code"]}),
        migrations.CreateModel(name="RecoveryPlan", fields=[
            ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
            ("created_at", models.DateTimeField(auto_now_add=True)), ("updated_at", models.DateTimeField(auto_now=True)),
            ("name", models.CharField(max_length=160)), ("strategy", models.CharField(default="BALANCED", max_length=60)),
            ("status", models.CharField(choices=[("DRAFT","Rascunho"),("QUEUED","Na fila"),("SOLVING","Otimizando"),("READY","Pronto"),("FAILED","Falhou"),("PUBLISHED","Publicado")], default="DRAFT", max_length=16)),
            ("rank", models.PositiveSmallIntegerField(default=0)), ("risk_score", models.DecimalField(decimal_places=2, default=0, max_digits=8)),
            ("low_risk", models.BooleanField(default=False)), ("auto_publish_eligible", models.BooleanField(default=False)),
            ("metrics", models.JSONField(blank=True, default=dict)), ("impact", models.JSONField(blank=True, default=dict)), ("error_message", models.TextField(blank=True)),
            ("scenario", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="recovery_plans", to="integrated_scheduling.integratedschedulescenario")),
            ("solver_run", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="recovery_plans", to="integrated_scheduling.schedulesolverrun")),
            ("trigger", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="recovery_plans", to="integrated_scheduling.reschedulingtrigger")),
        ], options={"ordering":["trigger","rank","risk_score","created_at"]}),
        migrations.AddConstraint(model_name="recoverypolicy", constraint=models.CheckConstraint(condition=models.Q(("candidate_count__gte",1)), name="ck_recovery_policy_candidates")),
        migrations.AddConstraint(model_name="recoverypolicy", constraint=models.CheckConstraint(condition=models.Q(("solver_time_limit_seconds__gte",1)), name="ck_recovery_policy_time")),
        migrations.AddConstraint(model_name="recoverypolicy", constraint=models.CheckConstraint(condition=models.Q(("max_risk_score__gte",0)), name="ck_recovery_policy_risk")),
        migrations.AddIndex(model_name="recoveryplan", index=models.Index(fields=["trigger","status","rank"], name="ix_recovery_plan_status")),
        migrations.AddConstraint(model_name="recoveryplan", constraint=models.UniqueConstraint(fields=("trigger","name"), name="uq_recovery_plan_name")),
    ]
