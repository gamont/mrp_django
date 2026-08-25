from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion

class Migration(migrations.Migration):
    dependencies = [("integrated_scheduling", "0014_commercial_pegging_recovery_073"), ("demand", "0001_initial"), migrations.swappable_dependency(settings.AUTH_USER_MODEL)]
    operations = [
        migrations.CreateModel(
            name="SalesOrderPromise",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("created_at", models.DateTimeField(auto_now_add=True)), ("updated_at", models.DateTimeField(auto_now=True)),
                ("source", models.CharField(choices=[("ATP_CTP","ATP/CTP"),("RECOVERY","Recovery"),("MANUAL","Manual")], max_length=16)),
                ("proposed_date", models.DateField()), ("previous_approved_date", models.DateField(blank=True, null=True)),
                ("quantity", models.DecimalField(decimal_places=4, max_digits=18)),
                ("status", models.CharField(choices=[("PENDING","Pendente"),("APPROVED","Aprovada"),("REJECTED","Rejeitada"),("SUPERSEDED","Substituída")], default="PENDING", max_length=16)),
                ("atp_result", models.JSONField(blank=True, default=dict)), ("ctp_result", models.JSONField(blank=True, default=dict)),
                ("rationale", models.TextField(blank=True)), ("decided_at", models.DateTimeField(blank=True, null=True)),
                ("decided_by", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="sales_promises_decided", to=settings.AUTH_USER_MODEL)),
                ("proposed_by", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="sales_promises_proposed", to=settings.AUTH_USER_MODEL)),
                ("recovery_plan", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="promise_proposals", to="integrated_scheduling.recoveryplan")),
                ("sales_order_line", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="promise_history", to="demand.salesorderline")),
                ("trigger", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="promise_proposals", to="integrated_scheduling.reschedulingtrigger")),
            ], options={"ordering":["-created_at"]}),
        migrations.AddIndex(model_name="salesorderpromise", index=models.Index(fields=["sales_order_line","status","created_at"], name="ix_solpromise_line_status")),
        migrations.AddIndex(model_name="salesorderpromise", index=models.Index(fields=["status","proposed_date"], name="ix_solpromise_status_date")),
        migrations.CreateModel(
            name="CommercialServiceCase",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("created_at", models.DateTimeField(auto_now_add=True)), ("updated_at", models.DateTimeField(auto_now=True)),
                ("status", models.CharField(choices=[("OPEN","Aberto"),("IN_REVIEW","Em análise"),("WAITING_CUSTOMER","Aguardando cliente"),("CLOSED","Fechado")], default="OPEN", max_length=20)),
                ("priority", models.CharField(choices=[("LOW","Baixa"),("MEDIUM","Média"),("HIGH","Alta"),("CRITICAL","Crítica")], default="MEDIUM", max_length=12)),
                ("reason", models.CharField(default="PROMISE_CHANGE", max_length=40)), ("notes", models.TextField(blank=True)),
                ("owner", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="commercial_service_cases", to=settings.AUTH_USER_MODEL)),
                ("promise", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="service_cases", to="integrated_scheduling.salesorderpromise")),
                ("recovery_plan", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="commercial_cases", to="integrated_scheduling.recoveryplan")),
                ("sales_order_line", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="commercial_cases", to="demand.salesorderline")),
                ("trigger", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="commercial_cases", to="integrated_scheduling.reschedulingtrigger")),
            ], options={"ordering":["-created_at"]}),
        migrations.AddIndex(model_name="commercialservicecase", index=models.Index(fields=["status","priority","created_at"], name="ix_comcase_status_priority")),
    ]
