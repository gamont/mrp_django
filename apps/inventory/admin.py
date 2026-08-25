from django.contrib import admin
from .models import InventoryTransaction, Location, Reservation, StockBalance, Warehouse

for model in [Warehouse, Location, StockBalance, InventoryTransaction, Reservation]:
    admin.site.register(model)
