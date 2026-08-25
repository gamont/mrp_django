from django.contrib import admin
from .models import Forecast, MasterProductionSchedule, SalesOrder, SalesOrderLine

for model in [Forecast, SalesOrder, SalesOrderLine, MasterProductionSchedule]:
    admin.site.register(model)


from .models import SalesDelivery, SalesDeliveryLine
for _m in [SalesDelivery, SalesDeliveryLine]:
    try: admin.site.register(_m)
    except admin.sites.AlreadyRegistered: pass
