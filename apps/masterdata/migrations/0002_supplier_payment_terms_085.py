from django.db import migrations, models

class Migration(migrations.Migration):
    dependencies=[("masterdata","0001_initial")]
    operations=[
        migrations.AddField(model_name="supplier",name="payment_terms_days",field=models.PositiveIntegerField(default=30,help_text="Dias entre a data planejada da compra e o desembolso estimado.")),
        migrations.AddField(model_name="supplier",name="payment_terms_code",field=models.CharField(blank=True,default="NET30",max_length=30)),
    ]
