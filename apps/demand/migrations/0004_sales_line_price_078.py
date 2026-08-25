from django.db import migrations, models
class Migration(migrations.Migration):
    dependencies=[('demand','0003_sales_delivery_076')]
    operations=[migrations.AddField(model_name='salesorderline',name='unit_net_price',field=models.DecimalField(blank=True,decimal_places=4,max_digits=18,null=True)), migrations.AddConstraint(model_name='salesorderline',constraint=models.CheckConstraint(condition=models.Q(unit_net_price__isnull=True) | models.Q(unit_net_price__gte=0),name='ck_sol_net_price_nonneg'))]
