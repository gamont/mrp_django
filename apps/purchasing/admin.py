from django.contrib import admin
from .models import GoodsReceipt, PurchaseOrder, PurchaseOrderLine

for model in [PurchaseOrder, PurchaseOrderLine, GoodsReceipt]:
    admin.site.register(model)
