# Generated manually for MRP 0.5.9.
from django.db import migrations, models
import django.db.models.deletion
import django.utils.timezone


class Migration(migrations.Migration):
    dependencies = [
        ("inventory", "0001_initial"),
        ("production", "0001_initial"),
        ("maintenance", "0002_planning_reliability"),
    ]

    operations = [
        migrations.AddField(model_name="maintenanceworkorder", name="priority_score", field=models.DecimalField(decimal_places=2, default=0, max_digits=8)),
        migrations.AddField(model_name="maintenanceworkorder", name="priority_reason", field=models.JSONField(blank=True, default=dict)),
        migrations.AddField(model_name="maintenanceworkorder", name="scheduling_locked", field=models.BooleanField(default=False)),
        migrations.CreateModel(
            name="MaintenanceRequiredSkill",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("min_proficiency", models.PositiveSmallIntegerField(default=1)),
                ("technicians_required", models.PositiveSmallIntegerField(default=1)),
                ("skill", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name="maintenance_requirements", to="maintenance.technicianskill")),
                ("work_order", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="required_skills", to="maintenance.maintenanceworkorder")),
            ],
        ),
        migrations.CreateModel(
            name="MaintenancePartReservation",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("part", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="reservations", to="maintenance.maintenancepart")),
                ("reservation", models.OneToOneField(on_delete=django.db.models.deletion.CASCADE, related_name="maintenance_part_reservation", to="inventory.reservation")),
            ],
            options={"ordering": ["part__work_order__number", "part__item__code", "reservation__location_id"]},
        ),
        migrations.CreateModel(
            name="MaintenanceScheduleConflict",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("conflict_type", models.CharField(choices=[("PRODUCTION", "Produção"), ("MACHINE", "Máquina"), ("TECHNICIAN", "Técnico"), ("PARTS", "Peças")], max_length=20)),
                ("severity", models.CharField(choices=[("INFO", "Informativa"), ("WARNING", "Atenção"), ("CRITICAL", "Crítica")], default="WARNING", max_length=20)),
                ("message", models.CharField(max_length=300)),
                ("detected_at", models.DateTimeField(default=django.utils.timezone.now)),
                ("resolved_at", models.DateTimeField(blank=True, null=True)),
                ("related_operation", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="maintenance_conflicts", to="production.workorderoperation")),
                ("work_order", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="schedule_conflicts", to="maintenance.maintenanceworkorder")),
            ],
            options={"ordering": ["-detected_at", "id"]},
        ),
        migrations.AddConstraint(model_name="maintenancerequiredskill", constraint=models.UniqueConstraint(fields=("work_order", "skill"), name="uq_maint_wo_required_skill")),
        migrations.AddConstraint(model_name="maintenancerequiredskill", constraint=models.CheckConstraint(condition=models.Q(("min_proficiency__gte", 1), ("min_proficiency__lte", 5)), name="ck_maint_req_skill_prof")),
        migrations.AddConstraint(model_name="maintenancerequiredskill", constraint=models.CheckConstraint(condition=models.Q(("technicians_required__gte", 1)), name="ck_maint_req_skill_techs")),
        migrations.AddIndex(model_name="maintenancescheduleconflict", index=models.Index(fields=["work_order", "conflict_type", "resolved_at"], name="ix_maint_sched_conflict")),
    ]
