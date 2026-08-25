from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion

class Migration(migrations.Migration):
    initial = True
    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ("common", "0001_initial"),
        ("masterdata", "0001_initial"),
        ("shopfloor", "0003_oee_shift_targets_history"),
    ]
    operations = [
        migrations.CreateModel(name="IntegratedScheduleScenario", fields=[
            ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
            ("created_at", models.DateTimeField(auto_now_add=True)), ("updated_at", models.DateTimeField(auto_now=True)),
            ("name", models.CharField(max_length=160)), ("horizon_start", models.DateField()), ("horizon_end", models.DateField()),
            ("status", models.CharField(choices=[("DRAFT","Rascunho"),("RUNNING","Executando"),("COMPLETED","Concluído"),("APPLIED","Aplicado"),("FAILED","Falhou")], default="DRAFT", max_length=16)),
            ("include_planned_production", models.BooleanField(default=True)), ("include_maintenance", models.BooleanField(default=True)),
            ("parameters", models.JSONField(blank=True, default=dict)), ("baseline_summary", models.JSONField(blank=True, default=dict)), ("simulated_summary", models.JSONField(blank=True, default=dict)),
            ("applied_at", models.DateTimeField(blank=True, null=True)), ("error_message", models.TextField(blank=True)),
            ("plant", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name="integrated_schedule_scenarios", to="common.plant")),
            ("created_by", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="integrated_schedule_scenarios_created", to=settings.AUTH_USER_MODEL)),
            ("applied_by", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="integrated_schedule_scenarios_applied", to=settings.AUTH_USER_MODEL)),
        ], options={"ordering":["-created_at"]}),
        migrations.CreateModel(name="IntegratedScheduleBlock", fields=[
            ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")), ("created_at", models.DateTimeField(auto_now_add=True)), ("updated_at", models.DateTimeField(auto_now=True)),
            ("block_type", models.CharField(choices=[("PRODUCTION","Produção"),("MAINTENANCE","Manutenção"),("CAPACITY_LOSS","Perda de capacidade")], max_length=20)),
            ("source_type", models.CharField(max_length=40)), ("source_id", models.CharField(max_length=64)), ("source_number", models.CharField(blank=True,max_length=80)), ("description", models.CharField(blank=True,max_length=220)),
            ("original_start", models.DateTimeField()), ("original_end", models.DateTimeField()), ("simulated_start", models.DateTimeField()), ("simulated_end", models.DateTimeField()),
            ("required_hours", models.DecimalField(decimal_places=4, default=0, max_digits=12)), ("lost_capacity_hours", models.DecimalField(decimal_places=4, default=0, max_digits=12)), ("late_hours", models.DecimalField(decimal_places=4, default=0, max_digits=12)), ("details", models.JSONField(blank=True, default=dict)),
            ("machine", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="integrated_schedule_blocks", to="shopfloor.machine")),
            ("scenario", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="blocks", to="integrated_scheduling.integratedschedulescenario")),
            ("work_center", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name="integrated_schedule_blocks", to="masterdata.workcenter")),
        ], options={"ordering":["simulated_start","work_center__code","block_type"]}),
        migrations.CreateModel(name="IntegratedScheduleConflict", fields=[
            ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")), ("created_at", models.DateTimeField(auto_now_add=True)), ("updated_at", models.DateTimeField(auto_now=True)),
            ("conflict_type", models.CharField(choices=[("MAINT_PROD","Manutenção × produção"),("CAPACITY","Sobrecarga de capacidade"),("DUE_DATE","Risco de atraso"),("MACHINE","Conflito de máquina")], max_length=20)),
            ("severity", models.CharField(choices=[("INFO","Informação"),("WARNING","Atenção"),("CRITICAL","Crítico")], default="WARNING", max_length=10)), ("overlap_hours", models.DecimalField(decimal_places=4, default=0, max_digits=12)), ("message", models.TextField()), ("details", models.JSONField(blank=True, default=dict)),
            ("maintenance_block", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.CASCADE, related_name="maintenance_conflicts", to="integrated_scheduling.integratedscheduleblock")),
            ("production_block", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.CASCADE, related_name="production_conflicts", to="integrated_scheduling.integratedscheduleblock")),
            ("scenario", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="conflicts", to="integrated_scheduling.integratedschedulescenario")),
            ("work_center", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.PROTECT, related_name="integrated_schedule_conflicts", to="masterdata.workcenter")),
        ], options={"ordering":["severity","work_center__code","created_at"]}),
        migrations.AddConstraint(model_name="integratedschedulescenario", constraint=models.CheckConstraint(condition=models.Q(("horizon_end__gte", models.F("horizon_start"))), name="ck_intsched_horizon")),
        migrations.AddIndex(model_name="integratedschedulescenario", index=models.Index(fields=["plant","status","horizon_start"], name="ix_intsched_plant_status")),
        migrations.AddConstraint(model_name="integratedscheduleblock", constraint=models.CheckConstraint(condition=models.Q(("original_end__gte", models.F("original_start"))), name="ck_intblock_original")),
        migrations.AddConstraint(model_name="integratedscheduleblock", constraint=models.CheckConstraint(condition=models.Q(("simulated_end__gte", models.F("simulated_start"))), name="ck_intblock_simulated")),
        migrations.AddConstraint(model_name="integratedscheduleblock", constraint=models.CheckConstraint(condition=models.Q(("required_hours__gte", 0)), name="ck_intblock_req_nonneg")),
        migrations.AddConstraint(model_name="integratedscheduleblock", constraint=models.CheckConstraint(condition=models.Q(("lost_capacity_hours__gte", 0)), name="ck_intblock_loss_nonneg")),
        migrations.AddConstraint(model_name="integratedscheduleblock", constraint=models.CheckConstraint(condition=models.Q(("late_hours__gte", 0)), name="ck_intblock_late_nonneg")),
        migrations.AddIndex(model_name="integratedscheduleblock", index=models.Index(fields=["scenario","work_center","simulated_start"], name="ix_intblock_center_time")),
        migrations.AddIndex(model_name="integratedscheduleblock", index=models.Index(fields=["scenario","source_type","source_id"], name="ix_intblock_source")),
        migrations.AddIndex(model_name="integratedscheduleconflict", index=models.Index(fields=["scenario","conflict_type","severity"], name="ix_intconf_type_sev")),
    ]
