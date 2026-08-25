from django.db import migrations, models
import django.db.models.deletion

class Migration(migrations.Migration):
    dependencies=[('integrated_scheduling','0035_mps_decision_external_anchor_094'),('common','0001_initial')]
    operations=[
      migrations.AlterField(model_name='mpsdecisionauditanchor',name='provider',field=models.CharField(choices=[('FILE_APPEND_ONLY','Arquivo append-only primário'),('FILE_SECONDARY','Arquivo append-only secundário'),('MANUAL_EXTERNAL','Âncora externa manual')],default='FILE_APPEND_ONLY',max_length=32)),
      migrations.CreateModel(
        name='MPSDecisionAnchorPolicy',
        fields=[
          ('id',models.BigAutoField(auto_created=True,primary_key=True,serialize=False,verbose_name='ID')),
          ('created_at',models.DateTimeField(auto_now_add=True)),('updated_at',models.DateTimeField(auto_now=True)),
          ('is_active',models.BooleanField(default=True)),
          ('cadence',models.CharField(choices=[('ON_FREEZE','Ao congelar plano'),('DAILY','Diária'),('BOTH','Ao congelar + diária')],default='BOTH',max_length=16)),
          ('required_providers',models.JSONField(blank=True,default=list,help_text='Providers independentes exigidos para considerar a decisão protegida.')),
          ('max_anchor_age_hours',models.PositiveIntegerField(default=24)),('retention_days',models.PositiveIntegerField(default=3650)),
          ('verify_after_publish',models.BooleanField(default=True)),('protect_active_cockpits',models.BooleanField(default=False)),('notes',models.TextField(blank=True)),
          ('plant',models.OneToOneField(on_delete=django.db.models.deletion.CASCADE,related_name='mps_decision_anchor_policy',to='common.plant')),
        ],options={'ordering':['plant__code']}),
    ]
