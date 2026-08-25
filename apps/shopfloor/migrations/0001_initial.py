# Generated manually for MRP 0.5.4.
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
        ("production", "0001_initial"),
    ]
    operations = [
        migrations.CreateModel(
            name="OperatorProfile",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("badge_code", models.CharField(max_length=40, unique=True)),
                ("pin_hash", models.CharField(max_length=128)),
                ("is_active", models.BooleanField(default=True)),
                ("failed_attempts", models.PositiveSmallIntegerField(default=0)),
                ("locked_until", models.DateTimeField(blank=True, null=True)),
                ("user", models.OneToOneField(on_delete=django.db.models.deletion.CASCADE, related_name="shopfloor_profile", to=settings.AUTH_USER_MODEL)),
            ],
            options={"ordering": ["badge_code"], "permissions": [("use_shopfloor_terminal", "Pode usar terminal de chão de fábrica")]},
        ),
        migrations.CreateModel(
            name="DowntimeReason",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("code", models.CharField(max_length=30)),
                ("description", models.CharField(max_length=160)),
                ("category", models.CharField(choices=[("UNPLANNED", "Não planejada"), ("PLANNED", "Planejada"), ("QUALITY", "Qualidade"), ("MATERIAL", "Falta de material"), ("TOOLING", "Ferramental"), ("OTHER", "Outros")], default="UNPLANNED", max_length=20)),
                ("is_active", models.BooleanField(default=True)),
                ("plant", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="downtime_reasons", to="common.plant")),
            ],
            options={"ordering": ["plant__code", "code"], "constraints": [models.UniqueConstraint(fields=("plant", "code"), name="uq_downtime_reason_plant_code")]},
        ),
        migrations.CreateModel(
            name="Machine",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("code", models.CharField(max_length=40)),
                ("name", models.CharField(max_length=120)),
                ("status", models.CharField(choices=[("INACTIVE", "Inativa"), ("IDLE", "Ociosa"), ("SETUP", "Setup"), ("RUNNING", "Em operação"), ("DOWN", "Parada"), ("REPAIR", "Em reparo"), ("PREVENTIVE", "Manutenção preventiva")], default="IDLE", max_length=20)),
                ("status_since", models.DateTimeField(default=django.utils.timezone.now)),
                ("is_active", models.BooleanField(default=True)),
                ("current_operation", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="machine_assignments", to="production.workorderoperation")),
                ("plant", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="machines", to="common.plant")),
                ("work_center", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name="machines", to="masterdata.workcenter")),
            ],
            options={
                "ordering": ["plant__code", "code"],
                "indexes": [models.Index(fields=["plant", "work_center", "status"], name="ix_machine_wc_status")],
                "constraints": [models.UniqueConstraint(fields=("plant", "code"), name="uq_machine_plant_code")],
            },
        ),
        migrations.CreateModel(
            name="TerminalStation",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("code", models.CharField(max_length=40)),
                ("name", models.CharField(max_length=120)),
                ("is_active", models.BooleanField(default=True)),
                ("machine", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="terminal_stations", to="shopfloor.machine")),
                ("plant", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="terminal_stations", to="common.plant")),
                ("work_center", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.PROTECT, related_name="terminal_stations", to="masterdata.workcenter")),
            ],
            options={"ordering": ["plant__code", "code"], "constraints": [models.UniqueConstraint(fields=("plant", "code"), name="uq_terminal_plant_code")]},
        ),
        migrations.CreateModel(
            name="DowntimeEvent",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("started_at", models.DateTimeField()),
                ("ended_at", models.DateTimeField(blank=True, null=True)),
                ("notes", models.TextField(blank=True)),
                ("machine", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name="downtime_events", to="shopfloor.machine")),
                ("operation", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="downtime_events", to="production.workorderoperation")),
                ("reason", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name="events", to="shopfloor.downtimereason")),
                ("reported_by", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="reported_downtimes", to=settings.AUTH_USER_MODEL)),
            ],
            options={
                "ordering": ["-started_at"],
                "indexes": [models.Index(fields=["machine", "ended_at", "started_at"], name="ix_downtime_machine_open")],
                "constraints": [
                    models.CheckConstraint(condition=models.Q(("ended_at__isnull", True)) | models.Q(("ended_at__gte", models.F("started_at"))), name="ck_downtime_end_after_start"),
                    models.UniqueConstraint(condition=models.Q(("ended_at__isnull", True)), fields=("machine",), name="uq_machine_open_downtime"),
                ],
            },
        ),
    ]
