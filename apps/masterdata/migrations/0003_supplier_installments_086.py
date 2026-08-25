from django.db import migrations, models
class Migration(migrations.Migration):
    dependencies=[('masterdata','0002_supplier_payment_terms_085')]
    operations=[migrations.AddField(model_name='supplier',name='payment_installments',field=models.JSONField(blank=True,default=list,help_text='Opcional: [{"days":30,"percent":50},{"days":60,"percent":50}]'))]
