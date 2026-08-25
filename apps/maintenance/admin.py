from django.contrib import admin

from .models import AssetMeterReading, FailureEvent, MaintenanceAsset, MaintenancePart, MaintenancePlan, MaintenanceWorkOrder


@admin.register(MaintenanceAsset)
class MaintenanceAssetAdmin(admin.ModelAdmin):
    list_display = ("code", "name", "plant", "asset_type", "criticality", "machine", "is_active")
    list_filter = ("plant", "asset_type", "criticality", "is_active")
    search_fields = ("code", "name", "serial_number")


@admin.register(MaintenancePlan)
class MaintenancePlanAdmin(admin.ModelAdmin):
    list_display = ("code", "asset", "strategy", "next_due_date", "next_due_meter", "is_active")
    list_filter = ("strategy", "is_active", "asset__plant")


class MaintenancePartInline(admin.TabularInline):
    model = MaintenancePart
    extra = 0


@admin.register(MaintenanceWorkOrder)
class MaintenanceWorkOrderAdmin(admin.ModelAdmin):
    list_display = ("number", "asset", "order_type", "priority", "status", "scheduled_start", "assigned_to")
    list_filter = ("plant", "order_type", "priority", "status")
    search_fields = ("number", "asset__code", "title")
    inlines = [MaintenancePartInline]


admin.site.register(AssetMeterReading)
admin.site.register(FailureEvent)

from .models import TechnicianSkill, TechnicianProfile, TechnicianSkillAssignment, WorkOrderAssignment, MaintenanceSLA, ConditionReading, ConditionRule
admin.site.register(TechnicianSkill)
admin.site.register(TechnicianProfile)
admin.site.register(TechnicianSkillAssignment)
admin.site.register(WorkOrderAssignment)
admin.site.register(MaintenanceSLA)
admin.site.register(ConditionReading)
admin.site.register(ConditionRule)

from .models import MaintenanceRequiredSkill, MaintenancePartReservation, MaintenanceScheduleConflict
admin.site.register(MaintenanceRequiredSkill)
admin.site.register(MaintenancePartReservation)
admin.site.register(MaintenanceScheduleConflict)
