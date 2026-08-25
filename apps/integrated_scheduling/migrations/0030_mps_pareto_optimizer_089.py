from django.db import migrations, models

class Migration(migrations.Migration):
    dependencies=[('integrated_scheduling','0029_mps_optimizer_088')]
    operations=[
        migrations.AddField(model_name='mpsoptimizationpolicy',name='enable_cp_sat_pareto',field=models.BooleanField(default=True)),
        migrations.AddField(model_name='mpsoptimizationpolicy',name='pareto_candidate_limit',field=models.PositiveIntegerField(default=12)),
        migrations.AddField(model_name='mpsoptimizationpolicy',name='pareto_solver_time_limit_seconds',field=models.PositiveIntegerField(default=20)),
        migrations.AddField(model_name='mpsoptimizationpolicy',name='pareto_quantity_scale',field=models.PositiveIntegerField(default=100)),
        migrations.AddField(model_name='mpsoptimizationpolicy',name='pareto_max_change_percent',field=models.DecimalField(decimal_places=3,default=30,max_digits=7)),
        migrations.AddField(model_name='mpsrevisionoptimizationrun',name='optimizer_mode',field=models.CharField(choices=[('HEURISTIC','Heurístico'),('CP_SAT_PARETO','CP-SAT Pareto')],default='HEURISTIC',max_length=20)),
        migrations.AddField(model_name='mpsrevisionoptimizationrun',name='solver_status',field=models.CharField(blank=True,max_length=30)),
        migrations.AlterField(model_name='mpsrevisionoptimizationcandidate',name='strategy',field=models.CharField(choices=[('BASELINE','Revisão atual'),('SHIFT_LATER','Postergar volume'),('SHIFT_EARLIER','Antecipar volume'),('LEVEL_LOAD','Nivelar buckets'),('SUPPLIER_TERMS','Fornecedor/prazo financeiro'),('CP_SAT_PARETO','CP-SAT / fronteira Pareto')],max_length=24)),
        migrations.AddField(model_name='mpsrevisionoptimizationcandidate',name='objective_vector',field=models.JSONField(blank=True,default=dict)),
        migrations.AddField(model_name='mpsrevisionoptimizationcandidate',name='pareto_rank',field=models.PositiveIntegerField(blank=True,null=True)),
        migrations.AddField(model_name='mpsrevisionoptimizationcandidate',name='is_pareto',field=models.BooleanField(default=False)),
        migrations.AddField(model_name='mpsrevisionoptimizationcandidate',name='dominated_by_count',field=models.PositiveIntegerField(default=0)),
        migrations.AddConstraint(model_name='mpsoptimizationpolicy',constraint=models.CheckConstraint(condition=models.Q(pareto_candidate_limit__gt=0),name='ck_mpsopt_pareto_limit_gt0')),
        migrations.AddConstraint(model_name='mpsoptimizationpolicy',constraint=models.CheckConstraint(condition=models.Q(pareto_max_change_percent__gte=0)&models.Q(pareto_max_change_percent__lte=100),name='ck_mpsopt_pareto_change_pct')),
    ]
