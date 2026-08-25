# Generated manually for MRP 0.3.3
from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):
    initial = True
    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ("common", "0001_initial"), ("masterdata", "0001_initial"), ("traceability", "0001_initial"),
    ]
    operations = [
        migrations.CreateModel(name="InspectionPlan", fields=[
            ("id", models.BigAutoField(primary_key=True, serialize=False)), ("created_at", models.DateTimeField(auto_now_add=True)), ("updated_at", models.DateTimeField(auto_now=True)),
            ("code", models.CharField(max_length=40, unique=True)), ("description", models.CharField(max_length=200)),
            ("source_type", models.CharField(choices=[("RECEIPT","Recebimento"),("PRODUCTION","Produção"),("STOCK","Estoque")], max_length=20)),
            ("revision", models.CharField(default="A", max_length=20)), ("effective_from", models.DateField()), ("effective_to", models.DateField(blank=True, null=True)),
            ("sample_size", models.PositiveIntegerField(default=1)), ("is_active", models.BooleanField(default=True)),
            ("item", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name="inspection_plans", to="masterdata.item")),
        ], options={"ordering":["item__code","code","revision"]}),
        migrations.CreateModel(name="InspectionCharacteristic", fields=[
            ("id", models.BigAutoField(primary_key=True, serialize=False)), ("created_at", models.DateTimeField(auto_now_add=True)), ("updated_at", models.DateTimeField(auto_now=True)),
            ("sequence", models.PositiveIntegerField()), ("name", models.CharField(max_length=120)),
            ("data_type", models.CharField(choices=[("NUMERIC","Numérico"),("BOOLEAN","Conforme/não conforme"),("TEXT","Texto")], max_length=15)),
            ("unit", models.CharField(blank=True, max_length=20)), ("lower_limit", models.DecimalField(blank=True, decimal_places=6, max_digits=18, null=True)),
            ("target_value", models.DecimalField(blank=True, decimal_places=6, max_digits=18, null=True)), ("upper_limit", models.DecimalField(blank=True, decimal_places=6, max_digits=18, null=True)),
            ("is_mandatory", models.BooleanField(default=True)), ("plan", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="characteristics", to="quality.inspectionplan")),
        ], options={"ordering":["plan","sequence"]}),
        migrations.CreateModel(name="InspectionOrder", fields=[
            ("id", models.BigAutoField(primary_key=True, serialize=False)), ("created_at", models.DateTimeField(auto_now_add=True)), ("updated_at", models.DateTimeField(auto_now=True)),
            ("source_type", models.CharField(max_length=40)), ("source_id", models.CharField(max_length=64)), ("quantity_received", models.DecimalField(decimal_places=4,max_digits=18)),
            ("quantity_inspected", models.DecimalField(decimal_places=4,default=0,max_digits=18)), ("quantity_approved", models.DecimalField(decimal_places=4,default=0,max_digits=18)),
            ("quantity_rejected", models.DecimalField(decimal_places=4,default=0,max_digits=18)),
            ("status", models.CharField(choices=[("OPEN","Aberta"),("IN_PROGRESS","Em inspeção"),("APPROVED","Aprovada"),("PARTIAL","Aprovada parcialmente"),("REJECTED","Rejeitada"),("CANCELLED","Cancelada")], default="OPEN", max_length=20)),
            ("opened_at", models.DateTimeField(auto_now_add=True)), ("completed_at", models.DateTimeField(blank=True,null=True)), ("notes", models.TextField(blank=True)),
            ("inspector", models.ForeignKey(blank=True,null=True,on_delete=django.db.models.deletion.SET_NULL,related_name="quality_inspections",to=settings.AUTH_USER_MODEL)),
            ("item", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT,related_name="inspection_orders",to="masterdata.item")),
            ("lot", models.ForeignKey(blank=True,null=True,on_delete=django.db.models.deletion.PROTECT,related_name="inspection_orders",to="traceability.inventorylot")),
            ("plan", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT,related_name="orders",to="quality.inspectionplan")),
            ("plant", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT,related_name="inspection_orders",to="common.plant")),
            ("serial", models.ForeignKey(blank=True,null=True,on_delete=django.db.models.deletion.PROTECT,related_name="inspection_orders",to="traceability.serialnumber")),
            ("supplier", models.ForeignKey(blank=True,null=True,on_delete=django.db.models.deletion.PROTECT,related_name="inspection_orders",to="masterdata.supplier")),
        ], options={"ordering":["-opened_at","-id"]}),
        migrations.CreateModel(name="InspectionResult", fields=[
            ("id", models.BigAutoField(primary_key=True,serialize=False)), ("created_at",models.DateTimeField(auto_now_add=True)), ("updated_at",models.DateTimeField(auto_now=True)),
            ("sample_number",models.PositiveIntegerField(default=1)), ("numeric_value",models.DecimalField(blank=True,decimal_places=6,max_digits=18,null=True)), ("boolean_value",models.BooleanField(blank=True,null=True)),
            ("text_value",models.TextField(blank=True)), ("is_conforming",models.BooleanField()), ("measured_at",models.DateTimeField(auto_now_add=True)), ("notes",models.TextField(blank=True)),
            ("characteristic",models.ForeignKey(on_delete=django.db.models.deletion.PROTECT,related_name="results",to="quality.inspectioncharacteristic")),
            ("measured_by",models.ForeignKey(blank=True,null=True,on_delete=django.db.models.deletion.SET_NULL,to=settings.AUTH_USER_MODEL)),
            ("order",models.ForeignKey(on_delete=django.db.models.deletion.CASCADE,related_name="results",to="quality.inspectionorder")),
        ], options={"ordering":["order","characteristic__sequence","sample_number"]}),
        migrations.CreateModel(name="NonConformance", fields=[
            ("id",models.BigAutoField(primary_key=True,serialize=False)), ("created_at",models.DateTimeField(auto_now_add=True)), ("updated_at",models.DateTimeField(auto_now=True)),
            ("number",models.CharField(max_length=30,unique=True)), ("severity",models.CharField(choices=[("MINOR","Menor"),("MAJOR","Maior"),("CRITICAL","Crítica")],default="MAJOR",max_length=10)),
            ("description",models.TextField()), ("quantity_affected",models.DecimalField(decimal_places=4,max_digits=18)),
            ("status",models.CharField(choices=[("OPEN","Aberta"),("UNDER_REVIEW","Em análise"),("DISPOSITIONED","Com disposição"),("CLOSED","Encerrada")],default="OPEN",max_length=20)),
            ("closed_at",models.DateTimeField(blank=True,null=True)),
            ("inspection_order",models.ForeignKey(blank=True,null=True,on_delete=django.db.models.deletion.PROTECT,related_name="nonconformances",to="quality.inspectionorder")),
            ("item",models.ForeignKey(on_delete=django.db.models.deletion.PROTECT,related_name="nonconformances",to="masterdata.item")),
            ("lot",models.ForeignKey(blank=True,null=True,on_delete=django.db.models.deletion.PROTECT,related_name="nonconformances",to="traceability.inventorylot")),
            ("opened_by",models.ForeignKey(blank=True,null=True,on_delete=django.db.models.deletion.SET_NULL,related_name="opened_nonconformances",to=settings.AUTH_USER_MODEL)),
            ("plant",models.ForeignKey(on_delete=django.db.models.deletion.PROTECT,related_name="nonconformances",to="common.plant")),
            ("serial",models.ForeignKey(blank=True,null=True,on_delete=django.db.models.deletion.PROTECT,related_name="nonconformances",to="traceability.serialnumber")),
            ("supplier",models.ForeignKey(blank=True,null=True,on_delete=django.db.models.deletion.PROTECT,related_name="nonconformances",to="masterdata.supplier")),
        ], options={"ordering":["-created_at"]}),
        migrations.CreateModel(name="Disposition", fields=[
            ("id",models.BigAutoField(primary_key=True,serialize=False)), ("created_at",models.DateTimeField(auto_now_add=True)), ("updated_at",models.DateTimeField(auto_now=True)),
            ("decision",models.CharField(choices=[("USE_AS_IS","Usar como está"),("REWORK","Retrabalho"),("RETURN","Devolver ao fornecedor"),("SCRAP","Refugar"),("SORT","Selecionar")],max_length=20)),
            ("quantity",models.DecimalField(decimal_places=4,max_digits=18)), ("instructions",models.TextField(blank=True)), ("decided_at",models.DateTimeField(auto_now_add=True)),
            ("approved_by",models.ForeignKey(blank=True,null=True,on_delete=django.db.models.deletion.SET_NULL,to=settings.AUTH_USER_MODEL)),
            ("nonconformance",models.ForeignKey(on_delete=django.db.models.deletion.CASCADE,related_name="dispositions",to="quality.nonconformance")),
        ], options={"ordering":["nonconformance","decided_at"]}),
        migrations.AddConstraint(model_name="inspectionplan", constraint=models.CheckConstraint(condition=models.Q(("sample_size__gt",0)),name="ck_qplan_sample_pos")),
        migrations.AddConstraint(model_name="inspectionplan", constraint=models.CheckConstraint(condition=models.Q(("effective_to__isnull",True), ("effective_to__gte",models.F("effective_from")), _connector="OR"),name="ck_qplan_dates")),
        migrations.AddConstraint(model_name="inspectioncharacteristic", constraint=models.UniqueConstraint(fields=("plan","sequence"),name="uq_qchar_plan_seq")),
        migrations.AddConstraint(model_name="inspectioncharacteristic", constraint=models.CheckConstraint(condition=models.Q(("lower_limit__isnull",True),("upper_limit__isnull",True),("lower_limit__lte",models.F("upper_limit")),_connector="OR"),name="ck_qchar_limits")),
        migrations.AddConstraint(model_name="inspectionorder", constraint=models.UniqueConstraint(fields=("source_type","source_id","plan"),name="uq_qorder_source_plan")),
        migrations.AddConstraint(model_name="inspectionorder", constraint=models.CheckConstraint(condition=models.Q(("quantity_received__gt",0)),name="ck_qorder_received_pos")),
        migrations.AddConstraint(model_name="inspectionorder", constraint=models.CheckConstraint(condition=models.Q(("quantity_inspected__gte",0)),name="ck_qorder_inspected_nonneg")),
        migrations.AddConstraint(model_name="inspectionorder", constraint=models.CheckConstraint(condition=models.Q(("quantity_approved__gte",0)),name="ck_qorder_approved_nonneg")),
        migrations.AddConstraint(model_name="inspectionorder", constraint=models.CheckConstraint(condition=models.Q(("quantity_rejected__gte",0)),name="ck_qorder_rejected_nonneg")),
        migrations.AddConstraint(model_name="inspectionresult", constraint=models.UniqueConstraint(fields=("order","characteristic","sample_number"),name="uq_qresult_order_char_sample")),
        migrations.AddConstraint(model_name="nonconformance", constraint=models.CheckConstraint(condition=models.Q(("quantity_affected__gt",0)),name="ck_ncr_qty_pos")),
        migrations.AddConstraint(model_name="disposition", constraint=models.CheckConstraint(condition=models.Q(("quantity__gt",0)),name="ck_disposition_qty_pos")),
        migrations.AddIndex(model_name="inspectionplan", index=models.Index(fields=["item","source_type","is_active"],name="ix_qplan_item_source")),
        migrations.AddIndex(model_name="inspectionorder", index=models.Index(fields=["plant","status","opened_at"],name="ix_qorder_plant_status")),
        migrations.AddIndex(model_name="inspectionorder", index=models.Index(fields=["item","status"],name="ix_qorder_item_status")),
        migrations.AddIndex(model_name="nonconformance", index=models.Index(fields=["plant","status","severity"],name="ix_ncr_status_severity")),
    ]
