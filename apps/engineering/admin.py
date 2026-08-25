from django.contrib import admin
from .models import *

class ChangeItemInline(admin.TabularInline): model=EngineeringChangeItem; extra=0
class ApprovalInline(admin.TabularInline): model=EngineeringChangeApproval; extra=0
@admin.register(EngineeringChange)
class EngineeringChangeAdmin(admin.ModelAdmin):
    list_display=("number","plant","title","status","effectivity_type","effective_date")
    list_filter=("plant","status","effectivity_type")
    search_fields=("number","title","reason")
    inlines=(ChangeItemInline,ApprovalInline)
@admin.register(BOMRevision)
class BOMRevisionAdmin(admin.ModelAdmin): list_display=("parent","revision","plant","status","effective_from")
admin.site.register([BOMRevisionLine, RoutingRevision, EngineeringImpact])
