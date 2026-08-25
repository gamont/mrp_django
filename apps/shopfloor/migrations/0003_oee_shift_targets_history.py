# Generated manually for MRP 0.5.6.
from decimal import Decimal

from django.db import migrations, models
import django.db.models.deletion
import django.utils.timezone


class Migration(migrations.Migration):
    dependencies = [
        ("shopfloor", "0002_oee_monitoring"),
        ("masterdata", "0001_initial"),
    ]

    operations = [
        migrations.AddField(
            model_name="oeeperiodsnapshot",
            name="availability_loss_minutes",
            field=models.DecimalField(decimal_places=2, default=0, max_digits=12),
        ),
        migrations.AddField(
            model_name="oeeperiodsnapshot",
            name="performance_loss_minutes",
            field=models.DecimalField(decimal_places=2, default=0, max_digits=12),
        ),
        migrations.AddField(
            model_name="oeeperiodsnapshot",
            name="quality_loss_minutes",
            field=models.DecimalField(decimal_places=2, default=0, max_digits=12),
        ),
        migrations.CreateModel(
            name="OEETarget",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("effective_from", models.DateField()),
                ("effective_to", models.DateField(blank=True, null=True)),
                ("oee_target", models.DecimalField(decimal_places=4, default=Decimal("0.8500"), max_digits=7)),
                ("availability_target", models.DecimalField(decimal_places=4, default=Decimal("0.9000"), max_digits=7)),
                ("performance_target", models.DecimalField(decimal_places=4, default=Decimal("0.9500"), max_digits=7)),
                ("quality_target", models.DecimalField(decimal_places=4, default=Decimal("0.9900"), max_digits=7)),
                ("is_active", models.BooleanField(default=True)),
                ("machine", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.CASCADE, related_name="oee_targets", to="shopfloor.machine")),
                ("plant", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="oee_targets", to="common.plant")),
                ("work_center", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.CASCADE, related_name="oee_targets", to="masterdata.workcenter")),
            ],
            options={
                "ordering": ["-effective_from", "plant__code", "work_center__code", "machine__code"],
                "indexes": [
                    models.Index(fields=["plant", "effective_from", "effective_to"], name="ix_oee_target_plant_date"),
                    models.Index(fields=["machine", "effective_from"], name="ix_oee_target_machine"),
                ],
                "constraints": [
                    models.CheckConstraint(condition=models.Q(("oee_target__gte", 0), ("oee_target__lte", 1)), name="ck_oee_target_oee_0_1"),
                    models.CheckConstraint(condition=models.Q(("availability_target__gte", 0), ("availability_target__lte", 1)), name="ck_oee_target_avail_0_1"),
                    models.CheckConstraint(condition=models.Q(("performance_target__gte", 0), ("performance_target__lte", 1)), name="ck_oee_target_perf_0_1"),
                    models.CheckConstraint(condition=models.Q(("quality_target__gte", 0), ("quality_target__lte", 1)), name="ck_oee_target_quality_0_1"),
                    models.CheckConstraint(condition=models.Q(("effective_to__isnull", True)) | models.Q(("effective_to__gte", models.F("effective_from"))), name="ck_oee_target_dates"),
                ],
            },
        ),
        migrations.CreateModel(
            name="OEEShiftSnapshot",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("metric_date", models.DateField()),
                ("window_start", models.DateTimeField()),
                ("window_end", models.DateTimeField()),
                ("planned_minutes", models.DecimalField(decimal_places=2, default=0, max_digits=12)),
                ("downtime_minutes", models.DecimalField(decimal_places=2, default=0, max_digits=12)),
                ("run_minutes", models.DecimalField(decimal_places=2, default=0, max_digits=12)),
                ("ideal_cycle_seconds", models.DecimalField(decimal_places=4, default=0, max_digits=12)),
                ("good_quantity", models.DecimalField(decimal_places=4, default=0, max_digits=18)),
                ("scrap_quantity", models.DecimalField(decimal_places=4, default=0, max_digits=18)),
                ("availability", models.DecimalField(decimal_places=4, default=0, max_digits=7)),
                ("performance", models.DecimalField(decimal_places=4, default=0, max_digits=7)),
                ("quality", models.DecimalField(decimal_places=4, default=0, max_digits=7)),
                ("oee", models.DecimalField(decimal_places=4, default=0, max_digits=7)),
                ("availability_loss_minutes", models.DecimalField(decimal_places=2, default=0, max_digits=12)),
                ("performance_loss_minutes", models.DecimalField(decimal_places=2, default=0, max_digits=12)),
                ("quality_loss_minutes", models.DecimalField(decimal_places=2, default=0, max_digits=12)),
                ("failures", models.PositiveIntegerField(default=0)),
                ("mtbf_minutes", models.DecimalField(decimal_places=2, default=0, max_digits=12)),
                ("mttr_minutes", models.DecimalField(decimal_places=2, default=0, max_digits=12)),
                ("calculated_at", models.DateTimeField(default=django.utils.timezone.now)),
                ("machine", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="oee_shift_snapshots", to="shopfloor.machine")),
                ("shift", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name="oee_snapshots", to="masterdata.workcentershift")),
            ],
            options={
                "ordering": ["-metric_date", "shift__start_time", "machine__code"],
                "indexes": [models.Index(fields=["metric_date", "shift", "machine"], name="ix_oees_date_shift_machine")],
                "constraints": [
                    models.UniqueConstraint(fields=("machine", "shift", "metric_date"), name="uq_oee_machine_shift_date"),
                    models.CheckConstraint(condition=models.Q(("planned_minutes__gte", 0)), name="ck_oees_plan_nonneg"),
                    models.CheckConstraint(condition=models.Q(("run_minutes__gte", 0)), name="ck_oees_run_nonneg"),
                    models.CheckConstraint(condition=models.Q(("downtime_minutes__gte", 0)), name="ck_oees_down_nonneg"),
                ],
            },
        ),
    ]
