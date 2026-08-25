from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion
import django.utils.timezone


class Migration(migrations.Migration):
    dependencies = [
        ('integrated_scheduling', '0037_mps_security_compliance_096'),
        ('common', '0001_initial'),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name='MPSComplianceEscalationPolicy',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('created_at', models.DateTimeField(auto_now_add=True)),('updated_at', models.DateTimeField(auto_now=True)),
                ('is_active', models.BooleanField(default=True)),('repeat_notifications', models.BooleanField(default=True)),
                ('repeat_interval_minutes', models.PositiveIntegerField(default=60)),('max_repeat_notifications', models.PositiveIntegerField(default=6)),
                ('use_on_call_contacts', models.BooleanField(default=True)),('send_email', models.BooleanField(default=True)),('notes', models.TextField(blank=True)),
                ('plant', models.OneToOneField(on_delete=django.db.models.deletion.CASCADE, related_name='mps_compliance_escalation_policy', to='common.plant')),
            ], options={'ordering':['plant__code']},
        ),
        migrations.CreateModel(
            name='MPSComplianceEscalationRule',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('created_at', models.DateTimeField(auto_now_add=True)),('updated_at', models.DateTimeField(auto_now=True)),
                ('name', models.CharField(max_length=120)),('level', models.CharField(choices=[('TEAM','Equipe'),('MANAGER','Gerente'),('DIRECTOR','Diretor'),('EXECUTIVE','Executivo')], max_length=16)),
                ('order', models.PositiveIntegerField(default=10)),('after_minutes', models.PositiveIntegerField(help_text='Minutos desde first_seen_at para ativar a regra.')),
                ('severities', models.JSONField(blank=True, default=list, help_text='LOW/MEDIUM/HIGH/CRITICAL; vazio = todas.')),
                ('categories', models.JSONField(blank=True, default=list, help_text='Categorias de incidente; vazio = todas.')),
                ('recipient_emails', models.JSONField(blank=True, default=list)),('recipient_groups', models.JSONField(blank=True, default=list, help_text='Grupos Django cujos usuários ativos com e-mail serão avisados.')),
                ('repeat_interval_minutes', models.PositiveIntegerField(blank=True, help_text='Override da política.', null=True)),('max_notifications', models.PositiveIntegerField(blank=True, help_text='Override da política.', null=True)),('is_active', models.BooleanField(default=True)),
                ('policy', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='rules', to='integrated_scheduling.mpscomplianceescalationpolicy')),
            ], options={'ordering':['policy__plant__code','order','after_minutes','id']},
        ),
        migrations.AddConstraint(model_name='mpscomplianceescalationrule', constraint=models.UniqueConstraint(fields=('policy','order'), name='uq_mpscomp_esc_rule_order')),
        migrations.CreateModel(
            name='MPSComplianceOnCallContact',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('created_at', models.DateTimeField(auto_now_add=True)),('updated_at', models.DateTimeField(auto_now=True)),
                ('name', models.CharField(max_length=120)),('email', models.EmailField(max_length=254)),('levels', models.JSONField(blank=True, default=list, help_text='Níveis atendidos; vazio = todos.')),
                ('weekdays', models.JSONField(blank=True, default=list, help_text='0=segunda ... 6=domingo; vazio = todos.')),('start_time', models.TimeField(blank=True, null=True)),('end_time', models.TimeField(blank=True, null=True)),('is_active', models.BooleanField(default=True)),
                ('plant', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='mps_compliance_on_call_contacts', to='common.plant')),
            ], options={'ordering':['plant__code','name']},
        ),
        migrations.AddIndex(model_name='mpscomplianceoncallcontact', index=models.Index(fields=['plant','is_active'], name='ix_mpscomp_oncall')),
        migrations.CreateModel(
            name='MPSComplianceEscalationEvent',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('created_at', models.DateTimeField(auto_now_add=True)),('updated_at', models.DateTimeField(auto_now=True)),
                ('level', models.CharField(choices=[('TEAM','Equipe'),('MANAGER','Gerente'),('DIRECTOR','Diretor'),('EXECUTIVE','Executivo')], max_length=16)),('status', models.CharField(choices=[('ACTIVE','Ativo'),('STOPPED','Encerrado')], default='ACTIVE', max_length=16)),
                ('activated_at', models.DateTimeField(default=django.utils.timezone.now)),('first_notified_at', models.DateTimeField(blank=True, null=True)),('last_notified_at', models.DateTimeField(blank=True, null=True)),('notification_count', models.PositiveIntegerField(default=0)),
                ('recipients', models.JSONField(blank=True, default=list)),('details', models.JSONField(blank=True, default=dict)),('stopped_at', models.DateTimeField(blank=True, null=True)),
                ('incident', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='escalation_events', to='integrated_scheduling.mpsdecisioncomplianceincident')),
                ('rule', models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name='events', to='integrated_scheduling.mpscomplianceescalationrule')),
            ], options={'ordering':['-activated_at','-id']},
        ),
        migrations.AddConstraint(model_name='mpscomplianceescalationevent', constraint=models.UniqueConstraint(fields=('incident','rule'), name='uq_mpscomp_inc_rule_event')),
        migrations.AddIndex(model_name='mpscomplianceescalationevent', index=models.Index(fields=['status','level','activated_at'], name='ix_mpscomp_esc_active')),
    ]
