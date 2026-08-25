# Generated for MRP Django 0.2.1.
import uuid

from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):
    initial = True

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name="Plant",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("code", models.CharField(max_length=20, unique=True)),
                ("name", models.CharField(max_length=120)),
                ("timezone", models.CharField(default="America/Sao_Paulo", max_length=50)),
                ("is_active", models.BooleanField(default=True)),
            ],
            options={"ordering": ["code"]},
        ),
        migrations.CreateModel(
            name="DomainEvent",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("event_id", models.UUIDField(default=uuid.uuid4, editable=False, unique=True)),
                ("idempotency_key", models.CharField(max_length=160, unique=True)),
                ("event_type", models.CharField(db_index=True, max_length=80)),
                ("aggregate_type", models.CharField(db_index=True, max_length=80)),
                ("aggregate_id", models.CharField(db_index=True, max_length=80)),
                ("payload", models.JSONField(blank=True, default=dict)),
                ("occurred_at", models.DateTimeField(auto_now_add=True, db_index=True)),
                (
                    "actor",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name="mrp_domain_events",
                        to=settings.AUTH_USER_MODEL,
                    ),
                ),
            ],
            options={
                "ordering": ["-occurred_at", "-id"],
                "indexes": [
                    models.Index(fields=["aggregate_type", "aggregate_id", "occurred_at"], name="ix_event_aggregate_time"),
                    models.Index(fields=["event_type", "occurred_at"], name="ix_event_type_time"),
                ],
            },
        ),
        migrations.CreateModel(
            name="ShopCalendarDay",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("date", models.DateField()),
                ("is_working_day", models.BooleanField(default=True)),
                ("capacity_factor", models.DecimalField(decimal_places=3, default=1, max_digits=6)),
                ("note", models.CharField(blank=True, max_length=200)),
                (
                    "plant",
                    models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="calendar_days", to="common.plant"),
                ),
            ],
            options={
                "ordering": ["date"],
                "constraints": [
                    models.UniqueConstraint(fields=("plant", "date"), name="uq_calendar_plant_date"),
                    models.CheckConstraint(condition=models.Q(("capacity_factor__gt", 0)), name="ck_calendar_capacity_pos"),
                ],
            },
        ),
    ]
