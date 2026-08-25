from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion
import django.utils.timezone


class Migration(migrations.Migration):
    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ("integrated_scheduling", "0019_executive_sop_078"),
        ("masterdata", "0001_initial"),
        ("planning", "0002_demand_pegging_allocation_073"),
    ]

    operations = [
        migrations.CreateModel(
            name="SAndOPCycle",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("created_at", models.DateTimeField(auto_now_add=True)), ("updated_at", models.DateTimeField(auto_now=True)),
                ("code", models.CharField(max_length=40)), ("version", models.PositiveIntegerField(default=1)),
                ("cycle_month", models.DateField(help_text="Primeiro dia do mês do ciclo S&OP.")),
                ("horizon_start", models.DateField()), ("horizon_end", models.DateField()), ("meeting_date", models.DateField(blank=True, null=True)),
                ("status", models.CharField(choices=[("DRAFT","Rascunho"),("DEMAND_REVIEW","Demand Review"),("SUPPLY_REVIEW","Supply Review"),("PRE_SOP","Pre-S&OP"),("EXECUTIVE_REVIEW","Executive S&OP"),("APPROVED","Aprovado"),("PUBLISHED","Publicado"),("ARCHIVED","Arquivado")], default="DRAFT", max_length=24)),
                ("demand_baseline", models.JSONField(blank=True, default=dict)), ("demand_consensus_summary", models.JSONField(blank=True, default=dict)),
                ("supply_summary", models.JSONField(blank=True, default=dict)), ("constraints_summary", models.JSONField(blank=True, default=dict)),
                ("executive_summary", models.JSONField(blank=True, default=dict)), ("notes", models.TextField(blank=True)),
                ("approved_at", models.DateTimeField(blank=True, null=True)), ("published_at", models.DateTimeField(blank=True, null=True)),
                ("approved_by", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="sop_cycles_approved", to=settings.AUTH_USER_MODEL)),
                ("created_by", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="sop_cycles_created", to=settings.AUTH_USER_MODEL)),
                ("plant", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name="sop_cycles", to="common.plant")),
                ("published_by", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="sop_cycles_published", to=settings.AUTH_USER_MODEL)),
                ("published_planning_run", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="source_sop_cycles", to="planning.planningrun")),
                ("source_snapshot", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="sop_cycles", to="integrated_scheduling.executivesandopsnapshot")),
            ], options={"ordering":["-cycle_month","-version"]},
        ),
        migrations.AddConstraint(model_name="sandopcycle", constraint=models.UniqueConstraint(fields=("plant","code","version"), name="uq_sop_cycle_version")),
        migrations.AddConstraint(model_name="sandopcycle", constraint=models.CheckConstraint(condition=models.Q(("horizon_end__gte", models.F("horizon_start"))), name="ck_sop_cycle_horizon")),
        migrations.AddIndex(model_name="sandopcycle", index=models.Index(fields=["plant","cycle_month","status"], name="ix_sop_cycle_month_status")),
        migrations.CreateModel(
            name="SAndOPDemandConsensusLine",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")), ("created_at", models.DateTimeField(auto_now_add=True)), ("updated_at", models.DateTimeField(auto_now=True)),
                ("bucket_date", models.DateField()), ("baseline_forecast_quantity", models.DecimalField(decimal_places=4, default=0, max_digits=22)),
                ("open_order_quantity", models.DecimalField(decimal_places=4, default=0, max_digits=22)), ("commercial_adjustment_quantity", models.DecimalField(decimal_places=4, default=0, max_digits=22)),
                ("consensus_quantity", models.DecimalField(decimal_places=4, default=0, max_digits=22)), ("rationale", models.TextField(blank=True)),
                ("cycle", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="demand_lines", to="integrated_scheduling.sandopcycle")),
                ("item", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name="sop_demand_lines", to="masterdata.item")),
            ], options={"ordering":["bucket_date","item__code"]},
        ),
        migrations.AddConstraint(model_name="sandopdemandconsensusline", constraint=models.UniqueConstraint(fields=("cycle","item","bucket_date"), name="uq_sop_demand_bucket")),
        migrations.AddIndex(model_name="sandopdemandconsensusline", index=models.Index(fields=["cycle","bucket_date"], name="ix_sop_demand_cycle_bucket")),
        migrations.CreateModel(
            name="SAndOPSupplyPlanLine",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")), ("created_at", models.DateTimeField(auto_now_add=True)), ("updated_at", models.DateTimeField(auto_now=True)),
                ("bucket_date", models.DateField()), ("demand_quantity", models.DecimalField(decimal_places=4, default=0, max_digits=22)),
                ("opening_inventory_quantity", models.DecimalField(decimal_places=4, default=0, max_digits=22)), ("planned_supply_quantity", models.DecimalField(decimal_places=4, default=0, max_digits=22)),
                ("capacity_constrained_quantity", models.DecimalField(decimal_places=4, default=0, max_digits=22)), ("projected_ending_inventory_quantity", models.DecimalField(decimal_places=4, default=0, max_digits=22)),
                ("gap_quantity", models.DecimalField(decimal_places=4, default=0, max_digits=22)), ("notes", models.TextField(blank=True)),
                ("cycle", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="supply_lines", to="integrated_scheduling.sandopcycle")),
                ("item", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name="sop_supply_lines", to="masterdata.item")),
            ], options={"ordering":["bucket_date","item__code"]},
        ),
        migrations.AddConstraint(model_name="sandopsupplyplanline", constraint=models.UniqueConstraint(fields=("cycle","item","bucket_date"), name="uq_sop_supply_bucket")),
        migrations.AddIndex(model_name="sandopsupplyplanline", index=models.Index(fields=["cycle","bucket_date"], name="ix_sop_supply_cycle_bucket")),
        migrations.CreateModel(
            name="SAndOPConstraint",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")), ("created_at", models.DateTimeField(auto_now_add=True)), ("updated_at", models.DateTimeField(auto_now=True)),
                ("category", models.CharField(choices=[("MATERIAL","Material"),("CAPACITY","Capacidade"),("LABOR","Mão de obra"),("MAINTENANCE","Manutenção"),("SUPPLIER","Fornecedor"),("SERVICE","Serviço"),("FINANCIAL","Financeiro"),("OTHER","Outro")], max_length=20)),
                ("severity", models.CharField(choices=[("LOW","Baixa"),("MEDIUM","Média"),("HIGH","Alta"),("CRITICAL","Crítica")], default="MEDIUM", max_length=12)),
                ("title", models.CharField(max_length=180)), ("description", models.TextField(blank=True)), ("impact", models.JSONField(blank=True, default=dict)), ("mitigation", models.TextField(blank=True)),
                ("status", models.CharField(choices=[("OPEN","Aberta"),("MITIGATED","Mitigada"),("ACCEPTED","Aceita"),("CLOSED","Encerrada")], default="OPEN", max_length=12)),
                ("cycle", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="constraints_register", to="integrated_scheduling.sandopcycle")),
                ("owner", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="sop_constraints_owned", to=settings.AUTH_USER_MODEL)),
            ], options={"ordering":["-severity","category","title"]},
        ),
        migrations.AddIndex(model_name="sandopconstraint", index=models.Index(fields=["cycle","status","severity"], name="ix_sop_constraint_status")),
        migrations.CreateModel(
            name="SAndOPDecision",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")), ("created_at", models.DateTimeField(auto_now_add=True)), ("updated_at", models.DateTimeField(auto_now=True)),
                ("category", models.CharField(choices=[("DEMAND","Demanda"),("SUPPLY","Suprimento"),("CAPACITY","Capacidade"),("INVENTORY","Estoque"),("SERVICE","Nível de serviço"),("COMMERCIAL","Comercial"),("FINANCIAL","Financeiro"),("OTHER","Outro")], max_length=20)),
                ("title", models.CharField(max_length=180)), ("decision", models.TextField()), ("due_date", models.DateField(blank=True, null=True)),
                ("status", models.CharField(choices=[("OPEN","Aberta"),("DONE","Concluída"),("CANCELLED","Cancelada")], default="OPEN", max_length=12)),
                ("cycle", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="decisions", to="integrated_scheduling.sandopcycle")),
                ("owner", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="sop_decisions_owned", to=settings.AUTH_USER_MODEL)),
            ], options={"ordering":["status","due_date","title"]},
        ),
        migrations.AddIndex(model_name="sandopdecision", index=models.Index(fields=["cycle","status","due_date"], name="ix_sop_decision_status")),
        migrations.CreateModel(
            name="SAndOPPublication",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")), ("created_at", models.DateTimeField(auto_now_add=True)), ("updated_at", models.DateTimeField(auto_now=True)),
                ("mps_source", models.CharField(max_length=60)), ("mps_lines", models.PositiveIntegerField(default=0)), ("published_at", models.DateTimeField(default=django.utils.timezone.now)), ("details", models.JSONField(blank=True, default=dict)),
                ("cycle", models.OneToOneField(on_delete=django.db.models.deletion.CASCADE, related_name="publication", to="integrated_scheduling.sandopcycle")),
                ("planning_run", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="sop_publications", to="planning.planningrun")),
                ("published_by", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="sop_publications_created", to=settings.AUTH_USER_MODEL)),
            ], options={"ordering":["-published_at"]},
        ),
    ]
