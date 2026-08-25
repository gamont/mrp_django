from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):
    dependencies = [
        ("integrated_scheduling", "0001_initial"),
        ("production", "0001_initial"),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]
    operations = [
        migrations.AddField(
            model_name="integratedschedulescenario",
            name="scheduling_direction",
            field=models.CharField(choices=[("FORWARD", "Forward"), ("BACKWARD", "Backward")], default="FORWARD", max_length=12),
        ),
        migrations.AddField(
            model_name="integratedschedulescenario",
            name="finite_by_machine",
            field=models.BooleanField(default=True),
        ),
        migrations.AddField(
            model_name="integratedschedulescenario",
            name="allow_alternate_resources",
            field=models.BooleanField(default=True),
        ),
        migrations.AddField(
            model_name="integratedscheduleblock",
            name="assignment_reason",
            field=models.CharField(blank=True, max_length=220),
        ),
        migrations.AddField(
            model_name="integratedscheduleblock",
            name="manually_locked",
            field=models.BooleanField(default=False),
        ),
        migrations.CreateModel(
            name="PublishedOperationSchedule",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("planned_start", models.DateTimeField()),
                ("planned_end", models.DateTimeField()),
                ("published_at", models.DateTimeField(auto_now_add=True)),
                ("machine", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="published_operation_schedules", to="shopfloor.machine")),
                ("operation", models.OneToOneField(on_delete=django.db.models.deletion.CASCADE, related_name="published_schedule", to="production.workorderoperation")),
                ("published_by", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="published_operation_schedules", to=settings.AUTH_USER_MODEL)),
                ("scenario", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name="published_operations", to="integrated_scheduling.integratedschedulescenario")),
                ("work_center", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name="published_operation_schedules", to="masterdata.workcenter")),
            ],
            options={"ordering": ["planned_start", "work_center__code"]},
        ),
        migrations.AddIndex(
            model_name="publishedoperationschedule",
            index=models.Index(fields=["work_center", "planned_start"], name="ix_pubop_center_start"),
        ),
        migrations.AddConstraint(
            model_name="publishedoperationschedule",
            constraint=models.CheckConstraint(condition=models.Q(planned_end__gt=models.F("planned_start")), name="ck_pubop_window"),
        ),
    ]
