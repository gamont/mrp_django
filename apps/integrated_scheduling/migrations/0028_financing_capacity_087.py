from django.db import migrations, models
import django.db.models.deletion

class Migration(migrations.Migration):
    dependencies=[('integrated_scheduling','0027_working_capital_086'),('common','0001_initial')]
    operations=[
        migrations.CreateModel(
            name='FinancingPolicy',
            fields=[
                ('id',models.BigAutoField(auto_created=True,primary_key=True,serialize=False,verbose_name='ID')),
                ('created_at',models.DateTimeField(auto_now_add=True)),('updated_at',models.DateTimeField(auto_now=True)),
                ('block_revision_approval_when_exceeded',models.BooleanField(default=False)),
                ('max_financing_utilization_percent',models.DecimalField(decimal_places=4,default=100,max_digits=8)),
                ('notes',models.TextField(blank=True)),
                ('plant',models.OneToOneField(on_delete=django.db.models.deletion.CASCADE,related_name='financing_policy',to='common.plant')),
            ],
            options={'constraints':[models.CheckConstraint(condition=models.Q(max_financing_utilization_percent__gt=0),name='ck_finpol_util_gt0'),models.CheckConstraint(condition=models.Q(max_financing_utilization_percent__lte=100),name='ck_finpol_util_lte100')]},
        ),
        migrations.CreateModel(
            name='FinancingFacility',
            fields=[
                ('id',models.BigAutoField(auto_created=True,primary_key=True,serialize=False,verbose_name='ID')),
                ('created_at',models.DateTimeField(auto_now_add=True)),('updated_at',models.DateTimeField(auto_now=True)),
                ('code',models.CharField(max_length=40)),('name',models.CharField(max_length=140)),
                ('limit_amount',models.DecimalField(decimal_places=2,default=0,max_digits=24)),
                ('annual_interest_rate_percent',models.DecimalField(decimal_places=6,default=0,max_digits=10)),
                ('priority',models.PositiveIntegerField(default=100)),('effective_from',models.DateField(blank=True,null=True)),('effective_to',models.DateField(blank=True,null=True)),('is_active',models.BooleanField(default=True)),('notes',models.TextField(blank=True)),
                ('plant',models.ForeignKey(on_delete=django.db.models.deletion.CASCADE,related_name='financing_facilities',to='common.plant')),
            ],
            options={'ordering':['priority','code'],'constraints':[models.UniqueConstraint(fields=('plant','code'),name='uq_fin_facility_plant_code'),models.CheckConstraint(condition=models.Q(limit_amount__gte=0),name='ck_fin_facility_limit_nonneg'),models.CheckConstraint(condition=models.Q(annual_interest_rate_percent__gte=0),name='ck_fin_facility_rate_nonneg')],'indexes':[models.Index(fields=['plant','is_active','priority'],name='ix_fin_facility_active')]},
        ),
        migrations.CreateModel(
            name='MPSRevisionSimulationFinancingBucket',
            fields=[
                ('id',models.BigAutoField(auto_created=True,primary_key=True,serialize=False,verbose_name='ID')),
                ('created_at',models.DateTimeField(auto_now_add=True)),('updated_at',models.DateTimeField(auto_now=True)),('bucket_date',models.DateField()),
                ('left_required_financing',models.DecimalField(decimal_places=2,default=0,max_digits=24)),('right_required_financing',models.DecimalField(decimal_places=2,default=0,max_digits=24)),
                ('left_financing_outstanding',models.DecimalField(decimal_places=2,default=0,max_digits=24)),('right_financing_outstanding',models.DecimalField(decimal_places=2,default=0,max_digits=24)),
                ('left_available_credit',models.DecimalField(decimal_places=2,default=0,max_digits=24)),('right_available_credit',models.DecimalField(decimal_places=2,default=0,max_digits=24)),
                ('left_uncovered_need',models.DecimalField(decimal_places=2,default=0,max_digits=24)),('right_uncovered_need',models.DecimalField(decimal_places=2,default=0,max_digits=24)),
                ('left_interest_expense',models.DecimalField(decimal_places=2,default=0,max_digits=24)),('right_interest_expense',models.DecimalField(decimal_places=2,default=0,max_digits=24)),('details',models.JSONField(blank=True,default=dict)),
                ('simulation',models.ForeignKey(on_delete=django.db.models.deletion.CASCADE,related_name='financing_buckets',to='integrated_scheduling.mpsrevisionsimulation')),
            ],
            options={'ordering':['bucket_date'],'constraints':[models.UniqueConstraint(fields=('simulation','bucket_date'),name='uq_mpssim_fin_bucket')],'indexes':[models.Index(fields=['simulation','bucket_date'],name='ix_mpssim_fin_bucket')]},
        ),
    ]
