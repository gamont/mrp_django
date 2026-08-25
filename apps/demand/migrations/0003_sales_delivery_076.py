from django.db import migrations, models
import django.db.models.deletion

class Migration(migrations.Migration):
    dependencies=[('demand','0001_initial')]
    operations=[
      migrations.CreateModel(name='SalesDelivery',fields=[('id',models.BigAutoField(auto_created=True,primary_key=True,serialize=False,verbose_name='ID')),('created_at',models.DateTimeField(auto_now_add=True)),('updated_at',models.DateTimeField(auto_now=True)),('number',models.CharField(max_length=50,unique=True)),('delivery_date',models.DateField()),('shipped_at',models.DateTimeField(blank=True,null=True)),('carrier',models.CharField(blank=True,max_length=120)),('tracking_reference',models.CharField(blank=True,max_length=120)),('notes',models.TextField(blank=True)),('plant',models.ForeignKey(on_delete=django.db.models.deletion.PROTECT,related_name='sales_deliveries',to='common.plant'))],options={'ordering':['-delivery_date','number']}),
      migrations.CreateModel(name='SalesDeliveryLine',fields=[('id',models.BigAutoField(auto_created=True,primary_key=True,serialize=False,verbose_name='ID')),('created_at',models.DateTimeField(auto_now_add=True)),('updated_at',models.DateTimeField(auto_now=True)),('quantity',models.DecimalField(decimal_places=4,max_digits=18)),('delivery',models.ForeignKey(on_delete=django.db.models.deletion.CASCADE,related_name='lines',to='demand.salesdelivery')),('sales_order_line',models.ForeignKey(on_delete=django.db.models.deletion.PROTECT,related_name='delivery_lines',to='demand.salesorderline'))],options={'ordering':['delivery','sales_order_line__line_number']}),
      migrations.AddIndex(model_name='salesdelivery',index=models.Index(fields=['plant','delivery_date'],name='ix_salesdel_plant_date')),
      migrations.AddConstraint(model_name='salesdeliveryline',constraint=models.UniqueConstraint(fields=('delivery','sales_order_line'),name='uq_delivery_sales_line')),
      migrations.AddConstraint(model_name='salesdeliveryline',constraint=models.CheckConstraint(condition=models.Q(('quantity__gt',0)),name='ck_deliveryline_qty_pos')),
      migrations.AddIndex(model_name='salesdeliveryline',index=models.Index(fields=['sales_order_line'],name='ix_deliveryline_sol')),
    ]
