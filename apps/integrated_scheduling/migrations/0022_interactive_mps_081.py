from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion
import django.utils.timezone

class Migration(migrations.Migration):
    dependencies=[('integrated_scheduling','0021_operational_mps_080'), migrations.swappable_dependency(settings.AUTH_USER_MODEL)]
    operations=[
        migrations.AddField(model_name='mpsweeklybucket',name='baseline_quantity',field=models.DecimalField(decimal_places=4,default=0,max_digits=22)),
        migrations.CreateModel(
            name='MPSBucketChangeRequest',
            fields=[
                ('id',models.BigAutoField(auto_created=True,primary_key=True,serialize=False,verbose_name='ID')),
                ('created_at',models.DateTimeField(auto_now_add=True)),('updated_at',models.DateTimeField(auto_now=True)),
                ('source_quantity_before',models.DecimalField(decimal_places=4,max_digits=22)),('source_quantity_after',models.DecimalField(decimal_places=4,max_digits=22)),
                ('target_quantity_before',models.DecimalField(blank=True,decimal_places=4,max_digits=22,null=True)),('target_quantity_after',models.DecimalField(blank=True,decimal_places=4,max_digits=22,null=True)),
                ('violation',models.CharField(choices=[('NONE','Sem violação'),('DEMAND_TIME_FENCE','Demand time fence'),('FROZEN_BUCKET','Bucket congelado')],default='NONE',max_length=24)),
                ('status',models.CharField(choices=[('PENDING','Pendente'),('APPROVED','Aprovada'),('REJECTED','Rejeitada')],default='PENDING',max_length=12)),
                ('reason',models.TextField(blank=True)),('requested_at',models.DateTimeField(default=django.utils.timezone.now)),('decided_at',models.DateTimeField(blank=True,null=True)),('decision_notes',models.TextField(blank=True)),
                ('publication',models.ForeignKey(on_delete=django.db.models.deletion.CASCADE,related_name='bucket_change_requests',to='integrated_scheduling.operationalmpspublication')),
                ('source_bucket',models.ForeignKey(on_delete=django.db.models.deletion.CASCADE,related_name='change_requests_as_source',to='integrated_scheduling.mpsweeklybucket')),
                ('target_bucket',models.ForeignKey(blank=True,null=True,on_delete=django.db.models.deletion.CASCADE,related_name='change_requests_as_target',to='integrated_scheduling.mpsweeklybucket')),
                ('requested_by',models.ForeignKey(blank=True,null=True,on_delete=django.db.models.deletion.SET_NULL,related_name='mps_bucket_changes_requested',to=settings.AUTH_USER_MODEL)),
                ('decided_by',models.ForeignKey(blank=True,null=True,on_delete=django.db.models.deletion.SET_NULL,related_name='mps_bucket_changes_decided',to=settings.AUTH_USER_MODEL)),
            ],
            options={'ordering':['-requested_at']},
        ),
        migrations.AddIndex(model_name='mpsbucketchangerequest',index=models.Index(fields=['publication','status'],name='ix_mpschg_pub_status')),
    ]
