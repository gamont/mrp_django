from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion
import django.utils.timezone


class Migration(migrations.Migration):
    dependencies = [
        ("integrated_scheduling", "0015_commercial_promising_074"),
        ("demand", "0001_initial"),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name="SalesOrderCommercialContact",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("name", models.CharField(max_length=160)),
                ("email", models.EmailField(blank=True, max_length=254)),
                ("api_url", models.URLField(blank=True)),
                ("preferred_channel", models.CharField(choices=[("EMAIL","E-mail"),("API","API"),("MANUAL","Manual")], default="EMAIL", max_length=12)),
                ("is_active", models.BooleanField(default=True)),
                ("sales_order", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="commercial_contacts", to="demand.salesorder")),
            ],
            options={"ordering": ["sales_order", "name"]},
        ),
        migrations.AddIndex(model_name="salesordercommercialcontact", index=models.Index(fields=["sales_order","is_active"], name="ix_socontact_order_active")),
        migrations.CreateModel(
            name="CustomerPromiseResponse",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("response", models.CharField(choices=[("ACCEPTED","Aceita"),("REJECTED","Rejeitada"),("COUNTERPROPOSED","Contraproposta")], max_length=20)),
                ("channel", models.CharField(choices=[("EMAIL","E-mail"),("API","API"),("PHONE","Telefone"),("MANUAL","Manual")], default="MANUAL", max_length=12)),
                ("confirmed_date", models.DateField(blank=True, null=True)),
                ("counterproposed_date", models.DateField(blank=True, null=True)),
                ("notes", models.TextField(blank=True)),
                ("external_reference", models.CharField(blank=True, max_length=120)),
                ("received_at", models.DateTimeField(default=django.utils.timezone.now)),
                ("promise", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="customer_responses", to="integrated_scheduling.salesorderpromise")),
                ("received_by", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="customer_promise_responses_received", to=settings.AUTH_USER_MODEL)),
            ],
            options={"ordering": ["-received_at", "-created_at"]},
        ),
        migrations.AddIndex(model_name="customerpromiseresponse", index=models.Index(fields=["promise","response","received_at"], name="ix_custresp_promise_resp")),
        migrations.CreateModel(
            name="CommercialCommunication",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("channel", models.CharField(choices=[("EMAIL","E-mail"),("API","API"),("MANUAL","Manual")], max_length=12)),
                ("direction", models.CharField(choices=[("OUTBOUND","Saída"),("INBOUND","Entrada")], default="OUTBOUND", max_length=12)),
                ("status", models.CharField(choices=[("PENDING","Pendente"),("SENT","Enviada"),("FAILED","Falhou")], default="PENDING", max_length=12)),
                ("subject", models.CharField(blank=True, max_length=240)),
                ("body", models.TextField(blank=True)),
                ("payload", models.JSONField(blank=True, default=dict)),
                ("external_reference", models.CharField(blank=True, max_length=160)),
                ("idempotency_key", models.CharField(max_length=160, unique=True)),
                ("sent_at", models.DateTimeField(blank=True, null=True)),
                ("error", models.TextField(blank=True)),
                ("contact", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="communications", to="integrated_scheduling.salesordercommercialcontact")),
                ("promise", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="communications", to="integrated_scheduling.salesorderpromise")),
                ("service_case", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="communications", to="integrated_scheduling.commercialservicecase")),
            ],
            options={"ordering": ["-created_at"]},
        ),
        migrations.AddIndex(model_name="commercialcommunication", index=models.Index(fields=["promise","status","created_at"], name="ix_comm_promise_status")),
    ]
