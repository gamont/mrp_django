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
            name="PurchaseOrder",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("number", models.CharField(max_length=40, unique=True)),
                ("order_date", models.DateField()),
                ("expected_date", models.DateField()),
                ("status", models.CharField(choices=[("DRAFT", "Rascunho"), ("RELEASED", "Liberada"), ("PARTIAL", "Parcial"), ("COMPLETED", "Concluída"), ("CANCELLED", "Cancelada")], default="DRAFT", max_length=15)),
                ("planning_run_id", models.PositiveBigIntegerField(blank=True, null=True)),
                ("planned_order_id", models.PositiveBigIntegerField(blank=True, null=True)),
                ("plant", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name="purchase_orders", to="common.plant")),
                ("supplier", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name="purchase_orders", to="masterdata.supplier")),
            ],
            options={
                "ordering": ["expected_date", "number"],
                "indexes": [models.Index(fields=["plant", "status", "expected_date"], name="ix_po_plant_status_date")],
                "constraints": [models.CheckConstraint(condition=models.Q(expected_date__gte=models.F("order_date")), name="ck_po_dates")],
            },
        ),
        migrations.CreateModel(
            name="PurchaseOrderLine",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("line_number", models.PositiveIntegerField()),
                ("quantity", models.DecimalField(decimal_places=4, max_digits=18)),
                ("received_quantity", models.DecimalField(decimal_places=4, default=0, max_digits=18)),
                ("unit_price", models.DecimalField(decimal_places=4, default=0, max_digits=18)),
                ("expected_date", models.DateField()),
                ("item", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name="purchase_order_lines", to="masterdata.item")),
                ("purchase_order", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="lines", to="purchasing.purchaseorder")),
            ],
            options={
                "ordering": ["purchase_order", "line_number"],
                "constraints": [
                    models.UniqueConstraint(fields=("purchase_order", "line_number"), name="uq_purchase_order_line"),
                    models.CheckConstraint(condition=models.Q(("quantity__gt", 0)), name="ck_pol_qty_pos"),
                    models.CheckConstraint(condition=models.Q(("received_quantity__gte", 0)), name="ck_pol_received_nonneg"),
                    models.CheckConstraint(condition=models.Q(received_quantity__lte=models.F("quantity")), name="ck_pol_received_lte_qty"),
                    models.CheckConstraint(condition=models.Q(("unit_price__gte", 0)), name="ck_pol_price_nonneg"),
                ],
            },
        ),
        migrations.CreateModel(
            name="GoodsReceipt",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("receipt_number", models.CharField(max_length=40)),
                ("idempotency_key", models.CharField(max_length=160, unique=True)),
                ("received_at", models.DateTimeField()),
                ("quantity", models.DecimalField(decimal_places=4, max_digits=18)),
                ("lot_number", models.CharField(blank=True, max_length=60)),
                ("notes", models.TextField(blank=True)),
                ("destination_location", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name="purchase_receipts", to="inventory.location")),
                ("inventory_transaction", models.OneToOneField(blank=True, null=True, on_delete=django.db.models.deletion.PROTECT, related_name="goods_receipt", to="inventory.inventorytransaction")),
                ("purchase_order_line", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name="receipts", to="purchasing.purchaseorderline")),
            ],
            options={
                "ordering": ["-received_at"],
                "indexes": [models.Index(fields=["purchase_order_line", "received_at"], name="ix_receipt_line_time")],
                "constraints": [
                    models.UniqueConstraint(fields=("purchase_order_line", "receipt_number"), name="uq_receipt_line_number"),
                    models.CheckConstraint(condition=models.Q(("quantity__gt", 0)), name="ck_receipt_qty_pos"),
                ],
            },
        ),
    ]
