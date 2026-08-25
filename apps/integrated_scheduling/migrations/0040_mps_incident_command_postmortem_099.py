from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion
import django.utils.timezone


class Migration(migrations.Migration):
    dependencies = [
        ('integrated_scheduling', '0039_mps_escalation_calendar_098'),
        ('common', '0001_initial'),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name='MPSIncidentCommandPolicy',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('created_at', models.DateTimeField(auto_now_add=True)), ('updated_at', models.DateTimeField(auto_now=True)),
                ('is_active', models.BooleanField(default=True)),
                ('auto_promote_levels', models.JSONField(blank=True, default=list, help_text='Escalation levels that automatically create a major incident; empty defaults to EXECUTIVE.')),
                ('auto_promote_severities', models.JSONField(blank=True, default=list, help_text='Incident severities eligible for auto promotion; empty defaults to CRITICAL.')),
                ('require_postmortem_for', models.JSONField(blank=True, default=list, help_text='Major incident severities requiring approved postmortem before closure; empty defaults to SEV1/SEV2.')),
                ('notes', models.TextField(blank=True)),
                ('plant', models.OneToOneField(on_delete=django.db.models.deletion.CASCADE, related_name='mps_incident_command_policy', to='common.plant')),
            ],
            options={'ordering': ['plant__code']},
        ),
        migrations.CreateModel(
            name='MPSMajorIncident',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('created_at', models.DateTimeField(auto_now_add=True)), ('updated_at', models.DateTimeField(auto_now=True)),
                ('code', models.CharField(max_length=40, unique=True)),
                ('title', models.CharField(max_length=220)),
                ('severity', models.CharField(choices=[('SEV1','Crítico'),('SEV2','Alto'),('SEV3','Moderado'),('SEV4','Baixo')], default='SEV2', max_length=8)),
                ('status', models.CharField(choices=[('DETECTED','Detectado'),('ACTIVE','Em resposta'),('MONITORING','Monitorando'),('RESOLVED','Resolvido'),('CLOSED','Encerrado')], default='DETECTED', max_length=16)),
                ('summary', models.TextField(blank=True)), ('impact', models.TextField(blank=True)), ('war_room_url', models.URLField(blank=True)),
                ('started_at', models.DateTimeField(default=django.utils.timezone.now)), ('acknowledged_at', models.DateTimeField(blank=True, null=True)), ('resolved_at', models.DateTimeField(blank=True, null=True)), ('closed_at', models.DateTimeField(blank=True, null=True)),
                ('details', models.JSONField(blank=True, default=dict)),
                ('commander', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='commanded_mps_major_incidents', to=settings.AUTH_USER_MODEL)),
                ('closed_by', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='closed_mps_major_incidents', to=settings.AUTH_USER_MODEL)),
                ('plant', models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name='mps_major_incidents', to='common.plant')),
                ('compliance_incidents', models.ManyToManyField(blank=True, related_name='major_incidents', to='integrated_scheduling.mpsdecisioncomplianceincident')),
            ],
            options={'ordering': ['-started_at','-id']},
        ),
        migrations.AddIndex(model_name='mpsmajorincident', index=models.Index(fields=['plant','status','severity'], name='ix_mps_major_incident')),
        migrations.CreateModel(
            name='MPSMajorIncidentTimelineEvent',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('created_at', models.DateTimeField(auto_now_add=True)), ('updated_at', models.DateTimeField(auto_now=True)),
                ('event_type', models.CharField(choices=[('DETECTED','Detectado'),('COMMAND','Comando'),('UPDATE','Atualização'),('DECISION','Decisão'),('MITIGATION','Mitigação'),('ESCALATION','Escalonamento'),('RECOVERY','Recuperação'),('RESOLVED','Resolvido'),('CLOSED','Encerrado')], default='UPDATE', max_length=16)),
                ('occurred_at', models.DateTimeField(default=django.utils.timezone.now)), ('message', models.TextField()), ('details', models.JSONField(blank=True, default=dict)),
                ('actor', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='mps_major_incident_timeline_events', to=settings.AUTH_USER_MODEL)),
                ('incident', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='timeline', to='integrated_scheduling.mpsmajorincident')),
            ], options={'ordering':['occurred_at','id']},
        ),
        migrations.AddIndex(model_name='mpsmajorincidenttimelineevent', index=models.Index(fields=['incident','occurred_at'], name='ix_mps_major_timeline')),
        migrations.CreateModel(
            name='MPSMajorIncidentAction',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('created_at', models.DateTimeField(auto_now_add=True)), ('updated_at', models.DateTimeField(auto_now=True)),
                ('action_type', models.CharField(choices=[('CONTAINMENT','Contenção'),('CORRECTIVE','Corretiva'),('PREVENTIVE','Preventiva')], default='CORRECTIVE', max_length=16)),
                ('title', models.CharField(max_length=220)), ('description', models.TextField(blank=True)), ('due_at', models.DateTimeField(blank=True, null=True)),
                ('status', models.CharField(choices=[('OPEN','Aberta'),('IN_PROGRESS','Em andamento'),('DONE','Concluída'),('CANCELLED','Cancelada')], default='OPEN', max_length=16)),
                ('completed_at', models.DateTimeField(blank=True, null=True)), ('verification', models.TextField(blank=True)),
                ('incident', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='actions', to='integrated_scheduling.mpsmajorincident')),
                ('owner', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='owned_mps_major_incident_actions', to=settings.AUTH_USER_MODEL)),
            ], options={'ordering':['status','due_at','id']},
        ),
        migrations.AddIndex(model_name='mpsmajorincidentaction', index=models.Index(fields=['incident','status','due_at'], name='ix_mps_major_action')),
        migrations.CreateModel(
            name='MPSMajorIncidentPostmortem',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('created_at', models.DateTimeField(auto_now_add=True)), ('updated_at', models.DateTimeField(auto_now=True)),
                ('status', models.CharField(choices=[('DRAFT','Rascunho'),('REVIEW','Em revisão'),('APPROVED','Aprovado')], default='DRAFT', max_length=16)),
                ('executive_summary', models.TextField(blank=True)), ('root_cause', models.TextField(blank=True)), ('root_cause_category', models.CharField(blank=True, max_length=40)),
                ('five_whys', models.JSONField(blank=True, default=list)), ('contributing_factors', models.JSONField(blank=True, default=list)),
                ('what_went_well', models.TextField(blank=True)), ('what_went_wrong', models.TextField(blank=True)), ('lessons_learned', models.TextField(blank=True)), ('prevention_plan', models.TextField(blank=True)), ('approved_at', models.DateTimeField(blank=True, null=True)),
                ('incident', models.OneToOneField(on_delete=django.db.models.deletion.CASCADE, related_name='postmortem', to='integrated_scheduling.mpsmajorincident')),
                ('prepared_by', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='prepared_mps_postmortems', to=settings.AUTH_USER_MODEL)),
                ('approved_by', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='approved_mps_postmortems', to=settings.AUTH_USER_MODEL)),
            ], options={'ordering':['-created_at']},
        ),
        migrations.CreateModel(
            name='MPSMajorIncidentLearningAction',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('created_at', models.DateTimeField(auto_now_add=True)), ('updated_at', models.DateTimeField(auto_now=True)),
                ('target_type', models.CharField(choices=[('MRP_POLICY','Política MRP'),('MPS_POLICY','Política MPS'),('COMPLIANCE','Compliance'),('ESCALATION','Escalonamento'),('MASTER_DATA','Dados mestres'),('PROCESS','Processo')], max_length=24)),
                ('description', models.TextField()), ('status', models.CharField(choices=[('PROPOSED','Proposta'),('ACCEPTED','Aceita'),('APPLIED','Aplicada'),('REJECTED','Rejeitada')], default='PROPOSED', max_length=16)), ('applied_at', models.DateTimeField(blank=True, null=True)), ('evidence', models.TextField(blank=True)),
                ('owner', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='owned_mps_learning_actions', to=settings.AUTH_USER_MODEL)),
                ('postmortem', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='learning_actions', to='integrated_scheduling.mpsmajorincidentpostmortem')),
            ], options={'ordering':['status','id']},
        ),
    ]
