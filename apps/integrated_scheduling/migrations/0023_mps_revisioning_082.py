from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):
    dependencies = [
        ('integrated_scheduling', '0022_interactive_mps_081'),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name='MPSRevision',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('number', models.PositiveIntegerField()),
                ('kind', models.CharField(choices=[('BASELINE','Baseline'),('WORKING','Revisão'),('ROLLBACK','Rollback')], default='WORKING', max_length=12)),
                ('status', models.CharField(choices=[('DRAFT','Rascunho'),('PENDING_APPROVAL','Aguardando aprovação'),('APPROVED','Aprovada'),('REJECTED','Rejeitada'),('SUPERSEDED','Substituída')], default='DRAFT', max_length=20)),
                ('label', models.CharField(blank=True, max_length=160)),
                ('notes', models.TextField(blank=True)),
                ('summary', models.JSONField(blank=True, default=dict)),
                ('rccp_summary', models.JSONField(blank=True, default=dict)),
                ('mrp_impact_summary', models.JSONField(blank=True, default=dict)),
                ('submitted_at', models.DateTimeField(blank=True, null=True)),
                ('approved_at', models.DateTimeField(blank=True, null=True)),
                ('decision_notes', models.TextField(blank=True)),
                ('publication', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='revisions', to='integrated_scheduling.operationalmpspublication')),
                ('parent', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='children', to='integrated_scheduling.mpsrevision')),
                ('created_by', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='mps_revisions_created', to=settings.AUTH_USER_MODEL)),
                ('submitted_by', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='mps_revisions_submitted', to=settings.AUTH_USER_MODEL)),
                ('approved_by', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='mps_revisions_approved', to=settings.AUTH_USER_MODEL)),
            ],
            options={'ordering':['publication','-number']},
        ),
        migrations.AddConstraint(model_name='mpsrevision', constraint=models.UniqueConstraint(fields=('publication','number'), name='uq_mpsrev_pub_number')),
        migrations.AddIndex(model_name='mpsrevision', index=models.Index(fields=['publication','status'], name='ix_mpsrev_pub_status')),
        migrations.CreateModel(
            name='MPSRevisionLine',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('created_at', models.DateTimeField(auto_now_add=True)), ('updated_at', models.DateTimeField(auto_now=True)),
                ('bucket_start', models.DateField()), ('bucket_end', models.DateField()),
                ('quantity', models.DecimalField(decimal_places=4,max_digits=22)),
                ('baseline_quantity', models.DecimalField(decimal_places=4,default=0,max_digits=22)),
                ('mps_status', models.CharField(choices=[('PLANNED','Planejado'),('FIRM','Firme'),('FROZEN','Congelado')], default='PLANNED', max_length=15)),
                ('frozen_reason', models.CharField(blank=True,max_length=160)),
                ('item', models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name='mps_revision_lines', to='masterdata.item')),
                ('revision', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='lines', to='integrated_scheduling.mpsrevision')),
            ],
            options={'ordering':['bucket_start','item__code']},
        ),
        migrations.AddConstraint(model_name='mpsrevisionline', constraint=models.UniqueConstraint(fields=('revision','item','bucket_start'), name='uq_mpsrevline_item_week')),
        migrations.AddIndex(model_name='mpsrevisionline', index=models.Index(fields=['revision','bucket_start'], name='ix_mpsrevline_week')),
        migrations.CreateModel(
            name='MPSRevisionRCCPLine',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('created_at', models.DateTimeField(auto_now_add=True)), ('updated_at', models.DateTimeField(auto_now=True)),
                ('bucket_start', models.DateField()),
                ('required_hours', models.DecimalField(decimal_places=4,default=0,max_digits=18)),
                ('available_hours', models.DecimalField(decimal_places=4,default=0,max_digits=18)),
                ('overload_hours', models.DecimalField(decimal_places=4,default=0,max_digits=18)),
                ('overload_percent', models.DecimalField(decimal_places=3,default=0,max_digits=10)),
                ('severity', models.CharField(choices=[('INFO','Informação'),('WARNING','Atenção'),('CRITICAL','Crítica')], default='WARNING', max_length=10)),
                ('revision', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='rccp_lines', to='integrated_scheduling.mpsrevision')),
                ('work_center', models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name='mps_revision_rccp_lines', to='masterdata.workcenter')),
            ],
            options={'ordering':['bucket_start','work_center__code']},
        ),
        migrations.AddConstraint(model_name='mpsrevisionrccpline', constraint=models.UniqueConstraint(fields=('revision','work_center','bucket_start'), name='uq_mpsrevrccp_center_week')),
    ]
