from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion
import django.utils.timezone

class Migration(migrations.Migration):
    dependencies=[('integrated_scheduling','0034_mps_decision_audit_093'),migrations.swappable_dependency(settings.AUTH_USER_MODEL)]
    operations=[
        migrations.CreateModel(
            name='MPSDecisionAuditAnchor',
            fields=[
                ('id',models.BigAutoField(auto_created=True,primary_key=True,serialize=False,verbose_name='ID')),
                ('created_at',models.DateTimeField(auto_now_add=True)),('updated_at',models.DateTimeField(auto_now=True)),
                ('provider',models.CharField(choices=[('FILE_APPEND_ONLY','Arquivo append-only externo'),('MANUAL_EXTERNAL','Âncora externa manual')],default='FILE_APPEND_ONLY',max_length=32)),
                ('anchored_sequence',models.PositiveIntegerField()),('anchored_head_hash',models.CharField(max_length=64)),
                ('anchored_at',models.DateTimeField(default=django.utils.timezone.now)),('external_reference',models.CharField(blank=True,max_length=500)),
                ('receipt',models.JSONField(blank=True,default=dict)),('receipt_hash',models.CharField(blank=True,max_length=64)),
                ('status',models.CharField(choices=[('ANCHORED','Ancorada'),('VERIFIED','Verificada'),('MISMATCH','Divergente'),('ERROR','Erro')],default='ANCHORED',max_length=16)),
                ('verified_at',models.DateTimeField(blank=True,null=True)),('verification_details',models.JSONField(blank=True,default=dict)),
                ('cockpit',models.ForeignKey(on_delete=django.db.models.deletion.CASCADE,related_name='audit_anchors',to='integrated_scheduling.mpsdecisioncockpit')),
                ('created_by',models.ForeignKey(blank=True,null=True,on_delete=django.db.models.deletion.SET_NULL,related_name='mps_decision_audit_anchors',to=settings.AUTH_USER_MODEL)),
            ],
            options={'ordering':['cockpit','anchored_sequence','id']},
        ),
        migrations.AddConstraint(model_name='mpsdecisionauditanchor',constraint=models.UniqueConstraint(fields=('cockpit','anchored_sequence','anchored_head_hash'),name='uq_mpsdec_anchor_point')),
        migrations.AddIndex(model_name='mpsdecisionauditanchor',index=models.Index(fields=['cockpit','anchored_sequence'],name='ix_mpsdec_anchor_seq')),
        migrations.AddIndex(model_name='mpsdecisionauditanchor',index=models.Index(fields=['status','anchored_at'],name='ix_mpsdec_anchor_status')),
    ]
