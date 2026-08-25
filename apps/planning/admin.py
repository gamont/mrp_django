from django.contrib import admin
from .models import (
    CapacityAllocation,
    CapacityScenario,
    PeggingRecord,
    PlannedOrder,
    PlanningBucket,
    PlanningChange,
    PlanningMessage,
    PlanningRun,
)

for model in [
    PlanningRun,
    PlanningBucket,
    PlannedOrder,
    PeggingRecord,
    PlanningMessage,
    PlanningChange,
    CapacityScenario,
    CapacityAllocation,
]:
    admin.site.register(model)
