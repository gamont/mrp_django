from django.db import migrations, models
import django.db.models.deletion
import django.utils.timezone

class Migration(migrations.Migration):
    dependencies=[('integrated_scheduling','0017_otif_service_level_076'),('common','0001_initial')]
    operations=[
        migrations.CreateModel(name='ServiceLevelTarget', fields=[
            ('id',models.BigAutoField(auto_created=True,primary_key=True,serialize=False,verbose_name='ID')),
            ('created_at',models.DateTimeField(auto_now_add=True)),('updated_at',models.DateTimeField(auto_now=True)),
            ('scope',models.CharField(choices=[('PLANT','Planta'),('CUSTOMER','Cliente'),('FAMILY','Família'),('ITEM','Item')],default='PLANT',max_length=16)),
            ('scope_key',models.CharField(blank=True,max_length=80)),('scope_label',models.CharField(blank=True,max_length=180)),
            ('effective_from',models.DateField()),('effective_to',models.DateField(blank=True,null=True)),
            ('otif_target_pct',models.DecimalField(decimal_places=2,default=95,max_digits=6)),('on_time_target_pct',models.DecimalField(decimal_places=2,default=97,max_digits=6)),
            ('in_full_target_pct',models.DecimalField(decimal_places=2,default=98,max_digits=6)),('fill_rate_target_pct',models.DecimalField(decimal_places=2,default=98,max_digits=6)),
            ('perfect_order_target_pct',models.DecimalField(decimal_places=2,default=95,max_digits=6)),('late_day_cost',models.DecimalField(decimal_places=2,default=0,max_digits=18)),
            ('incomplete_unit_cost',models.DecimalField(decimal_places=4,default=0,max_digits=18)),('is_active',models.BooleanField(default=True)),
            ('plant',models.ForeignKey(on_delete=django.db.models.deletion.CASCADE,related_name='service_level_targets',to='common.plant')),
        ], options={'ordering':['plant__code','scope','scope_key','-effective_from']}),
        migrations.CreateModel(name='ServiceLevelPeriodSnapshot', fields=[
            ('id',models.BigAutoField(auto_created=True,primary_key=True,serialize=False,verbose_name='ID')),('created_at',models.DateTimeField(auto_now_add=True)),('updated_at',models.DateTimeField(auto_now=True)),
            ('reference',models.CharField(choices=[('REQUESTED','Solicitada'),('APPROVED_PROMISE','Promessa aprovada'),('CUSTOMER_ACCEPTED','Aceita pelo cliente')],default='CUSTOMER_ACCEPTED',max_length=24)),
            ('period_start',models.DateField()),('period_end',models.DateField()),('scope',models.CharField(choices=[('PLANT','Planta'),('CUSTOMER','Cliente'),('FAMILY','Família'),('ITEM','Item')],default='PLANT',max_length=16)),
            ('scope_key',models.CharField(blank=True,max_length=80)),('scope_label',models.CharField(blank=True,max_length=180)),('lines',models.PositiveIntegerField(default=0)),('orders',models.PositiveIntegerField(default=0)),
            ('ordered_quantity',models.DecimalField(decimal_places=4,default=0,max_digits=22)),('delivered_quantity',models.DecimalField(decimal_places=4,default=0,max_digits=22)),('overdue_backlog_quantity',models.DecimalField(decimal_places=4,default=0,max_digits=22)),
            ('on_time_pct',models.DecimalField(decimal_places=2,default=0,max_digits=7)),('in_full_pct',models.DecimalField(decimal_places=2,default=0,max_digits=7)),('otif_pct',models.DecimalField(decimal_places=2,default=0,max_digits=7)),('fill_rate_pct',models.DecimalField(decimal_places=2,default=0,max_digits=7)),('perfect_order_proxy_pct',models.DecimalField(decimal_places=2,default=0,max_digits=7)),
            ('estimated_service_failure_cost',models.DecimalField(decimal_places=2,default=0,max_digits=22)),('target_otif_pct',models.DecimalField(blank=True,decimal_places=2,max_digits=7,null=True)),('target_met',models.BooleanField(default=False)),('cause_summary',models.JSONField(blank=True,default=list)),('details',models.JSONField(blank=True,default=dict)),('calculated_at',models.DateTimeField(default=django.utils.timezone.now)),
            ('plant',models.ForeignKey(on_delete=django.db.models.deletion.CASCADE,related_name='service_level_snapshots',to='common.plant')),
        ], options={'ordering':['-period_start','scope','scope_key']}),
        migrations.AddConstraint(model_name='serviceleveltarget',constraint=models.UniqueConstraint(fields=('plant','scope','scope_key','effective_from'),name='uq_sl_target_scope_date')),
        migrations.AddConstraint(model_name='serviceleveltarget',constraint=models.CheckConstraint(condition=models.Q(effective_to__isnull=True) | models.Q(effective_to__gte=models.F('effective_from')),name='ck_sl_target_dates')),
        migrations.AddIndex(model_name='serviceleveltarget',index=models.Index(fields=['plant','scope','scope_key','is_active'],name='ix_sl_target_scope')),
        migrations.AddConstraint(model_name='servicelevelperiodsnapshot',constraint=models.UniqueConstraint(fields=('plant','reference','period_start','period_end','scope','scope_key'),name='uq_sl_snapshot_period_scope')),
        migrations.AddConstraint(model_name='servicelevelperiodsnapshot',constraint=models.CheckConstraint(condition=models.Q(period_end__gte=models.F('period_start')),name='ck_sl_snapshot_dates')),
        migrations.AddIndex(model_name='servicelevelperiodsnapshot',index=models.Index(fields=['plant','reference','period_start','scope'],name='ix_sl_snapshot_period')),
    ]
