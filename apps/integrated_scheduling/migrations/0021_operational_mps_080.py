from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion
import django.utils.timezone

class Migration(migrations.Migration):
    dependencies=[
        ('integrated_scheduling','0020_sop_cycle_079'),
        ('demand','0004_sales_line_price_078'),
        ('planning','0001_initial'),
        ('masterdata','0001_initial'),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]
    operations=[
        migrations.CreateModel(
            name='MPSOperationalPolicy',
            fields=[
                ('id',models.BigAutoField(auto_created=True,primary_key=True,serialize=False,verbose_name='ID')),
                ('created_at',models.DateTimeField(auto_now_add=True)),('updated_at',models.DateTimeField(auto_now=True)),
                ('bucket_days',models.PositiveSmallIntegerField(default=7)),('demand_time_fence_days',models.PositiveIntegerField(default=14)),('planning_time_fence_days',models.PositiveIntegerField(default=42)),('require_rccp_clear',models.BooleanField(default=True)),('overload_tolerance_percent',models.DecimalField(decimal_places=3,default=0,max_digits=7)),('auto_create_planning_run',models.BooleanField(default=True)),
                ('plant',models.OneToOneField(on_delete=django.db.models.deletion.CASCADE,related_name='mps_operational_policy',to='common.plant')),
            ],
        ),
        migrations.CreateModel(
            name='OperationalMPSPublication',
            fields=[
                ('id',models.BigAutoField(auto_created=True,primary_key=True,serialize=False,verbose_name='ID')),
                ('created_at',models.DateTimeField(auto_now_add=True)),('updated_at',models.DateTimeField(auto_now=True)),
                ('status',models.CharField(choices=[('DRAFT','Rascunho'),('VALIDATED','Validado'),('BLOCKED','Bloqueado'),('PUBLISHED','Publicado'),('MRP_RUNNING','MRP executando'),('MRP_COMPLETED','MRP concluído'),('FAILED','Falhou')],default='DRAFT',max_length=20)),
                ('as_of_date',models.DateField(default=django.utils.timezone.localdate)),('horizon_start',models.DateField()),('horizon_end',models.DateField()),('source',models.CharField(max_length=80,unique=True)),('summary',models.JSONField(blank=True,default=dict)),('validation_summary',models.JSONField(blank=True,default=dict)),('published_at',models.DateTimeField(blank=True,null=True)),('mrp_started_at',models.DateTimeField(blank=True,null=True)),('mrp_completed_at',models.DateTimeField(blank=True,null=True)),('error_message',models.TextField(blank=True)),
                ('cycle',models.ForeignKey(on_delete=django.db.models.deletion.PROTECT,related_name='operational_mps_publications',to='integrated_scheduling.sandopcycle')),
                ('policy',models.ForeignKey(on_delete=django.db.models.deletion.PROTECT,related_name='publications',to='integrated_scheduling.mpsoperationalpolicy')),
                ('planning_run',models.ForeignKey(blank=True,null=True,on_delete=django.db.models.deletion.SET_NULL,related_name='operational_mps_publications',to='planning.planningrun')),
                ('created_by',models.ForeignKey(blank=True,null=True,on_delete=django.db.models.deletion.SET_NULL,related_name='operational_mps_publications_created',to=settings.AUTH_USER_MODEL)),
                ('published_by',models.ForeignKey(blank=True,null=True,on_delete=django.db.models.deletion.SET_NULL,related_name='operational_mps_publications_published',to=settings.AUTH_USER_MODEL)),
            ],options={'ordering':['-created_at']},
        ),
        migrations.CreateModel(
            name='MPSWeeklyBucket',
            fields=[
                ('id',models.BigAutoField(auto_created=True,primary_key=True,serialize=False,verbose_name='ID')),
                ('created_at',models.DateTimeField(auto_now_add=True)),('updated_at',models.DateTimeField(auto_now=True)),('bucket_start',models.DateField()),('bucket_end',models.DateField()),('quantity',models.DecimalField(decimal_places=4,max_digits=22)),('source_demand_quantity',models.DecimalField(decimal_places=4,default=0,max_digits=22)),('source_supply_quantity',models.DecimalField(decimal_places=4,default=0,max_digits=22)),('mps_status',models.CharField(choices=[('PLANNED','Planejado'),('FIRM','Firme'),('FROZEN','Congelado')],default='PLANNED',max_length=15)),('frozen_reason',models.CharField(blank=True,max_length=160)),
                ('item',models.ForeignKey(on_delete=django.db.models.deletion.PROTECT,related_name='operational_mps_buckets',to='masterdata.item')),
                ('publication',models.ForeignKey(on_delete=django.db.models.deletion.CASCADE,related_name='weekly_buckets',to='integrated_scheduling.operationalmpspublication')),
                ('published_mps',models.ForeignKey(blank=True,null=True,on_delete=django.db.models.deletion.SET_NULL,related_name='operational_weekly_buckets',to='demand.masterproductionschedule')),
            ],options={'ordering':['bucket_start','item__code']},
        ),
        migrations.CreateModel(
            name='MPSRCCPException',
            fields=[
                ('id',models.BigAutoField(auto_created=True,primary_key=True,serialize=False,verbose_name='ID')),
                ('created_at',models.DateTimeField(auto_now_add=True)),('updated_at',models.DateTimeField(auto_now=True)),('bucket_start',models.DateField()),('required_hours',models.DecimalField(decimal_places=4,default=0,max_digits=18)),('available_hours',models.DecimalField(decimal_places=4,default=0,max_digits=18)),('overload_hours',models.DecimalField(decimal_places=4,default=0,max_digits=18)),('overload_percent',models.DecimalField(decimal_places=3,default=0,max_digits=10)),('severity',models.CharField(choices=[('INFO','Informação'),('WARNING','Atenção'),('CRITICAL','Crítica')],default='WARNING',max_length=10)),('status',models.CharField(choices=[('OPEN','Aberta'),('ACCEPTED','Aceita'),('RESOLVED','Resolvida')],default='OPEN',max_length=12)),('message',models.TextField(blank=True)),('details',models.JSONField(blank=True,default=dict)),
                ('publication',models.ForeignKey(on_delete=django.db.models.deletion.CASCADE,related_name='rccp_exceptions',to='integrated_scheduling.operationalmpspublication')),
                ('work_center',models.ForeignKey(on_delete=django.db.models.deletion.PROTECT,related_name='mps_rccp_exceptions',to='masterdata.workcenter')),
            ],options={'ordering':['-severity','bucket_start','work_center__code']},
        ),
        migrations.AddConstraint(model_name='mpsoperationalpolicy',constraint=models.CheckConstraint(condition=models.Q(('bucket_days__gt',0)),name='ck_mpsop_bucket_pos')),
        migrations.AddConstraint(model_name='mpsoperationalpolicy',constraint=models.CheckConstraint(condition=models.Q(('planning_time_fence_days__gte',models.F('demand_time_fence_days'))),name='ck_mpsop_fences_order')),
        migrations.AddConstraint(model_name='mpsoperationalpolicy',constraint=models.CheckConstraint(condition=models.Q(('overload_tolerance_percent__gte',0)),name='ck_mpsop_tol_nonneg')),
        migrations.AddConstraint(model_name='operationalmpspublication',constraint=models.CheckConstraint(condition=models.Q(('horizon_end__gte',models.F('horizon_start'))),name='ck_opmps_horizon')),
        migrations.AddIndex(model_name='operationalmpspublication',index=models.Index(fields=['cycle','status'],name='ix_opmps_cycle_status')),
        migrations.AddConstraint(model_name='mpsweeklybucket',constraint=models.UniqueConstraint(fields=('publication','item','bucket_start'),name='uq_opmps_week_item')),
        migrations.AddConstraint(model_name='mpsweeklybucket',constraint=models.CheckConstraint(condition=models.Q(('quantity__gte',0)),name='ck_opmps_week_qty_nonneg')),
        migrations.AddConstraint(model_name='mpsweeklybucket',constraint=models.CheckConstraint(condition=models.Q(('bucket_end__gte',models.F('bucket_start'))),name='ck_opmps_week_dates')),
        migrations.AddIndex(model_name='mpsweeklybucket',index=models.Index(fields=['publication','bucket_start','mps_status'],name='ix_opmps_week_status')),
        migrations.AddConstraint(model_name='mpsrccpexception',constraint=models.UniqueConstraint(fields=('publication','work_center','bucket_start'),name='uq_mpsrccp_center_week')),
        migrations.AddIndex(model_name='mpsrccpexception',index=models.Index(fields=['publication','status','severity'],name='ix_mpsrccp_status')),
    ]
