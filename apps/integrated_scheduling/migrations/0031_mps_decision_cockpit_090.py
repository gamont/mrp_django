from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion

class Migration(migrations.Migration):
    dependencies = [
        ("integrated_scheduling", "0030_mps_pareto_optimizer_089"),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]
    operations = [
        migrations.CreateModel(
            name="MPSDecisionCockpit",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("status", models.CharField(choices=[("OPEN","Aberto"),("SELECTED","Cenário selecionado"),("PENDING_APPROVAL","Aguardando aprovação executiva"),("APPROVED","Aprovado"),("FROZEN","Congelado como plano oficial"),("REJECTED","Rejeitado")], default="OPEN", max_length=20)),
                ("selection_rationale", models.TextField(blank=True)),
                ("executive_notes", models.TextField(blank=True)),
                ("decision_snapshot", models.JSONField(blank=True, default=dict)),
                ("approved_at", models.DateTimeField(blank=True, null=True)),
                ("frozen_at", models.DateTimeField(blank=True, null=True)),
                ("selected_at", models.DateTimeField(blank=True, null=True)),
                ("submitted_at", models.DateTimeField(blank=True, null=True)),
                ("approved_by", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="mps_decision_cockpits_approved", to=settings.AUTH_USER_MODEL)),
                ("baseline_revision", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name="decision_cockpit_baselines", to="integrated_scheduling.mpsrevision")),
                ("created_by", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="mps_decision_cockpits_created", to=settings.AUTH_USER_MODEL)),
                ("frozen_by", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="mps_decision_cockpits_frozen", to=settings.AUTH_USER_MODEL)),
                ("official_revision", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.PROTECT, related_name="official_decision_cockpits", to="integrated_scheduling.mpsrevision")),
                ("optimization_run", models.OneToOneField(on_delete=django.db.models.deletion.PROTECT, related_name="decision_cockpit", to="integrated_scheduling.mpsrevisionoptimizationrun")),
                ("publication", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="decision_cockpits", to="integrated_scheduling.operationalmpspublication")),
                ("selected_by", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="mps_decision_cockpits_selected", to=settings.AUTH_USER_MODEL)),
                ("selected_candidate", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.PROTECT, related_name="decision_cockpits_selected", to="integrated_scheduling.mpsrevisionoptimizationcandidate")),
                ("submitted_by", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="mps_decision_cockpits_submitted", to=settings.AUTH_USER_MODEL)),
            ],
            options={"ordering":["-created_at"]},
        ),
        migrations.CreateModel(
            name="MPSDecisionCandidateReview",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("shortlisted", models.BooleanField(default=False)),
                ("business_label", models.CharField(blank=True, max_length=120)),
                ("executive_note", models.TextField(blank=True)),
                ("priority", models.PositiveIntegerField(default=0)),
                ("candidate", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="decision_reviews", to="integrated_scheduling.mpsrevisionoptimizationcandidate")),
                ("cockpit", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="candidate_reviews", to="integrated_scheduling.mpsdecisioncockpit")),
                ("reviewed_at", models.DateTimeField(blank=True, null=True)),
                ("reviewed_by", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="mps_decision_candidate_reviews", to=settings.AUTH_USER_MODEL)),
            ],
            options={"ordering":["-shortlisted","priority","candidate__pareto_rank","candidate__rank","id"]},
        ),
        migrations.AddConstraint(model_name="mpsdecisioncandidatereview", constraint=models.UniqueConstraint(fields=("cockpit","candidate"), name="uq_mpsdec_cockpit_candidate")),
        migrations.AddIndex(model_name="mpsdecisioncockpit", index=models.Index(fields=["publication","status"], name="ix_mpsdec_pub_status")),
        migrations.AddIndex(model_name="mpsdecisioncandidatereview", index=models.Index(fields=["cockpit","shortlisted"], name="ix_mpsdec_review_short")),
    ]
