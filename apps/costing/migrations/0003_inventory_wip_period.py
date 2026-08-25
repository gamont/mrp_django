from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):
    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ("costing", "0002_work_order_costs_and_variances"),
        ("inventory", "0001_initial"),
        ("production", "0001_initial"),
    ]

    operations = [
        migrations.CreateModel(
            name="AccountingPeriod",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("code", models.CharField(max_length=20)),
                ("start_date", models.DateField()),
                ("end_date", models.DateField()),
                ("status", models.CharField(choices=[("OPEN", "Aberto"), ("CLOSING", "Em fechamento"), ("CLOSED", "Fechado")], db_index=True, default="OPEN", max_length=12)),
                ("closed_at", models.DateTimeField(blank=True, null=True)),
                ("closed_by", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="closed_accounting_periods", to=settings.AUTH_USER_MODEL)),
                ("cost_version", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.PROTECT, related_name="accounting_periods", to="costing.costversion")),
                ("plant", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name="accounting_periods", to="common.plant")),
            ],
            options={"ordering": ["-start_date", "plant__code"]},
        ),
        migrations.CreateModel(
            name="InventoryValuationSnapshot",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("valuation_method", models.CharField(choices=[("STANDARD", "Custo padrão"), ("MOVING_AVERAGE", "Custo médio móvel"), ("ACTUAL", "Custo real")], default="STANDARD", max_length=20)),
                ("as_of", models.DateTimeField()),
                ("total_quantity", models.DecimalField(decimal_places=4, default=0, max_digits=22)),
                ("total_value", models.DecimalField(decimal_places=4, default=0, max_digits=22)),
                ("cost_version", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name="inventory_snapshots", to="costing.costversion")),
                ("period", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="inventory_snapshots", to="costing.accountingperiod")),
            ],
            options={"ordering": ["-as_of"]},
        ),
        migrations.CreateModel(
            name="WIPSnapshot",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("as_of", models.DateTimeField()),
                ("total_value", models.DecimalField(decimal_places=4, default=0, max_digits=22)),
                ("cost_version", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name="wip_snapshots", to="costing.costversion")),
                ("period", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="wip_snapshots", to="costing.accountingperiod")),
            ],
            options={"ordering": ["-as_of"]},
        ),
        migrations.CreateModel(
            name="InventoryValuationLine",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("quantity", models.DecimalField(decimal_places=4, max_digits=18)),
                ("unit_cost", models.DecimalField(decimal_places=6, default=0, max_digits=18)),
                ("total_value", models.DecimalField(decimal_places=4, default=0, max_digits=22)),
                ("item", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name="inventory_valuation_lines", to="masterdata.item")),
                ("location", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name="valuation_lines", to="inventory.location")),
                ("snapshot", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="lines", to="costing.inventoryvaluationsnapshot")),
            ],
            options={"ordering": ["item__code", "location__code"]},
        ),
        migrations.CreateModel(
            name="WIPLine",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("material_cost", models.DecimalField(decimal_places=4, default=0, max_digits=18)),
                ("setup_cost", models.DecimalField(decimal_places=4, default=0, max_digits=18)),
                ("labor_cost", models.DecimalField(decimal_places=4, default=0, max_digits=18)),
                ("machine_cost", models.DecimalField(decimal_places=4, default=0, max_digits=18)),
                ("overhead_cost", models.DecimalField(decimal_places=4, default=0, max_digits=18)),
                ("subcontract_cost", models.DecimalField(decimal_places=4, default=0, max_digits=18)),
                ("scrap_cost", models.DecimalField(decimal_places=4, default=0, max_digits=18)),
                ("completed_value", models.DecimalField(decimal_places=4, default=0, max_digits=18)),
                ("wip_value", models.DecimalField(decimal_places=4, default=0, max_digits=18)),
                ("snapshot", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="lines", to="costing.wipsnapshot")),
                ("work_order", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name="wip_lines", to="production.workorder")),
            ],
            options={"ordering": ["work_order__number"]},
        ),
        migrations.AddConstraint(model_name="accountingperiod", constraint=models.UniqueConstraint(fields=("plant", "code"), name="uq_cost_period_plant_code")),
        migrations.AddConstraint(model_name="accountingperiod", constraint=models.CheckConstraint(condition=models.Q(("end_date__gte", models.F("start_date"))), name="ck_cost_period_dates")),
        migrations.AddConstraint(model_name="inventoryvaluationsnapshot", constraint=models.UniqueConstraint(fields=("period", "valuation_method"), name="uq_invvaluation_period_method")),
        migrations.AddConstraint(model_name="inventoryvaluationline", constraint=models.UniqueConstraint(fields=("snapshot", "item", "location"), name="uq_invvaluation_line")),
        migrations.AddConstraint(model_name="wipsnapshot", constraint=models.UniqueConstraint(fields=("period",), name="uq_wip_period")),
        migrations.AddConstraint(model_name="wipline", constraint=models.UniqueConstraint(fields=("snapshot", "work_order"), name="uq_wip_line")),
    ]
