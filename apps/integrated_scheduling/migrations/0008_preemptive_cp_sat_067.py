from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):
    dependencies = [("integrated_scheduling", "0007_solver_async_warmstart_066")]

    operations = [
        migrations.AddField(model_name="schedulesolverrun", name="preemptive_operations", field=models.BooleanField(default=False)),
        migrations.AddField(model_name="schedulesolverrun", name="max_consecutive_minutes", field=models.PositiveIntegerField(default=240)),
        migrations.AddField(model_name="schedulesolverrun", name="handoff_penalty", field=models.PositiveIntegerField(default=5)),
        migrations.AddConstraint(model_name="schedulesolverrun", constraint=models.CheckConstraint(condition=models.Q(("max_consecutive_minutes__gte", 1)), name="ck_solver_max_consecutive_pos")),
        migrations.CreateModel(
            name="ScheduleSolverSegment",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("sequence", models.PositiveSmallIntegerField()),
                ("start", models.DateTimeField()),
                ("end", models.DateTimeField()),
                ("processing_minutes", models.PositiveIntegerField()),
                ("calendar_kind", models.CharField(default="REGULAR", max_length=20)),
                ("shift_name", models.CharField(blank=True, max_length=60)),
                ("handoff_after", models.BooleanField(default=False)),
                ("details", models.JSONField(blank=True, default=dict)),
                ("assignment", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="segments", to="integrated_scheduling.schedulesolverassignment")),
            ],
            options={"ordering": ["assignment", "sequence"]},
        ),
        migrations.AddConstraint(model_name="schedulesolversegment", constraint=models.UniqueConstraint(fields=("assignment", "sequence"), name="uq_solver_segment_sequence")),
        migrations.AddConstraint(model_name="schedulesolversegment", constraint=models.CheckConstraint(condition=models.Q(("end__gt", models.F("start"))), name="ck_solver_segment_window")),
        migrations.AddConstraint(model_name="schedulesolversegment", constraint=models.CheckConstraint(condition=models.Q(("processing_minutes__gt", 0)), name="ck_solver_segment_minutes_pos")),
        migrations.AddIndex(model_name="schedulesolversegment", index=models.Index(fields=["assignment", "start"], name="ix_solver_segment_start")),
    ]
