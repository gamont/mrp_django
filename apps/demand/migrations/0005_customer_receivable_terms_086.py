from django.db import migrations, models
class Migration(migrations.Migration):
    dependencies=[('demand','0004_sales_line_price_078')]
    operations=[
        migrations.AddField(model_name='salesorder',name='receivable_terms_days',field=models.PositiveIntegerField(default=30,help_text='Dias entre a data de compromisso/entrega planejada e o recebimento estimado.')),
        migrations.AddField(model_name='salesorder',name='receivable_terms_code',field=models.CharField(blank=True,default='NET30',max_length=30)),
        migrations.AddField(model_name='salesorder',name='receivable_installments',field=models.JSONField(blank=True,default=list,help_text='Opcional: [{"days":30,"percent":50},{"days":60,"percent":50}]')),
    ]
