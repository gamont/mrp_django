from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion
import django.utils.timezone


class Migration(migrations.Migration):
    dependencies = [
        ("costing", "0005_revaluation_traceable_cost_reconciliation"),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name="PeriodCloseRun",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("created_at", models.DateTimeField(auto_now_add=True)), ("updated_at", models.DateTimeField(auto_now=True)),
                ("status", models.CharField(choices=[("RUNNING","Executando"),("COMPLETED","Concluído"),("FAILED","Falhou"),("REVERSED","Estornado")], db_index=True, default="RUNNING", max_length=16)),
                ("started_at", models.DateTimeField(default=django.utils.timezone.now)), ("finished_at", models.DateTimeField(blank=True, null=True)),
                ("inventory_value", models.DecimalField(decimal_places=4, default=0, max_digits=22)), ("wip_value", models.DecimalField(decimal_places=4, default=0, max_digits=22)),
                ("variance_value", models.DecimalField(decimal_places=4, default=0, max_digits=22)), ("ledger_debits", models.DecimalField(decimal_places=4, default=0, max_digits=22)),
                ("ledger_credits", models.DecimalField(decimal_places=4, default=0, max_digits=22)), ("reconciliation_quantity_variance", models.DecimalField(decimal_places=4, default=0, max_digits=22)),
                ("reconciliation_value_variance", models.DecimalField(decimal_places=4, default=0, max_digits=22)), ("strict_reconciliation", models.BooleanField(default=False)),
                ("error_message", models.TextField(blank=True)),
                ("executed_by", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="cost_period_close_runs", to=settings.AUTH_USER_MODEL)),
                ("period", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name="close_runs", to="costing.accountingperiod")),
            ], options={"ordering":["-started_at"]},
        ),
        migrations.CreateModel(
            name="PeriodReopenRequest",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("created_at", models.DateTimeField(auto_now_add=True)), ("updated_at", models.DateTimeField(auto_now=True)),
                ("status", models.CharField(choices=[("REQUESTED","Solicitada"),("APPROVED","Aprovada"),("REJECTED","Rejeitada"),("APPLIED","Aplicada"),("CANCELLED","Cancelada")], db_index=True, default="REQUESTED", max_length=16)),
                ("reason", models.TextField()), ("requested_at", models.DateTimeField(default=django.utils.timezone.now)),
                ("decided_at", models.DateTimeField(blank=True, null=True)), ("decision_notes", models.TextField(blank=True)), ("applied_at", models.DateTimeField(blank=True, null=True)),
                ("period", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name="reopen_requests", to="costing.accountingperiod")),
                ("requested_by", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="requested_cost_period_reopens", to=settings.AUTH_USER_MODEL)),
                ("decided_by", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="decided_cost_period_reopens", to=settings.AUTH_USER_MODEL)),
                ("applied_by", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="applied_cost_period_reopens", to=settings.AUTH_USER_MODEL)),
            ], options={"ordering":["-requested_at"]},
        ),
        migrations.CreateModel(
            name="CostLedgerReversal",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("created_at", models.DateTimeField(auto_now_add=True)), ("updated_at", models.DateTimeField(auto_now=True)),
                ("reason", models.CharField(max_length=240)), ("reversed_at", models.DateTimeField(default=django.utils.timezone.now)),
                ("original_entry", models.OneToOneField(on_delete=django.db.models.deletion.PROTECT, related_name="reversal_record", to="costing.costledgerentry")),
                ("reversal_entry", models.OneToOneField(on_delete=django.db.models.deletion.PROTECT, related_name="reverses_record", to="costing.costledgerentry")),
                ("reversed_by", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="cost_ledger_reversals", to=settings.AUTH_USER_MODEL)),
            ], options={"ordering":["-reversed_at"]},
        ),
        migrations.CreateModel(
            name="CostPeriodAudit",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("created_at", models.DateTimeField(auto_now_add=True)), ("updated_at", models.DateTimeField(auto_now=True)),
                ("action", models.CharField(choices=[("CLOSE_STARTED","Fechamento iniciado"),("CLOSE_COMPLETED","Fechamento concluído"),("CLOSE_FAILED","Falha no fechamento"),("REOPEN_REQUESTED","Reabertura solicitada"),("REOPEN_APPROVED","Reabertura aprovada"),("REOPEN_REJECTED","Reabertura rejeitada"),("REOPEN_APPLIED","Reabertura aplicada"),("LEDGER_REVERSED","Lançamento estornado")], db_index=True, max_length=32)),
                ("occurred_at", models.DateTimeField(db_index=True, default=django.utils.timezone.now)), ("reference_type", models.CharField(blank=True, max_length=40)),
                ("reference_id", models.CharField(blank=True, max_length=64)), ("payload", models.JSONField(blank=True, default=dict)),
                ("actor", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="cost_period_audit_entries", to=settings.AUTH_USER_MODEL)),
                ("period", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name="cost_audit_entries", to="costing.accountingperiod")),
            ], options={"ordering":["-occurred_at","-id"]},
        ),
        migrations.AddIndex(model_name="periodcloserun", index=models.Index(fields=["period","status","started_at"], name="ix_close_run_period_status")),
        migrations.AddIndex(model_name="periodreopenrequest", index=models.Index(fields=["period","status"], name="ix_reopen_period_status")),
        migrations.AddIndex(model_name="costperiodaudit", index=models.Index(fields=["period","action","occurred_at"], name="ix_costaudit_period_action")),
    ]
