from django.db import migrations, models
import django.db.models.deletion

class Migration(migrations.Migration):
    dependencies = [("planning", "0001_initial"), ("demand", "0001_initial"), ("masterdata", "0001_initial")]
    operations = [
        migrations.CreateModel(
            name="DemandPeggingAllocation",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("source_type", models.CharField(choices=[("SALES_ORDER_LINE","Linha de pedido"),("MPS","MPS"),("FORECAST","Previsão"),("SAFETY_STOCK","Estoque de segurança")], max_length=24)),
                ("source_id", models.PositiveIntegerField(blank=True, null=True)),
                ("required_date", models.DateField()),
                ("quantity", models.DecimalField(decimal_places=4, max_digits=18)),
                ("details", models.JSONField(blank=True, default=dict)),
                ("planned_order", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="demand_allocations", to="planning.plannedorder")),
                ("sales_order_line", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.CASCADE, related_name="mrp_allocations", to="demand.salesorderline")),
                ("top_level_item", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="demand_pegging_allocations", to="masterdata.item")),
            ],
            options={"ordering":["planned_order","required_date","source_type","source_id"]},
        ),
        migrations.AddIndex(model_name="demandpeggingallocation", index=models.Index(fields=["source_type","source_id"], name="ix_dempeg_source")),
        migrations.AddIndex(model_name="demandpeggingallocation", index=models.Index(fields=["planned_order","source_type"], name="ix_dempeg_order_source")),
        migrations.AddConstraint(model_name="demandpeggingallocation", constraint=models.CheckConstraint(condition=models.Q(("quantity__gt", 0)), name="ck_dempeg_qty_pos")),
    ]
