from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):
    initial = True
    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ("common", "0001_initial"),
        ("inventory", "0001_initial"),
        ("masterdata", "0001_initial"),
    ]
    operations = [
        migrations.CreateModel(
            name="InventoryLot",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("lot_number", models.CharField(max_length=80)),
                ("manufacture_date", models.DateField(blank=True, null=True)),
                ("expiration_date", models.DateField(blank=True, null=True)),
                ("received_at", models.DateTimeField(blank=True, null=True)),
                ("source_type", models.CharField(blank=True, max_length=40)),
                ("source_id", models.CharField(blank=True, max_length=64)),
                ("status", models.CharField(choices=[("AVAILABLE", "Disponível"), ("QUARANTINE", "Quarentena"), ("INSPECTION", "Em inspeção"), ("BLOCKED", "Bloqueado"), ("REJECTED", "Rejeitado"), ("EXPIRED", "Vencido"), ("CONSUMED", "Consumido")], default="AVAILABLE", max_length=20)),
                ("notes", models.TextField(blank=True)),
                ("item", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name="inventory_lots", to="masterdata.item")),
                ("plant", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name="inventory_lots", to="common.plant")),
                ("supplier", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.PROTECT, related_name="supplied_lots", to="masterdata.supplier")),
            ],
            options={"ordering": ["item__code", "lot_number"]},
        ),
        migrations.CreateModel(
            name="LotBalance",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("created_at", models.DateTimeField(auto_now_add=True)), ("updated_at", models.DateTimeField(auto_now=True)),
                ("on_hand", models.DecimalField(decimal_places=4, default=0, max_digits=18)),
                ("allocated", models.DecimalField(decimal_places=4, default=0, max_digits=18)),
                ("location", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name="lot_balances", to="inventory.location")),
                ("lot", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="balances", to="traceability.inventorylot")),
            ],
        ),
        migrations.CreateModel(
            name="LotTransaction",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("created_at", models.DateTimeField(auto_now_add=True)), ("updated_at", models.DateTimeField(auto_now=True)),
                ("transaction_type", models.CharField(choices=[("RECEIPT", "Recebimento"), ("ISSUE", "Baixa"), ("TRANSFER", "Transferência"), ("ADJUSTMENT", "Ajuste"), ("STATUS", "Mudança de status"), ("SPLIT", "Fracionamento"), ("MERGE", "Consolidação")], max_length=20)),
                ("quantity", models.DecimalField(decimal_places=4, max_digits=18)),
                ("reference_type", models.CharField(blank=True, max_length=40)), ("reference_id", models.CharField(blank=True, max_length=64)),
                ("posted_at", models.DateTimeField(auto_now_add=True)), ("idempotency_key", models.CharField(max_length=160, unique=True)), ("notes", models.TextField(blank=True)),
                ("from_location", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.PROTECT, related_name="outgoing_lot_transactions", to="inventory.location")),
                ("to_location", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.PROTECT, related_name="incoming_lot_transactions", to="inventory.location")),
                ("lot", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name="transactions", to="traceability.inventorylot")),
                ("posted_by", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, to=settings.AUTH_USER_MODEL)),
            ],
        ),
        migrations.CreateModel(
            name="LotReservation",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("created_at", models.DateTimeField(auto_now_add=True)), ("updated_at", models.DateTimeField(auto_now=True)),
                ("quantity", models.DecimalField(decimal_places=4, max_digits=18)), ("consumed_quantity", models.DecimalField(decimal_places=4, default=0, max_digits=18)),
                ("demand_type", models.CharField(max_length=40)), ("demand_id", models.CharField(max_length=64)), ("required_date", models.DateField()),
                ("status", models.CharField(choices=[("OPEN", "Aberta"), ("CONSUMED", "Consumida"), ("CANCELLED", "Cancelada")], default="OPEN", max_length=15)),
                ("location", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name="lot_reservations", to="inventory.location")),
                ("lot", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name="reservations", to="traceability.inventorylot")),
            ],
        ),
        migrations.CreateModel(
            name="SerialNumber",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("created_at", models.DateTimeField(auto_now_add=True)), ("updated_at", models.DateTimeField(auto_now=True)),
                ("serial_number", models.CharField(max_length=100)),
                ("status", models.CharField(choices=[("CREATED", "Criado"), ("AVAILABLE", "Disponível"), ("RESERVED", "Reservado"), ("IN_PRODUCTION", "Em produção"), ("INSTALLED", "Instalado"), ("SHIPPED", "Expedido"), ("BLOCKED", "Bloqueado"), ("SCRAPPED", "Refugado")], default="CREATED", max_length=20)),
                ("source_type", models.CharField(blank=True, max_length=40)), ("source_id", models.CharField(blank=True, max_length=64)),
                ("manufactured_at", models.DateTimeField(blank=True, null=True)), ("notes", models.TextField(blank=True)),
                ("current_location", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.PROTECT, related_name="serial_numbers", to="inventory.location")),
                ("item", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name="serial_numbers", to="masterdata.item")),
                ("lot", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.PROTECT, related_name="serial_numbers", to="traceability.inventorylot")),
                ("plant", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name="serial_numbers", to="common.plant")),
            ],
        ),
        migrations.CreateModel(
            name="SerialTransaction",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("created_at", models.DateTimeField(auto_now_add=True)), ("updated_at", models.DateTimeField(auto_now=True)),
                ("transaction_type", models.CharField(choices=[("CREATE", "Criação"), ("MOVE", "Movimentação"), ("RESERVE", "Reserva"), ("ISSUE", "Baixa"), ("INSTALL", "Instalação"), ("REMOVE", "Remoção"), ("SHIP", "Expedição"), ("BLOCK", "Bloqueio"), ("SCRAP", "Refugo")], max_length=20)),
                ("reference_type", models.CharField(blank=True, max_length=40)), ("reference_id", models.CharField(blank=True, max_length=64)),
                ("posted_at", models.DateTimeField(auto_now_add=True)), ("idempotency_key", models.CharField(max_length=160, unique=True)), ("notes", models.TextField(blank=True)),
                ("from_location", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.PROTECT, related_name="outgoing_serial_transactions", to="inventory.location")),
                ("to_location", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.PROTECT, related_name="incoming_serial_transactions", to="inventory.location")),
                ("posted_by", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, to=settings.AUTH_USER_MODEL)),
                ("serial", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name="transactions", to="traceability.serialnumber")),
            ],
        ),
        migrations.CreateModel(
            name="SerialComponent",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("created_at", models.DateTimeField(auto_now_add=True)), ("updated_at", models.DateTimeField(auto_now=True)),
                ("quantity", models.DecimalField(decimal_places=4, default=1, max_digits=18)), ("installed_at", models.DateTimeField()), ("removed_at", models.DateTimeField(blank=True, null=True)),
                ("work_order_id", models.CharField(blank=True, max_length=64)), ("operation_sequence", models.PositiveIntegerField(blank=True, null=True)), ("notes", models.TextField(blank=True)),
                ("component_serial", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name="where_installed", to="traceability.serialnumber")),
                ("parent_serial", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name="installed_components", to="traceability.serialnumber")),
            ],
        ),
        migrations.AddConstraint(model_name="inventorylot", constraint=models.UniqueConstraint(fields=("plant", "item", "lot_number"), name="uq_lot_plant_item_number")),
        migrations.AddConstraint(model_name="lotbalance", constraint=models.UniqueConstraint(fields=("lot", "location"), name="uq_lotbalance_lot_location")),
        migrations.AddConstraint(model_name="serialnumber", constraint=models.UniqueConstraint(fields=("plant", "item", "serial_number"), name="uq_serial_plant_item_number")),
        migrations.AddConstraint(model_name="serialcomponent", constraint=models.UniqueConstraint(condition=models.Q(("removed_at__isnull", True)), fields=("parent_serial", "component_serial"), name="uq_serialcomp_active_pair")),
    ]
