from django.contrib import admin

from .models import (
    DowntimeEvent, DowntimeReason, Machine, MachineProductionRecord, OEEPeriodSnapshot,
    OEEShiftSnapshot, OEETarget, OperatorProfile, TerminalStation,
)


@admin.register(OperatorProfile)
class OperatorProfileAdmin(admin.ModelAdmin):
    list_display = ("badge_code", "user", "is_active", "failed_attempts", "locked_until")
    search_fields = ("badge_code", "user__username", "user__first_name", "user__last_name")


@admin.register(Machine)
class MachineAdmin(admin.ModelAdmin):
    list_display = ("code", "name", "plant", "work_center", "status", "current_operation", "planned_minutes_per_day", "ideal_cycle_seconds", "is_active")
    list_filter = ("plant", "work_center", "status", "is_active")
    search_fields = ("code", "name")


@admin.register(TerminalStation)
class TerminalStationAdmin(admin.ModelAdmin):
    list_display = ("code", "name", "plant", "work_center", "machine", "is_active")
    list_filter = ("plant", "is_active")


@admin.register(DowntimeReason)
class DowntimeReasonAdmin(admin.ModelAdmin):
    list_display = ("code", "description", "plant", "category", "is_active")
    list_filter = ("plant", "category", "is_active")


@admin.register(DowntimeEvent)
class DowntimeEventAdmin(admin.ModelAdmin):
    list_display = ("machine", "reason", "operation", "started_at", "ended_at", "reported_by")
    list_filter = ("machine__plant", "reason__category")
    readonly_fields = ("created_at", "updated_at")


@admin.register(MachineProductionRecord)
class MachineProductionRecordAdmin(admin.ModelAdmin):
    list_display = ("machine", "report", "operation", "reported_at")
    list_filter = ("machine__plant", "machine")
    date_hierarchy = "reported_at"


@admin.register(OEEPeriodSnapshot)
class OEEPeriodSnapshotAdmin(admin.ModelAdmin):
    list_display = ("metric_date", "machine", "oee", "availability", "performance", "quality", "failures", "mtbf_minutes", "mttr_minutes")
    list_filter = ("machine__plant", "machine", "metric_date")
    readonly_fields = ("calculated_at", "created_at", "updated_at")


@admin.register(OEETarget)
class OEETargetAdmin(admin.ModelAdmin):
    list_display = ("plant", "work_center", "machine", "effective_from", "effective_to", "oee_target", "is_active")
    list_filter = ("plant", "is_active")
    search_fields = ("plant__code", "work_center__code", "machine__code")


@admin.register(OEEShiftSnapshot)
class OEEShiftSnapshotAdmin(admin.ModelAdmin):
    list_display = ("metric_date", "shift", "machine", "oee", "availability", "performance", "quality", "failures")
    list_filter = ("machine__plant", "shift", "metric_date")
    readonly_fields = ("calculated_at", "created_at", "updated_at")
