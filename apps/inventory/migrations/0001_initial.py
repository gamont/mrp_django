# Generated for MRP Django 0.2.1.
from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):
    initial = True

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ("common", "0001_initial"),
        ("masterdata", "0001_initial"),
    ]

    operations = [
        migrations.CreateModel(
            name="Warehouse",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("code", models.CharField(max_length=30)),
                ("name", models.CharField(max_length=120)),
                ("is_active", models.BooleanField(default=True)),
                ("plant", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="warehouses", to="common.plant")),
            ],
            options={
                "ordering": ["plant__code", "code"],
                "constraints": [models.UniqueConstraint(fields=("plant", "code"), name="uq_warehouse_plant_code")],
            },
        ),
        migrations.CreateModel(
            name="Location",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("code", models.CharField(max_length=40)),
                ("description", models.CharField(blank=True, max_length=120)),
                ("is_active", models.BooleanField(default=True)),
                ("warehouse", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="locations", to="inventory.warehouse")),
            ],
            options={
                "ordering": ["warehouse__code", "code"],
                "constraints": [models.UniqueConstraint(fields=("warehouse", "code"), name="uq_location_warehouse_code")],
            },
        ),
        migrations.CreateModel(
            name="StockBalance",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("on_hand", models.DecimalField(decimal_places=4, default=0, max_digits=18)),
                ("allocated", models.DecimalField(decimal_places=4, default=0, max_digits=18)),
                ("item", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="stock_balances", to="masterdata.item")),
                ("location", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="stock_balances", to="inventory.location")),
            ],
            options={
                "ordering": ["item__code", "location__code"],
                "constraints": [
                    models.UniqueConstraint(fields=("item", "location"), name="uq_stock_item_location"),
                    models.CheckConstraint(condition=models.Q(("on_hand__gte", 0)), name="ck_stock_onhand_nonneg"),
                    models.CheckConstraint(condition=models.Q(("allocated__gte", 0)), name="ck_stock_alloc_nonneg"),
                ],
            },
        ),
        migrations.CreateModel(
            name="InventoryTransaction",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("transaction_type", models.CharField(choices=[("RECEIPT", "Recebimento"), ("ISSUE", "Baixa"), ("TRANSFER", "Transferência"), ("ADJUSTMENT", "Ajuste"), ("PURCHASE_RECEIPT", "Recebimento de compra"), ("PRODUCTION_RECEIPT", "Entrada de produção"), ("PRODUCTION_ISSUE", "Consumo de produção"), ("RETURN", "Devolução")], max_length=30)),
                ("quantity", models.DecimalField(decimal_places=4, max_digits=18)),
                ("reference_type", models.CharField(blank=True, max_length=40)),
                ("reference_id", models.CharField(blank=True, max_length=64)),
                ("posted_at", models.DateTimeField(auto_now_add=True)),
                ("notes", models.TextField(blank=True)),
                ("idempotency_key", models.CharField(blank=True, max_length=160, null=True, unique=True)),
                ("from_location", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.PROTECT, related_name="outgoing_transactions", to="inventory.location")),
                ("item", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name="inventory_transactions", to="masterdata.item")),
                ("posted_by", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, to=settings.AUTH_USER_MODEL)),
                ("to_location", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.PROTECT, related_name="incoming_transactions", to="inventory.location")),
            ],
            options={
                "ordering": ["-posted_at", "-id"],
                "indexes": [
                    models.Index(fields=["item", "posted_at"], name="ix_invtx_item_posted"),
                    models.Index(fields=["reference_type", "reference_id"], name="ix_invtx_reference"),
                ],
                "constraints": [
                    models.CheckConstraint(condition=~models.Q(("quantity", 0)), name="ck_invtx_quantity_nonzero"),
                    models.CheckConstraint(condition=models.Q(("transaction_type", "ADJUSTMENT")) | models.Q(("quantity__gt", 0)), name="ck_invtx_positive_normal"),
                ],
            },
        ),
        migrations.CreateModel(
            name="Reservation",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("quantity", models.DecimalField(decimal_places=4, max_digits=18)),
                ("requested_quantity", models.DecimalField(decimal_places=4, default=0, max_digits=18)),
                ("consumed_quantity", models.DecimalField(decimal_places=4, default=0, max_digits=18)),
                ("consumed_requested_quantity", models.DecimalField(decimal_places=4, default=0, max_digits=18)),
                ("demand_type", models.CharField(max_length=40)),
                ("demand_id", models.CharField(max_length=64)),
                ("required_date", models.DateField()),
                ("status", models.CharField(choices=[("OPEN", "Aberta"), ("CONSUMED", "Consumida"), ("CANCELLED", "Cancelada")], default="OPEN", max_length=15)),
                ("item", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="reservations", to="masterdata.item")),
                ("location", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name="reservations", to="inventory.location")),
                ("requested_item", models.ForeignKey(blank=True, help_text="Item originalmente solicitado quando a reserva usa substituto.", null=True, on_delete=django.db.models.deletion.PROTECT, related_name="substitution_reservations", to="masterdata.item")),
            ],
            options={
                "ordering": ["required_date", "item__code"],
                "indexes": [
                    models.Index(fields=["demand_type", "demand_id", "status"], name="ix_reservation_demand"),
                    models.Index(fields=["item", "status", "required_date"], name="ix_reservation_item_date"),
                ],
                "constraints": [
                    models.CheckConstraint(condition=models.Q(("quantity__gt", 0)), name="ck_reservation_qty_pos"),
                    models.CheckConstraint(condition=models.Q(("requested_quantity__gt", 0)), name="ck_reservation_req_pos"),
                    models.CheckConstraint(condition=models.Q(("consumed_quantity__gte", 0)), name="ck_reservation_cons_nonneg"),
                    models.CheckConstraint(condition=models.Q(consumed_quantity__lte=models.F("quantity")), name="ck_reservation_cons_lte_qty"),
                    models.CheckConstraint(condition=models.Q(("consumed_requested_quantity__gte", 0)), name="ck_reservation_reqcons_nonneg"),
                    models.CheckConstraint(condition=models.Q(consumed_requested_quantity__lte=models.F("requested_quantity")), name="ck_reservation_reqcons_lte"),
                ],
            },
        ),
    ]
