# Generated for MRP Django 0.2.1.
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):
    initial = True
    dependencies = [
        ("common", "0001_initial"),
        ("masterdata", "0001_initial"),
        ("inventory", "0001_initial"),
    ]

    operations = [
        migrations.CreateModel(
            name="WorkOrder",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("number", models.CharField(max_length=40, unique=True)),
                ("quantity", models.DecimalField(decimal_places=4, max_digits=18)),
                ("completed_quantity", models.DecimalField(decimal_places=4, default=0, max_digits=18)),
                ("release_date", models.DateField()),
                ("due_date", models.DateField()),
                ("status", models.CharField(choices=[("PLANNED", "Planejada"), ("RELEASED", "Liberada"), ("IN_PROGRESS", "Em andamento"), ("COMPLETED", "Concluída"), ("CLOSED", "Encerrada"), ("CANCELLED", "Cancelada")], default="PLANNED", max_length=20)),
                ("planning_run_id", models.PositiveBigIntegerField(blank=True, null=True)),
                ("planned_order_id", models.PositiveBigIntegerField(blank=True, null=True)),
                ("item", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name="work_orders", to="masterdata.item")),
                ("plant", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name="work_orders", to="common.plant")),
                ("routing", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="work_orders", to="masterdata.routing")),
            ],
            options={
                "ordering": ["release_date", "number"],
                "indexes": [models.Index(fields=["plant", "status", "due_date"], name="ix_wo_plant_status_due")],
                "constraints": [
                    models.CheckConstraint(condition=models.Q(("quantity__gt", 0)), name="ck_wo_qty_pos"),
                    models.CheckConstraint(condition=models.Q(("completed_quantity__gte", 0)), name="ck_wo_completed_nonneg"),
                    models.CheckConstraint(condition=models.Q(completed_quantity__lte=models.F("quantity")), name="ck_wo_completed_lte_qty"),
                    models.CheckConstraint(condition=models.Q(due_date__gte=models.F("release_date")), name="ck_wo_dates"),
                ],
            },
        ),
        migrations.CreateModel(
            name="WorkOrderMaterial",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("required_quantity", models.DecimalField(decimal_places=4, max_digits=18)),
                ("issued_quantity", models.DecimalField(decimal_places=4, default=0, max_digits=18)),
                ("required_date", models.DateField()),
                ("bom_line", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, to="masterdata.bomline")),
                ("item", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name="work_order_materials", to="masterdata.item")),
                ("work_order", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="materials", to="production.workorder")),
            ],
            options={
                "ordering": ["work_order", "item__code"],
                "indexes": [models.Index(fields=["work_order", "required_date"], name="ix_womaterial_order_date")],
                "constraints": [
                    models.CheckConstraint(condition=models.Q(("required_quantity__gt", 0)), name="ck_womaterial_req_pos"),
                    models.CheckConstraint(condition=models.Q(("issued_quantity__gte", 0)), name="ck_womaterial_issue_nonneg"),
                    models.CheckConstraint(condition=models.Q(issued_quantity__lte=models.F("required_quantity")), name="ck_womaterial_issue_lte"),
                ],
            },
        ),
        migrations.CreateModel(
            name="WorkOrderOperation",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("sequence", models.PositiveIntegerField()),
                ("description", models.CharField(max_length=200)),
                ("status", models.CharField(choices=[("PENDING", "Pendente"), ("READY", "Pronta"), ("SETUP", "Setup"), ("RUNNING", "Executando"), ("INTERRUPTED", "Interrompida"), ("COMPLETED", "Concluída")], default="PENDING", max_length=20)),
                ("planned_start", models.DateTimeField(blank=True, null=True)),
                ("planned_end", models.DateTimeField(blank=True, null=True)),
                ("actual_start", models.DateTimeField(blank=True, null=True)),
                ("actual_end", models.DateTimeField(blank=True, null=True)),
                ("setup_hours", models.DecimalField(decimal_places=4, default=0, max_digits=12)),
                ("run_hours", models.DecimalField(decimal_places=4, default=0, max_digits=12)),
                ("work_center", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name="work_order_operations", to="masterdata.workcenter")),
                ("work_order", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="operations", to="production.workorder")),
            ],
            options={
                "ordering": ["work_order", "sequence"],
                "constraints": [
                    models.UniqueConstraint(fields=("work_order", "sequence"), name="uq_work_order_operation"),
                    models.CheckConstraint(condition=models.Q(("setup_hours__gte", 0)), name="ck_woop_setup_nonneg"),
                    models.CheckConstraint(condition=models.Q(("run_hours__gte", 0)), name="ck_woop_run_nonneg"),
                ],
            },
        ),
        migrations.CreateModel(
            name="ProductionReport",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("reported_at", models.DateTimeField()),
                ("good_quantity", models.DecimalField(decimal_places=4, default=0, max_digits=18)),
                ("scrap_quantity", models.DecimalField(decimal_places=4, default=0, max_digits=18)),
                ("labor_hours", models.DecimalField(decimal_places=4, default=0, max_digits=12)),
                ("machine_hours", models.DecimalField(decimal_places=4, default=0, max_digits=12)),
                ("notes", models.TextField(blank=True)),
                ("operation", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.PROTECT, related_name="reports", to="production.workorderoperation")),
                ("work_order", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name="reports", to="production.workorder")),
            ],
            options={
                "ordering": ["-reported_at"],
                "indexes": [models.Index(fields=["work_order", "reported_at"], name="ix_prodreport_order_time")],
                "constraints": [
                    models.CheckConstraint(condition=models.Q(("good_quantity__gte", 0)), name="ck_prodreport_good_nonneg"),
                    models.CheckConstraint(condition=models.Q(("scrap_quantity__gte", 0)), name="ck_prodreport_scrap_nonneg"),
                    models.CheckConstraint(condition=models.Q(("labor_hours__gte", 0)), name="ck_prodreport_labor_nonneg"),
                    models.CheckConstraint(condition=models.Q(("machine_hours__gte", 0)), name="ck_prodreport_machine_nonneg"),
                ],
            },
        ),
        migrations.CreateModel(
            name="WorkOrderCompletion",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("idempotency_key", models.CharField(max_length=160, unique=True)),
                ("good_quantity", models.DecimalField(decimal_places=4, max_digits=18)),
                ("scrap_quantity", models.DecimalField(decimal_places=4, default=0, max_digits=18)),
                ("reported_at", models.DateTimeField()),
                ("backflush", models.BooleanField(default=True)),
                ("closed_order", models.BooleanField(default=False)),
                ("notes", models.TextField(blank=True)),
                ("destination_location", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name="production_completions", to="inventory.location")),
                ("receipt_transaction", models.OneToOneField(on_delete=django.db.models.deletion.PROTECT, related_name="work_order_completion", to="inventory.inventorytransaction")),
                ("work_order", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name="completions", to="production.workorder")),
            ],
            options={
                "ordering": ["-reported_at", "-id"],
                "indexes": [models.Index(fields=["work_order", "reported_at"], name="ix_wocompletion_order_time")],
                "constraints": [
                    models.CheckConstraint(condition=models.Q(("good_quantity__gt", 0)), name="ck_wocompletion_good_pos"),
                    models.CheckConstraint(condition=models.Q(("scrap_quantity__gte", 0)), name="ck_wocompletion_scrap_nonneg"),
                ],
            },
        ),
    ]
