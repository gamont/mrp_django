from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion

class Migration(migrations.Migration):
    dependencies = [("integrated_scheduling", "0013_recovery_control_center_072"), ("planning", "0002_demand_pegging_allocation_073"), ("demand", "0001_initial"), migrations.swappable_dependency(settings.AUTH_USER_MODEL)]
    operations = [
        migrations.CreateModel(
            name="RecoveryCommercialImpact",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")), ("created_at", models.DateTimeField(auto_now_add=True)), ("updated_at", models.DateTimeField(auto_now=True)),
                ("pegged_quantity", models.DecimalField(decimal_places=4, max_digits=18)), ("requested_date", models.DateField()), ("current_promise_date", models.DateField(blank=True, null=True)), ("recovered_promise_date", models.DateField(blank=True, null=True)), ("promise_delta_days", models.IntegerField(default=0)),
                ("promise_status", models.CharField(choices=[("ON_TIME","No prazo"),("AT_RISK","Em risco"),("LATE","Atrasado"),("RECOVERED","Recuperado"),("UNKNOWN","Indeterminado")], default="UNKNOWN", max_length=16)),
                ("pegging_method", models.CharField(default="EXACT_MRP_SOURCE", max_length=32)), ("details", models.JSONField(blank=True, default=dict)),
                ("recovery_plan", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.CASCADE, related_name="commercial_impacts", to="integrated_scheduling.recoveryplan")),
                ("sales_order_line", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="recovery_impacts", to="demand.salesorderline")),
                ("trigger", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="commercial_impacts", to="integrated_scheduling.reschedulingtrigger")),
            ], options={"ordering":["sales_order_line__sales_order__number","sales_order_line__line_number"]}),
        migrations.AddConstraint(model_name="recoverycommercialimpact", constraint=models.UniqueConstraint(fields=("trigger","recovery_plan","sales_order_line"), name="uq_recovery_commercial_impact")),
        migrations.AddIndex(model_name="recoverycommercialimpact", index=models.Index(fields=["trigger","promise_status"], name="ix_reccomm_trigger_status")),
        migrations.CreateModel(
            name="CommercialPromiseAlert",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")), ("created_at", models.DateTimeField(auto_now_add=True)), ("updated_at", models.DateTimeField(auto_now=True)),
                ("severity", models.CharField(choices=[("LOW","Baixa"),("MEDIUM","Média"),("HIGH","Alta"),("CRITICAL","Crítica")], default="MEDIUM", max_length=12)),
                ("status", models.CharField(choices=[("OPEN","Aberto"),("ACKNOWLEDGED","Reconhecido"),("RESOLVED","Resolvido")], default="OPEN", max_length=16)),
                ("message", models.TextField()), ("acknowledged_at", models.DateTimeField(blank=True, null=True)), ("details", models.JSONField(blank=True, default=dict)),
                ("acknowledged_by", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="acknowledged_commercial_alerts", to=settings.AUTH_USER_MODEL)),
                ("recovery_plan", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.CASCADE, related_name="commercial_alerts", to="integrated_scheduling.recoveryplan")),
                ("sales_order_line", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="promise_alerts", to="demand.salesorderline")),
                ("trigger", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="commercial_alerts", to="integrated_scheduling.reschedulingtrigger")),
            ], options={"ordering":["-created_at"]}),
        migrations.AddIndex(model_name="commercialpromisealert", index=models.Index(fields=["status","severity","created_at"], name="ix_commalert_status_sev")),
    ]
