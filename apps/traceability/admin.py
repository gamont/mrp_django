from django.contrib import admin
from .models import InventoryLot, LotBalance, LotReservation, LotTransaction, SerialComponent, SerialNumber, SerialTransaction

admin.site.register([InventoryLot, LotBalance, LotReservation, LotTransaction, SerialNumber, SerialTransaction, SerialComponent])
