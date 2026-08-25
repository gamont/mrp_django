# Generated for MRP Django 0.2.1.
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):
    initial = True
    dependencies = [("common", "0001_initial"), ("masterdata", "0001_initial")]

    operations = [
        migrations.CreateModel(
            name="Forecast",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("period_start", models.DateField()),
                ("period_end", models.DateField()),
                ("quantity", models.DecimalField(decimal_places=4, max_digits=18)),
                ("version", models.PositiveIntegerField(default=1)),
                ("status", models.CharField(choices=[("DRAFT", "Rascunho"), ("APPROVED", "Aprovada"), ("CANCELLED", "Cancelada")], default="DRAFT", max_length=15)),
                ("item", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="forecasts", to="masterdata.item")),
                ("plant", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="forecasts", to="common.plant")),
            ],
            options={
                "ordering": ["period_start", "item__code"],
                "constraints": [
                    models.UniqueConstraint(fields=("plant", "item", "period_start", "version"), name="uq_forecast_version"),
                    models.CheckConstraint(condition=models.Q(("quantity__gt", 0)), name="ck_forecast_qty_pos"),
                    models.CheckConstraint(condition=models.Q(period_end__gte=models.F("period_start")), name="ck_forecast_dates"),
                ],
            },
        ),
        migrations.CreateModel(
            name="SalesOrder",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("number", models.CharField(max_length=40, unique=True)),
                ("customer_code", models.CharField(max_length=50)),
                ("customer_name", models.CharField(max_length=160)),
                ("order_date", models.DateField()),
                ("requested_date", models.DateField()),
                ("status", models.CharField(choices=[("DRAFT", "Rascunho"), ("CONFIRMED", "Confirmado"), ("PARTIAL", "Parcial"), ("COMPLETED", "Concluído"), ("CANCELLED", "Cancelado")], default="DRAFT", max_length=15)),
                ("plant", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name="sales_orders", to="common.plant")),
            ],
            options={
                "ordering": ["-order_date", "number"],
                "constraints": [models.CheckConstraint(condition=models.Q(requested_date__gte=models.F("order_date")), name="ck_salesorder_dates")],
            },
        ),
        migrations.CreateModel(
            name="MasterProductionSchedule",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("due_date", models.DateField()),
                ("quantity", models.DecimalField(decimal_places=4, max_digits=18)),
                ("status", models.CharField(choices=[("PLANNED", "Planejado"), ("FIRM", "Firme"), ("FROZEN", "Congelado"), ("CANCELLED", "Cancelado")], default="PLANNED", max_length=15)),
                ("source", models.CharField(blank=True, max_length=60)),
                ("notes", models.TextField(blank=True)),
                ("item", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="mps_entries", to="masterdata.item")),
                ("plant", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="mps_entries", to="common.plant")),
            ],
            options={
                "ordering": ["due_date", "item__code"],
                "indexes": [models.Index(fields=["plant", "due_date", "status"], name="ix_mps_plant_due_status")],
                "constraints": [
                    models.UniqueConstraint(fields=("plant", "item", "due_date", "source"), name="uq_mps_source"),
                    models.CheckConstraint(condition=models.Q(("quantity__gt", 0)), name="ck_mps_qty_pos"),
                ],
            },
        ),
        migrations.CreateModel(
            name="SalesOrderLine",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("line_number", models.PositiveIntegerField()),
                ("quantity", models.DecimalField(decimal_places=4, max_digits=18)),
                ("delivered_quantity", models.DecimalField(decimal_places=4, default=0, max_digits=18)),
                ("requested_date", models.DateField()),
                ("item", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name="sales_order_lines", to="masterdata.item")),
                ("sales_order", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="lines", to="demand.salesorder")),
            ],
            options={
                "ordering": ["sales_order", "line_number"],
                "constraints": [
                    models.UniqueConstraint(fields=("sales_order", "line_number"), name="uq_sales_order_line"),
                    models.CheckConstraint(condition=models.Q(("quantity__gt", 0)), name="ck_sol_qty_pos"),
                    models.CheckConstraint(condition=models.Q(("delivered_quantity__gte", 0)), name="ck_sol_deliv_nonneg"),
                    models.CheckConstraint(condition=models.Q(delivered_quantity__lte=models.F("quantity")), name="ck_sol_deliv_lte_qty"),
                ],
            },
        ),
    ]
