from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion

class Migration(migrations.Migration):
    dependencies=[('integrated_scheduling','0011_execution_publication_070'), migrations.swappable_dependency(settings.AUTH_USER_MODEL)]
    operations=[
        migrations.AddField(model_name='reschedulingtrigger',name='recovery_summary',field=models.JSONField(blank=True,default=dict)),
        migrations.AddField(model_name='reschedulingtrigger',name='auto_solver_enqueued_at',field=models.DateTimeField(blank=True,null=True)),
        migrations.AddField(model_name='reschedulingtrigger',name='approved_at',field=models.DateTimeField(blank=True,null=True)),
        migrations.AddField(model_name='reschedulingtrigger',name='approved_by',field=models.ForeignKey(blank=True,null=True,on_delete=django.db.models.deletion.SET_NULL,related_name='approved_rescheduling_triggers',to=settings.AUTH_USER_MODEL)),
        migrations.AlterField(model_name='reschedulingtrigger',name='status',field=models.CharField(choices=[('NEW','Novo'),('PROCESSING','Processando'),('RESCHEDULED','Cenário preparado'),('SOLVING','Otimizando'),('READY','Plano recuperado pronto'),('PUBLISHED','Plano recuperado publicado'),('IGNORED','Ignorado'),('FAILED','Falhou')],default='NEW',max_length=16)),
    ]
