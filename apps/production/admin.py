from django.contrib import admin
from .models import (
    ProductionReport,
    WorkOrder,
    WorkOrderCompletion,
    WorkOrderMaterial,
    WorkOrderOperation,
)

for model in [
    WorkOrder,
    WorkOrderMaterial,
    WorkOrderOperation,
    ProductionReport,
    WorkOrderCompletion,
]:
    admin.site.register(model)
