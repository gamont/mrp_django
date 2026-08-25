from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):
    dependencies = [
        ("integrated_scheduling", "0002_finite_gantt_scenarios"),
        ("masterdata", "0001_initial"),
        ("shopfloor", "0003_oee_shift_targets_history"),
    ]

    operations = [
        migrations.AddField(
            model_name="integratedschedulescenario",
            name="respect_industrial_calendar",
            field=models.BooleanField(default=True),
        ),
        migrations.CreateModel(
            name="IndustrialShiftBreak",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("name", models.CharField(default="Intervalo", max_length=80)),
                ("start_time", models.TimeField()),
                ("end_time", models.TimeField()),
                ("is_active", models.BooleanField(default=True)),
                ("shift", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="industrial_breaks", to="masterdata.workcentershift")),
            ],
            options={"ordering": ["shift", "start_time"]},
        ),
        migrations.AddConstraint(
            model_name="industrialshiftbreak",
            constraint=models.CheckConstraint(condition=models.Q(end_time__gt=models.F("start_time")), name="ck_intshiftbreak_window"),
        ),
        migrations.CreateModel(
            name="IndustrialCalendarWindow",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("date", models.DateField()),
                ("start_time", models.TimeField()),
                ("end_time", models.TimeField()),
                ("window_type", models.CharField(choices=[("OVERTIME", "Hora extra"), ("CLOSURE", "Fechamento")], max_length=12)),
                ("capacity_factor", models.DecimalField(decimal_places=3, default=1, max_digits=6)),
                ("note", models.CharField(blank=True, max_length=200)),
                ("machine", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.CASCADE, related_name="industrial_calendar_windows", to="shopfloor.machine")),
                ("plant", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="industrial_calendar_windows", to="common.plant")),
                ("work_center", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.CASCADE, related_name="industrial_calendar_windows", to="masterdata.workcenter")),
            ],
            options={"ordering": ["date", "start_time"]},
        ),
        migrations.AddIndex(model_name="industrialcalendarwindow", index=models.Index(fields=["plant", "date", "window_type"], name="ix_intcal_plant_date")),
        migrations.AddConstraint(model_name="industrialcalendarwindow", constraint=models.CheckConstraint(condition=models.Q(end_time__gt=models.F("start_time")), name="ck_intcal_window")),
        migrations.AddConstraint(model_name="industrialcalendarwindow", constraint=models.CheckConstraint(condition=models.Q(capacity_factor__gt=0), name="ck_intcal_factor_pos")),
        migrations.CreateModel(
            name="IntegratedScheduleSegment",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("segment_type", models.CharField(choices=[("REGULAR", "Turno regular"), ("OVERTIME", "Hora extra")], default="REGULAR", max_length=12)),
                ("start", models.DateTimeField()),
                ("end", models.DateTimeField()),
                ("effective_hours", models.DecimalField(decimal_places=4, default=0, max_digits=12)),
                ("capacity_factor", models.DecimalField(decimal_places=4, default=1, max_digits=7)),
                ("block", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="segments", to="integrated_scheduling.integratedscheduleblock")),
            ],
            options={"ordering": ["start"]},
        ),
        migrations.AddIndex(model_name="integratedschedulesegment", index=models.Index(fields=["block", "start"], name="ix_intseg_block_start")),
        migrations.AddConstraint(model_name="integratedschedulesegment", constraint=models.CheckConstraint(condition=models.Q(end__gt=models.F("start")), name="ck_intseg_window")),
        migrations.AddConstraint(model_name="integratedschedulesegment", constraint=models.CheckConstraint(condition=models.Q(effective_hours__gte=0), name="ck_intseg_hours_nonneg")),
        migrations.AddConstraint(model_name="integratedschedulesegment", constraint=models.CheckConstraint(condition=models.Q(capacity_factor__gt=0), name="ck_intseg_factor_pos")),
    ]
