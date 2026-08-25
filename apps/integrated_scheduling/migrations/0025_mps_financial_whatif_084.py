from django.db import migrations, models
import django.db.models.deletion

class Migration(migrations.Migration):
    dependencies=[
        ('integrated_scheduling','0024_mps_revision_whatif_083'),
        ('costing','0006_period_close_reopen_audit'),
        ('masterdata','0001_initial'),
    ]
    operations=[
        migrations.AddField(model_name='mpsrevisionsimulation',name='cost_version',field=models.ForeignKey(blank=True,null=True,on_delete=django.db.models.deletion.SET_NULL,related_name='mps_revision_simulations',to='costing.costversion')),
        migrations.AddField(model_name='mpsrevisionsimulation',name='financial_summary',field=models.JSONField(blank=True,default=dict)),
        migrations.CreateModel(name='MPSRevisionSimulationFinancialLine',fields=[
            ('id',models.BigAutoField(primary_key=True,serialize=False)),('created_at',models.DateTimeField(auto_now_add=True)),('updated_at',models.DateTimeField(auto_now=True)),
            ('category',models.CharField(choices=[('PURCHASE_SPEND','Compras planejadas'),('MATERIAL_COST','Material MAKE'),('LABOR_COST','Mão de obra MAKE'),('MACHINE_COST','Máquina MAKE'),('OVERHEAD_COST','Overhead/setup MAKE'),('INVENTORY_EXPOSURE','Estoque projetado'),('WIP_PROXY','WIP planejado (proxy)'),('CASH_OUTFLOW_PROXY','Saída de caixa (proxy)')],max_length=32)),
            ('left_value',models.DecimalField(decimal_places=2,default=0,max_digits=24)),('right_value',models.DecimalField(decimal_places=2,default=0,max_digits=24)),('delta_value',models.DecimalField(decimal_places=2,default=0,max_digits=24)),('details',models.JSONField(blank=True,default=dict)),
            ('item',models.ForeignKey(blank=True,null=True,on_delete=django.db.models.deletion.PROTECT,related_name='mps_financial_whatif_lines',to='masterdata.item')),
            ('simulation',models.ForeignKey(on_delete=django.db.models.deletion.CASCADE,related_name='financial_lines',to='integrated_scheduling.mpsrevisionsimulation')),
        ],options={'ordering':['category','item__code']}),
        migrations.AddConstraint(model_name='mpsrevisionsimulationfinancialline',constraint=models.UniqueConstraint(fields=('simulation','category','item'),name='uq_mpssimfin_cat_item')),
        migrations.AddIndex(model_name='mpsrevisionsimulationfinancialline',index=models.Index(fields=['simulation','category'],name='ix_mpssimfin_category')),
    ]
