from django.contrib import admin
from .models import (
    BOMLine,
    Item,
    ItemPlantPolicy,
    ItemSubstitute,
    ItemSupplier,
    Routing,
    RoutingOperation,
    Supplier,
    WorkCenter,
    WorkCenterShift,
)

for model in [
    Item,
    ItemPlantPolicy,
    BOMLine,
    WorkCenter,
    WorkCenterShift,
    Routing,
    RoutingOperation,
    Supplier,
    ItemSupplier,
    ItemSubstitute,
]:
    admin.site.register(model)
