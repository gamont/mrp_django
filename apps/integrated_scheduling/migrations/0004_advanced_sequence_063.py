from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):
    dependencies = [("integrated_scheduling", "0003_industrial_calendar_062")]

    operations = [
        migrations.AddField(
            model_name="integratedschedulescenario",
            name="dispatch_rule",
            field=models.CharField(choices=[("EDD", "Earliest Due Date"), ("SPT", "Shortest Processing Time"), ("CR", "Critical Ratio"), ("PRIORITY", "Prioridade comercial"), ("SETUP_MIN", "Minimizar setup")], default="EDD", max_length=16),
        ),
        migrations.AddField(model_name="integratedschedulescenario", name="minimize_setups", field=models.BooleanField(default=True)),
        migrations.AddField(model_name="integratedschedulescenario", name="campaign_mode", field=models.BooleanField(default=False)),
        migrations.AddField(model_name="integratedscheduleblock", name="sequence_setup_hours", field=models.DecimalField(decimal_places=4, default=0, max_digits=10)),
        migrations.AddField(model_name="integratedscheduleblock", name="dispatch_score", field=models.DecimalField(decimal_places=6, default=0, max_digits=18)),
        migrations.AddField(model_name="integratedscheduleblock", name="sequence_position", field=models.PositiveIntegerField(default=0)),
        migrations.CreateModel(
            name="ProductFamily",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("code", models.CharField(max_length=40)),
                ("name", models.CharField(max_length=120)),
                ("is_active", models.BooleanField(default=True)),
                ("plant", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="scheduling_product_families", to="common.plant")),
            ],
            options={"ordering": ["plant__code", "code"]},
        ),
        migrations.AddConstraint(model_name="productfamily", constraint=models.UniqueConstraint(fields=("plant", "code"), name="uq_sched_family_plant_code")),
        migrations.CreateModel(
            name="ItemSchedulingProfile",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("commercial_priority", models.PositiveSmallIntegerField(default=50)),
                ("campaign_code", models.CharField(blank=True, max_length=40)),
                ("family", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="items", to="integrated_scheduling.productfamily")),
                ("item", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="scheduling_profiles", to="masterdata.item")),
                ("plant", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="item_scheduling_profiles", to="common.plant")),
            ],
            options={"ordering": ["plant__code", "item__code"]},
        ),
        migrations.AddConstraint(model_name="itemschedulingprofile", constraint=models.UniqueConstraint(fields=("plant", "item"), name="uq_sched_profile_plant_item")),
        migrations.AddConstraint(model_name="itemschedulingprofile", constraint=models.CheckConstraint(condition=models.Q(("commercial_priority__lte", 100)), name="ck_sched_priority_lte_100")),
        migrations.CreateModel(
            name="SequenceSetupRule",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("setup_hours", models.DecimalField(decimal_places=4, default=0, max_digits=10)),
                ("is_active", models.BooleanField(default=True)),
                ("from_family", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.CASCADE, related_name="setup_rules_from", to="integrated_scheduling.productfamily")),
                ("machine", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.CASCADE, related_name="sequence_setup_rules", to="shopfloor.machine")),
                ("plant", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="sequence_setup_rules", to="common.plant")),
                ("to_family", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="setup_rules_to", to="integrated_scheduling.productfamily")),
                ("work_center", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="sequence_setup_rules", to="masterdata.workcenter")),
            ],
            options={"ordering": ["work_center__code", "machine__code", "from_family__code", "to_family__code"]},
        ),
        migrations.AddConstraint(model_name="sequencesetuprule", constraint=models.UniqueConstraint(fields=("plant", "work_center", "machine", "from_family", "to_family"), name="uq_sequence_setup_rule")),
        migrations.AddConstraint(model_name="sequencesetuprule", constraint=models.CheckConstraint(condition=models.Q(("setup_hours__gte", 0)), name="ck_seqsetup_hours_nonneg")),
    ]
