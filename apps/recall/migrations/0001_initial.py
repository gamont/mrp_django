# Generated manually for MRP 0.3.4
from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):
    initial = True
    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ("common", "0001_initial"),
        ("masterdata", "0001_initial"),
        ("quality", "0001_initial"),
        ("traceability", "0001_initial"),
    ]
    operations = [
        migrations.CreateModel(
            name="RecallCase",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("created_at", models.DateTimeField(auto_now_add=True)), ("updated_at", models.DateTimeField(auto_now=True)),
                ("number", models.CharField(max_length=30, unique=True)),
                ("classification", models.CharField(choices=[("INTERNAL", "Contenção interna"), ("SUPPLIER", "Problema de fornecedor"), ("MARKET", "Recall de mercado"), ("REGULATORY", "Recall regulatório")], max_length=20)),
                ("title", models.CharField(max_length=200)), ("description", models.TextField()), ("reason", models.TextField()),
                ("status", models.CharField(choices=[("DRAFT", "Rascunho"), ("INVESTIGATING", "Em investigação"), ("APPROVED", "Aprovado"), ("EXECUTING", "Em execução"), ("COMPLETED", "Concluído"), ("CANCELLED", "Cancelado")], default="DRAFT", max_length=20)),
                ("approved_at", models.DateTimeField(blank=True, null=True)), ("completed_at", models.DateTimeField(blank=True, null=True)), ("notes", models.TextField(blank=True)),
                ("approved_by", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="approved_recall_cases", to=settings.AUTH_USER_MODEL)),
                ("nonconformance", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.PROTECT, related_name="recall_cases", to="quality.nonconformance")),
                ("opened_by", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="opened_recall_cases", to=settings.AUTH_USER_MODEL)),
                ("plant", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name="recall_cases", to="common.plant")),
                ("supplier", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.PROTECT, related_name="recall_cases", to="masterdata.supplier")),
            ],
            options={"ordering": ["-created_at", "-id"], "permissions": [("approve_recallcase", "Pode aprovar recall"), ("execute_recallcase", "Pode executar recall")]},
        ),
        migrations.CreateModel(
            name="RecallCriterion",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")), ("created_at", models.DateTimeField(auto_now_add=True)), ("updated_at", models.DateTimeField(auto_now=True)),
                ("criterion_type", models.CharField(choices=[("LOT", "Lote"), ("SERIAL", "Número de série"), ("ITEM", "Item"), ("SUPPLIER", "Fornecedor"), ("PRODUCTION_PERIOD", "Período de produção"), ("SOURCE_REFERENCE", "Referência de origem")], max_length=25)),
                ("date_from", models.DateTimeField(blank=True, null=True)), ("date_to", models.DateTimeField(blank=True, null=True)), ("reference_type", models.CharField(blank=True, max_length=40)), ("reference_id", models.CharField(blank=True, max_length=64)), ("notes", models.TextField(blank=True)),
                ("item", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.PROTECT, related_name="recall_criteria", to="masterdata.item")),
                ("lot", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.PROTECT, related_name="recall_criteria", to="traceability.inventorylot")),
                ("recall_case", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="criteria", to="recall.recallcase")),
                ("serial", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.PROTECT, related_name="recall_criteria", to="traceability.serialnumber")),
                ("supplier", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.PROTECT, related_name="recall_criteria", to="masterdata.supplier")),
            ], options={"ordering": ["recall_case", "id"]},
        ),
        migrations.CreateModel(
            name="RecallAffectedUnit",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")), ("created_at", models.DateTimeField(auto_now_add=True)), ("updated_at", models.DateTimeField(auto_now=True)),
                ("source", models.CharField(choices=[("DIRECT", "Critério direto"), ("LOT_SERIAL", "Série vinculada ao lote"), ("GENEALOGY_UP", "Where-used"), ("GENEALOGY_DOWN", "Componente"), ("REFERENCE", "Referência transacional")], max_length=20)),
                ("depth", models.PositiveIntegerField(default=0)), ("disposition", models.CharField(choices=[("PENDING", "Pendente"), ("BLOCKED", "Bloqueado"), ("RETURNED", "Retornado"), ("REWORKED", "Retrabalhado"), ("SCRAPPED", "Refugado"), ("CLEARED", "Liberado")], default="PENDING", max_length=20)),
                ("blocked_at", models.DateTimeField(blank=True, null=True)), ("disposition_at", models.DateTimeField(blank=True, null=True)), ("notes", models.TextField(blank=True)),
                ("item", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name="recall_affected_units", to="masterdata.item")),
                ("lot", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.PROTECT, related_name="recall_affected_units", to="traceability.inventorylot")),
                ("recall_case", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="affected_units", to="recall.recallcase")),
                ("serial", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.PROTECT, related_name="recall_affected_units", to="traceability.serialnumber")),
            ], options={"ordering": ["recall_case", "depth", "item__code", "id"]},
        ),
        migrations.CreateModel(
            name="RecallAction",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")), ("created_at", models.DateTimeField(auto_now_add=True)), ("updated_at", models.DateTimeField(auto_now=True)),
                ("action_type", models.CharField(choices=[("BLOCK", "Bloquear"), ("NOTIFY", "Notificar"), ("RETURN", "Retornar"), ("REWORK", "Retrabalhar"), ("SCRAP", "Refugar"), ("RELEASE", "Liberar"), ("VERIFY", "Verificar")], max_length=15)),
                ("status", models.CharField(choices=[("OPEN", "Aberta"), ("IN_PROGRESS", "Em andamento"), ("DONE", "Concluída"), ("CANCELLED", "Cancelada")], default="OPEN", max_length=15)),
                ("due_date", models.DateField(blank=True, null=True)), ("completed_at", models.DateTimeField(blank=True, null=True)), ("result", models.TextField(blank=True)),
                ("affected_unit", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.CASCADE, related_name="actions", to="recall.recallaffectedunit")),
                ("owner", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="recall_actions", to=settings.AUTH_USER_MODEL)),
                ("recall_case", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="actions", to="recall.recallcase")),
            ], options={"ordering": ["status", "due_date", "id"]},
        ),
        migrations.AddConstraint(model_name="recallaffectedunit", constraint=models.UniqueConstraint(condition=models.Q(("serial__isnull", False)), fields=("recall_case", "serial"), name="uq_recall_affected_serial")),
        migrations.AddConstraint(model_name="recallaffectedunit", constraint=models.UniqueConstraint(condition=models.Q(("lot__isnull", False), ("serial__isnull", True)), fields=("recall_case", "lot"), name="uq_recall_affected_lot")),
        migrations.AddConstraint(model_name="recallaffectedunit", constraint=models.CheckConstraint(condition=models.Q(("serial__isnull", False), ("lot__isnull", False), _connector="OR"), name="ck_recall_affected_target")),
        migrations.AddIndex(model_name="recallcase", index=models.Index(fields=["plant", "status", "classification"], name="ix_recall_status_class")),
        migrations.AddIndex(model_name="recallcase", index=models.Index(fields=["supplier", "status"], name="ix_recall_supplier_status")),
        migrations.AddIndex(model_name="recallcriterion", index=models.Index(fields=["recall_case", "criterion_type"], name="ix_recallcriterion_case_type")),
        migrations.AddIndex(model_name="recallcriterion", index=models.Index(fields=["reference_type", "reference_id"], name="ix_recallcriterion_ref")),
        migrations.AddIndex(model_name="recallaffectedunit", index=models.Index(fields=["recall_case", "disposition"], name="ix_recallaffected_disposition")),
        migrations.AddIndex(model_name="recallaffectedunit", index=models.Index(fields=["item", "lot", "serial"], name="ix_recallaffected_target")),
        migrations.AddIndex(model_name="recallaction", index=models.Index(fields=["recall_case", "status", "action_type"], name="ix_recallaction_case_status")),
        migrations.AddIndex(model_name="recallaction", index=models.Index(fields=["owner", "status", "due_date"], name="ix_recallaction_owner_due")),
    ]
