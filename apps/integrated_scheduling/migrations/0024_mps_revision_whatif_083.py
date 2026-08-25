from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion

class Migration(migrations.Migration):
    dependencies=[
        ('integrated_scheduling','0023_mps_revisioning_082'),
        ('planning','0002_demand_pegging_allocation_073'),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]
    operations=[
        migrations.AddField(
            model_name='mpsoperationalpolicy', name='require_mrp_whatif_before_approval',
            field=models.BooleanField(default=True),
        ),
        migrations.CreateModel(
            name='MPSRevisionSimulation',
            fields=[
                ('id',models.BigAutoField(auto_created=True,primary_key=True,serialize=False,verbose_name='ID')),
                ('created_at',models.DateTimeField(auto_now_add=True)),('updated_at',models.DateTimeField(auto_now=True)),
                ('status',models.CharField(choices=[('DRAFT','Rascunho'),('RUNNING','Executando'),('COMPLETED','Concluída'),('FAILED','Falhou')],default='DRAFT',max_length=12)),
                ('summary',models.JSONField(blank=True,default=dict)),('diff_summary',models.JSONField(blank=True,default=dict)),
                ('started_at',models.DateTimeField(blank=True,null=True)),('completed_at',models.DateTimeField(blank=True,null=True)),('error_message',models.TextField(blank=True)),
                ('compare_planning_run',models.ForeignKey(blank=True,null=True,on_delete=django.db.models.deletion.SET_NULL,related_name='mps_revision_compare_simulations',to='planning.planningrun')),
                ('target_planning_run',models.ForeignKey(blank=True,null=True,on_delete=django.db.models.deletion.SET_NULL,related_name='mps_revision_target_simulations',to='planning.planningrun')),
                ('compare_revision',models.ForeignKey(on_delete=django.db.models.deletion.PROTECT,related_name='mrp_comparisons_as_baseline',to='integrated_scheduling.mpsrevision')),
                ('revision',models.ForeignKey(on_delete=django.db.models.deletion.CASCADE,related_name='mrp_simulations',to='integrated_scheduling.mpsrevision')),
                ('created_by',models.ForeignKey(blank=True,null=True,on_delete=django.db.models.deletion.SET_NULL,related_name='mps_revision_simulations_created',to=settings.AUTH_USER_MODEL)),
            ],
            options={'ordering':['-created_at']},
        ),
        migrations.AddIndex(model_name='mpsrevisionsimulation',index=models.Index(fields=['revision','status'],name='ix_mpssim_rev_status')),
        migrations.CreateModel(
            name='MPSRevisionSimulationDiffLine',
            fields=[
                ('id',models.BigAutoField(auto_created=True,primary_key=True,serialize=False,verbose_name='ID')),
                ('created_at',models.DateTimeField(auto_now_add=True)),('updated_at',models.DateTimeField(auto_now=True)),
                ('diff_type',models.CharField(choices=[('MAKE','OP planejada'),('PURCHASE','Compra planejada'),('SHORTAGE','Falta / exceção'),('PEGGING','Pegging')],max_length=12)),
                ('event_date',models.DateField(blank=True,null=True)),('reference_key',models.CharField(max_length=180)),
                ('left_quantity',models.DecimalField(decimal_places=4,default=0,max_digits=22)),('right_quantity',models.DecimalField(decimal_places=4,default=0,max_digits=22)),('delta_quantity',models.DecimalField(decimal_places=4,default=0,max_digits=22)),
                ('details',models.JSONField(blank=True,default=dict)),
                ('item',models.ForeignKey(blank=True,null=True,on_delete=django.db.models.deletion.PROTECT,related_name='mps_simulation_diffs',to='masterdata.item')),
                ('simulation',models.ForeignKey(on_delete=django.db.models.deletion.CASCADE,related_name='diff_lines',to='integrated_scheduling.mpsrevisionsimulation')),
            ],
            options={'ordering':['diff_type','event_date','reference_key']},
        ),
        migrations.AddIndex(model_name='mpsrevisionsimulationdiffline',index=models.Index(fields=['simulation','diff_type'],name='ix_mpssimdiff_type')),
        migrations.AddConstraint(model_name='mpsrevisionsimulationdiffline',constraint=models.UniqueConstraint(fields=('simulation','diff_type','reference_key'),name='uq_mpssimdiff_key')),
    ]
