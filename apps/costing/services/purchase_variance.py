from decimal import Decimal
from django.db import transaction
from apps.costing.models import CostVersion, ItemCost, PurchasePriceVariance
from apps.purchasing.models import GoodsReceipt

D = Decimal

@transaction.atomic
def calculate_purchase_price_variance(receipt: GoodsReceipt, version: CostVersion | None = None):
    plant = receipt.purchase_order_line.purchase_order.plant
    version = version or CostVersion.objects.filter(plant=plant, status=CostVersion.Status.ACTIVE).order_by("-effective_from").first()
    if not version:
        raise ValueError("Não existe versão de custo ativa para a planta.")
    line = receipt.purchase_order_line
    standard = ItemCost.objects.filter(cost_version=version, item=line.item).values_list("total_cost", flat=True).first()
    standard = standard if standard is not None else line.item.standard_cost
    variance = (line.unit_price - standard) * receipt.quantity
    obj, _ = PurchasePriceVariance.objects.update_or_create(goods_receipt=receipt, defaults={"cost_version": version, "standard_unit_cost": standard, "actual_unit_price": line.unit_price, "quantity": receipt.quantity, "variance_amount": variance, "favorable": variance <= 0})
    return obj
