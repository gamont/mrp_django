# Generated manually for MRP 0.5.5.
from django.db import migrations, models
import django.db.models.deletion
import django.utils.timezone


class Migration(migrations.Migration):
    dependencies = [
        ("shopfloor", "0001_initial"),
        ("production", "0001_initial"),
    ]

    operations = [
        migrations.AddField(
            model_name="machine",
            name="planned_minutes_per_day",
            field=models.DecimalField(decimal_places=2, default=480, max_digits=8),
        ),
        migrations.AddField(
            model_name="machine",
            name="ideal_cycle_seconds",
            field=models.DecimalField(decimal_places=4, default=0, max_digits=12),
        ),
        migrations.AddConstraint(
            model_name="machine",
            constraint=models.CheckConstraint(condition=models.Q(("planned_minutes_per_day__gte", 0)), name="ck_machine_plan_minutes_nonneg"),
        ),
        migrations.AddConstraint(
            model_name="machine",
            constraint=models.CheckConstraint(condition=models.Q(("ideal_cycle_seconds__gte", 0)), name="ck_machine_cycle_nonneg"),
        ),
        migrations.CreateModel(
            name="MachineProductionRecord",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("reported_at", models.DateTimeField()),
                ("machine", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name="production_records", to="shopfloor.machine")),
                ("operation", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name="shopfloor_machine_records", to="production.workorderoperation")),
                ("report", models.OneToOneField(on_delete=django.db.models.deletion.PROTECT, related_name="shopfloor_machine_record", to="production.productionreport")),
            ],
            options={
                "ordering": ["-reported_at"],
                "indexes": [models.Index(fields=["machine", "reported_at"], name="ix_sf_prod_machine_time")],
            },
        ),
        migrations.CreateModel(
            name="OEEPeriodSnapshot",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("metric_date", models.DateField()),
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
                ("failures", models.PositiveIntegerField(default=0)),
                ("mtbf_minutes", models.DecimalField(decimal_places=2, default=0, max_digits=12)),
                ("mttr_minutes", models.DecimalField(decimal_places=2, default=0, max_digits=12)),
                ("calculated_at", models.DateTimeField(default=django.utils.timezone.now)),
                ("machine", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="oee_snapshots", to="shopfloor.machine")),
            ],
            options={
                "ordering": ["-metric_date", "machine__code"],
                "indexes": [models.Index(fields=["metric_date", "machine"], name="ix_oee_date_machine")],
                "constraints": [
                    models.UniqueConstraint(fields=("machine", "metric_date"), name="uq_oee_machine_date"),
                    models.CheckConstraint(condition=models.Q(("planned_minutes__gte", 0)), name="ck_oee_planned_nonneg"),
                    models.CheckConstraint(condition=models.Q(("run_minutes__gte", 0)), name="ck_oee_run_nonneg"),
                    models.CheckConstraint(condition=models.Q(("downtime_minutes__gte", 0)), name="ck_oee_down_nonneg"),
                ],
            },
        ),
    ]
