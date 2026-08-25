from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion
import django.utils.timezone

class Migration(migrations.Migration):
    dependencies = [
        ('integrated_scheduling', '0036_mps_anchor_policy_095'),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]
    operations = [
        migrations.RemoveConstraint(model_name='mpsdecisionauditanchor', name='uq_mpsdec_anchor_point'),
        migrations.AddConstraint(model_name='mpsdecisionauditanchor', constraint=models.UniqueConstraint(fields=('cockpit','provider','anchored_sequence','anchored_head_hash'), name='uq_mpsdec_anchor_provider_point')),
        migrations.CreateModel(
            name='MPSDecisionCompliancePolicy',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('created_at', models.DateTimeField(auto_now_add=True)), ('updated_at', models.DateTimeField(auto_now=True)),
                ('is_active', models.BooleanField(default=True)), ('alert_recipients', models.JSONField(blank=True, default=list)),
                ('alert_statuses', models.JSONField(blank=True, default=list)), ('standard_sla_hours', models.PositiveIntegerField(default=24)),
                ('high_sla_hours', models.PositiveIntegerField(default=12)), ('critical_sla_hours', models.PositiveIntegerField(default=4)),
                ('auto_export_evidence', models.BooleanField(default=True)), ('evidence_max_age_hours', models.PositiveIntegerField(default=168)),
                ('send_email_alerts', models.BooleanField(default=True)), ('snapshot_retention_days', models.PositiveIntegerField(default=1095)),
                ('notes', models.TextField(blank=True)),
                ('plant', models.OneToOneField(on_delete=django.db.models.deletion.CASCADE, related_name='mps_decision_compliance_policy', to='common.plant')),
            ], options={'ordering':['plant__code']}
        ),
        migrations.CreateModel(
            name='MPSDecisionComplianceIncident',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('created_at', models.DateTimeField(auto_now_add=True)), ('updated_at', models.DateTimeField(auto_now=True)),
                ('category', models.CharField(choices=[('STALE','Âncora vencida'),('UNPROTECTED','Sem proteção'),('MISMATCH','Divergência de integridade'),('SLA_BREACH','SLA de proteção excedido'),('EVIDENCE_STALE','Evidência periódica vencida')], max_length=24)),
                ('severity', models.CharField(choices=[('LOW','Baixa'),('MEDIUM','Média'),('HIGH','Alta'),('CRITICAL','Crítica')], default='MEDIUM', max_length=16)),
                ('status', models.CharField(choices=[('OPEN','Aberto'),('ACKNOWLEDGED','Reconhecido'),('RESOLVED','Resolvido')], default='OPEN', max_length=16)),
                ('first_seen_at', models.DateTimeField(default=django.utils.timezone.now)), ('last_seen_at', models.DateTimeField(default=django.utils.timezone.now)),
                ('message', models.TextField()), ('details', models.JSONField(blank=True, default=dict)), ('alerted_at', models.DateTimeField(blank=True, null=True)),
                ('acknowledged_at', models.DateTimeField(blank=True, null=True)), ('resolved_at', models.DateTimeField(blank=True, null=True)),
                ('acknowledged_by', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='acknowledged_mps_compliance_incidents', to=settings.AUTH_USER_MODEL)),
                ('cockpit', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='compliance_incidents', to='integrated_scheduling.mpsdecisioncockpit')),
            ], options={'ordering':['status','-severity','-last_seen_at']}
        ),
        migrations.AddIndex(model_name='mpsdecisioncomplianceincident', index=models.Index(fields=['status','severity','last_seen_at'], name='ix_mpscomp_inc_status')),
        migrations.AddIndex(model_name='mpsdecisioncomplianceincident', index=models.Index(fields=['cockpit','category','status'], name='ix_mpscomp_inc_cockpit')),
        migrations.CreateModel(
            name='MPSDecisionComplianceSnapshot',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('created_at', models.DateTimeField(auto_now_add=True)), ('updated_at', models.DateTimeField(auto_now=True)),
                ('snapshot_date', models.DateField()), ('monitored_count', models.PositiveIntegerField(default=0)), ('protected_count', models.PositiveIntegerField(default=0)),
                ('stale_count', models.PositiveIntegerField(default=0)), ('unprotected_count', models.PositiveIntegerField(default=0)), ('mismatch_count', models.PositiveIntegerField(default=0)),
                ('protected_percent', models.DecimalField(decimal_places=2, default=0, max_digits=7)), ('evidence_current_percent', models.DecimalField(decimal_places=2, default=0, max_digits=7)),
                ('avg_minutes_to_first_anchor', models.DecimalField(decimal_places=2, default=0, max_digits=12)), ('integrity_failures', models.PositiveIntegerField(default=0)),
                ('open_incidents', models.PositiveIntegerField(default=0)), ('details', models.JSONField(blank=True, default=dict)),
                ('plant', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='mps_decision_compliance_snapshots', to='common.plant')),
            ], options={'ordering':['-snapshot_date','plant__code']}
        ),
        migrations.AddConstraint(model_name='mpsdecisioncompliancesnapshot', constraint=models.UniqueConstraint(fields=('plant','snapshot_date'), name='uq_mpscomp_snapshot_day')),
        migrations.AddIndex(model_name='mpsdecisioncompliancesnapshot', index=models.Index(fields=['plant','snapshot_date'], name='ix_mpscomp_snapshot_day')),
    ]
