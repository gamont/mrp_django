from django.contrib import admin

from .models import DomainEvent, Plant, ShopCalendarDay


@admin.register(DomainEvent)
class DomainEventAdmin(admin.ModelAdmin):
    list_display = ("occurred_at", "event_type", "aggregate_type", "aggregate_id", "idempotency_key")
    list_filter = ("event_type", "aggregate_type", "occurred_at")
    search_fields = ("aggregate_id", "idempotency_key")
    readonly_fields = (
        "event_id",
        "idempotency_key",
        "event_type",
        "aggregate_type",
        "aggregate_id",
        "payload",
        "actor",
        "occurred_at",
    )

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False


admin.site.register(Plant)
admin.site.register(ShopCalendarDay)
