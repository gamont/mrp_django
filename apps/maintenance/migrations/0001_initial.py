# Generated manually for MRP 0.5.7.
from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion
import django.utils.timezone


class Migration(migrations.Migration):
    initial = True
    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ("common", "0001_initial"),
        ("masterdata", "0001_initial"),
        ("inventory", "0001_initial"),
        ("shopfloor", "0003_oee_shift_targets_history"),
    ]
    operations = [
        migrations.CreateModel(
            name="MaintenanceAsset",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("created_at", models.DateTimeField(auto_now_add=True)), ("updated_at", models.DateTimeField(auto_now=True)),
                ("code", models.CharField(max_length=40)), ("name", models.CharField(max_length=160)),
                ("asset_type", models.CharField(choices=[("MACHINE","Máquina"),("TOOL","Ferramental"),("UTILITY","Utilidade"),("FACILITY","Instalação"),("OTHER","Outro")], default="MACHINE", max_length=20)),
                ("criticality", models.CharField(choices=[("LOW","Baixa"),("MEDIUM","Média"),("HIGH","Alta"),("CRITICAL","Crítica")], default="MEDIUM", max_length=20)),
                ("manufacturer", models.CharField(blank=True, max_length=120)), ("model_number", models.CharField(blank=True, max_length=80)), ("serial_number", models.CharField(blank=True, max_length=100)),
                ("commissioned_on", models.DateField(blank=True, null=True)), ("is_active", models.BooleanField(default=True)),
                ("machine", models.OneToOneField(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="maintenance_asset", to="shopfloor.machine")),
                ("plant", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="maintenance_assets", to="common.plant")),
                ("work_center", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="maintenance_assets", to="masterdata.workcenter")),
            ], options={"ordering":["plant__code","code"], "indexes":[models.Index(fields=["plant","criticality","is_active"], name="ix_maint_asset_crit")], "constraints":[models.UniqueConstraint(fields=("plant","code"), name="uq_maint_asset_plant_code")]},
        ),
        migrations.CreateModel(
            name="MaintenancePlan",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")), ("created_at", models.DateTimeField(auto_now_add=True)), ("updated_at", models.DateTimeField(auto_now=True)),
                ("code", models.CharField(max_length=50)), ("title", models.CharField(max_length=180)),
                ("strategy", models.CharField(choices=[("CALENDAR","Calendário"),("METER","Medidor"),("HYBRID","Calendário ou medidor")], default="CALENDAR", max_length=20)),
                ("interval_days", models.PositiveIntegerField(default=0)), ("interval_meter", models.DecimalField(decimal_places=3, default=0, max_digits=18)), ("planned_duration_hours", models.DecimalField(decimal_places=2, default=0, max_digits=10)),
                ("next_due_date", models.DateField(blank=True, null=True)), ("next_due_meter", models.DecimalField(blank=True, decimal_places=3, max_digits=18, null=True)), ("instructions", models.TextField(blank=True)), ("is_active", models.BooleanField(default=True)),
                ("asset", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="maintenance_plans", to="maintenance.maintenanceasset")),
            ], options={"ordering":["asset__code","code"], "constraints":[models.UniqueConstraint(fields=("asset","code"), name="uq_maint_plan_asset_code"), models.CheckConstraint(condition=models.Q(("interval_meter__gte",0)), name="ck_maint_plan_meter_nonneg"), models.CheckConstraint(condition=models.Q(("planned_duration_hours__gte",0)), name="ck_maint_plan_duration_nonneg")]},
        ),
        migrations.CreateModel(
            name="MaintenanceWorkOrder",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")), ("created_at", models.DateTimeField(auto_now_add=True)), ("updated_at", models.DateTimeField(auto_now=True)),
                ("number", models.CharField(max_length=50, unique=True)), ("order_type", models.CharField(choices=[("PREVENTIVE","Preventiva"),("CORRECTIVE","Corretiva"),("PREDICTIVE","Preditiva"),("INSPECTION","Inspeção")], default="PREVENTIVE", max_length=20)),
                ("priority", models.CharField(choices=[("LOW","Baixa"),("NORMAL","Normal"),("HIGH","Alta"),("EMERGENCY","Emergência")], default="NORMAL", max_length=20)),
                ("status", models.CharField(choices=[("PLANNED","Planejada"),("RELEASED","Liberada"),("IN_PROGRESS","Em execução"),("WAITING_PARTS","Aguardando peças"),("COMPLETED","Concluída"),("CANCELLED","Cancelada")], default="PLANNED", max_length=20)),
                ("title", models.CharField(max_length=180)), ("description", models.TextField(blank=True)), ("requested_at", models.DateTimeField(default=django.utils.timezone.now)), ("scheduled_start", models.DateTimeField(blank=True, null=True)), ("scheduled_end", models.DateTimeField(blank=True, null=True)), ("started_at", models.DateTimeField(blank=True, null=True)), ("completed_at", models.DateTimeField(blank=True, null=True)), ("completion_notes", models.TextField(blank=True)), ("meter_at_completion", models.DecimalField(blank=True, decimal_places=3, max_digits=18, null=True)),
                ("asset", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name="work_orders", to="maintenance.maintenanceasset")),
                ("assigned_to", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="assigned_maintenance_orders", to=settings.AUTH_USER_MODEL)),
                ("downtime_event", models.OneToOneField(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="maintenance_work_order", to="shopfloor.downtimeevent")),
                ("plan", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="work_orders", to="maintenance.maintenanceplan")),
                ("plant", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name="maintenance_work_orders", to="common.plant")),
                ("requested_by", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="requested_maintenance_orders", to=settings.AUTH_USER_MODEL)),
            ], options={"ordering":["-requested_at","number"], "indexes":[models.Index(fields=["plant","status","priority"], name="ix_maint_wo_status"), models.Index(fields=["asset","scheduled_start"], name="ix_maint_wo_asset_date")], "constraints":[models.CheckConstraint(condition=models.Q(("scheduled_end__isnull",True)) | models.Q(("scheduled_start__isnull",True)) | models.Q(("scheduled_end__gte",models.F("scheduled_start"))), name="ck_maint_wo_schedule_order")]},
        ),
        migrations.CreateModel(
            name="AssetMeterReading",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")), ("created_at", models.DateTimeField(auto_now_add=True)), ("updated_at", models.DateTimeField(auto_now=True)), ("reading_at", models.DateTimeField(default=django.utils.timezone.now)), ("meter_value", models.DecimalField(decimal_places=3, max_digits=18)), ("source", models.CharField(default="MANUAL", max_length=40)), ("notes", models.CharField(blank=True, max_length=240)),
                ("asset", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="meter_readings", to="maintenance.maintenanceasset")), ("recorded_by", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="maintenance_meter_readings", to=settings.AUTH_USER_MODEL)),
            ], options={"ordering":["-reading_at","-id"], "indexes":[models.Index(fields=["asset","reading_at"], name="ix_asset_meter_time")], "constraints":[models.CheckConstraint(condition=models.Q(("meter_value__gte",0)), name="ck_asset_meter_nonneg")]},
        ),
        migrations.CreateModel(
            name="MaintenancePart",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")), ("created_at", models.DateTimeField(auto_now_add=True)), ("updated_at", models.DateTimeField(auto_now=True)), ("planned_quantity", models.DecimalField(decimal_places=4, default=0, max_digits=18)), ("issued_quantity", models.DecimalField(decimal_places=4, default=0, max_digits=18)),
                ("issue_transaction", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="maintenance_part_lines", to="inventory.inventorytransaction")), ("item", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name="maintenance_parts", to="masterdata.item")), ("source_location", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.PROTECT, related_name="maintenance_part_issues", to="inventory.location")), ("work_order", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="parts", to="maintenance.maintenanceworkorder")),
            ], options={"ordering":["work_order__number","item__code"], "constraints":[models.UniqueConstraint(fields=("work_order","item"), name="uq_maint_part_wo_item"), models.CheckConstraint(condition=models.Q(("planned_quantity__gte",0)), name="ck_maint_part_plan_nonneg"), models.CheckConstraint(condition=models.Q(("issued_quantity__gte",0)), name="ck_maint_part_issue_nonneg")]},
        ),
        migrations.CreateModel(
            name="FailureEvent",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")), ("created_at", models.DateTimeField(auto_now_add=True)), ("updated_at", models.DateTimeField(auto_now=True)), ("failure_class", models.CharField(choices=[("MECHANICAL","Mecânica"),("ELECTRICAL","Elétrica"),("AUTOMATION","Automação"),("QUALITY","Qualidade"),("OTHER","Outra")], default="OTHER", max_length=20)), ("occurred_at", models.DateTimeField(default=django.utils.timezone.now)), ("symptom", models.TextField()), ("cause", models.TextField(blank=True)), ("corrective_action", models.TextField(blank=True)), ("resolved_at", models.DateTimeField(blank=True, null=True)),
                ("asset", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name="failure_events", to="maintenance.maintenanceasset")), ("downtime_event", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="failure_events", to="shopfloor.downtimeevent")), ("reported_by", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="reported_failures", to=settings.AUTH_USER_MODEL)), ("work_order", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="failure_events", to="maintenance.maintenanceworkorder")),
            ], options={"ordering":["-occurred_at"], "indexes":[models.Index(fields=["asset","occurred_at"], name="ix_failure_asset_time")]},
        ),
    ]
